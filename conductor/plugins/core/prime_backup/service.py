import os
import time
from pathlib import Path
from typing import List, Optional
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import Session, sessionmaker
from .models import Base, Backup, Fileset, FileEntry, Blob, Chunk, ChunkGroup, ChunkGroupChunkBinding, BlobChunkGroupBinding
from .engine import BackupEngine

class BackupService:
    def __init__(self, db_url: str, storage_root: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.backup_engine = BackupEngine(storage_root)

    def create_backup(self, source_dir: str, creator: str, comment: str) -> Backup:
        source_path = Path(source_dir)
        with self.Session() as session:
            # 1. Start a new Fileset
            fileset = Fileset(file_count=0, total_raw_size=0)
            session.add(fileset)
            session.flush()
            
            total_files = 0
            total_size = 0
            
            # 2. Scan and Process
            for root, dirs, files in os.walk(source_path):
                for name in files:
                    file_path = Path(root) / name
                    rel_path = file_path.relative_to(source_path).as_posix()
                    
                    # Basic skip for Backup directory if it happens to be inside (though validated against)
                    if "backup" in file_path.parts:
                        continue
                        
                    stat = file_path.stat()
                    total_files += 1
                    total_size += stat.st_size
                    
                    # Deduplication check
                    # For simplicity in this native rewrite, we focus on full-file blobs first, 
                    # but we keep the architecture ready for Chunks.
                    
                    # Calculate full file hash
                    file_hash = self._calc_file_hash(file_path)
                    
                    # Check if blob exists
                    blob = session.execute(select(Blob).where(Blob.hash == file_hash)).scalar_one_or_none()
                    if not blob:
                        # Process chunks and store
                        # (In a full implementation we'd use CDC here, but let's stick to simple blob for now
                        # to ensure stability, then add chunking if needed)
                        blob_raw_data = file_path.read_bytes()
                        blob_hash, stored_size = self.backup_engine.store_chunk(blob_raw_data)
                        blob = Blob(hash=blob_hash, raw_size=len(blob_raw_data), stored_size=stored_size, compress="zstd")
                        session.add(blob)
                        session.flush()
                    
                    file_entry = FileEntry(
                        fileset_id=fileset.id,
                        path=rel_path,
                        role=0,
                        mode=stat.st_mode,
                        uid=stat.st_uid,
                        gid=stat.st_gid,
                        mtime=int(stat.st_mtime),
                        mtime_ns=stat.st_mtime_ns % 1_000_000_000,
                        blob_id=blob.id
                    )
                    session.add(file_entry)
            
            fileset.file_count = total_files
            fileset.total_raw_size = total_size
            
            # 3. Create Backup entry
            backup = Backup(
                creator=creator,
                comment=comment,
                fileset_id=fileset.id,
                file_count=total_files,
                total_raw_size=total_size
            )
            session.add(backup)
            session.commit()
            return backup

    def _calc_file_hash(self, path: Path) -> str:
        import blake3
        hasher = blake3.blake3()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_history(self) -> List[Backup]:
        with Session(self.engine) as session:
            return session.execute(select(Backup).order_by(desc(Backup.timestamp))).scalars().all()

    def restore_backup(self, backup_id: int, target_dir: str):
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        
        with Session(self.engine) as session:
            backup = session.get(Backup, backup_id)
            if not backup:
                raise ValueError(f"Backup {backup_id} not found")
                
            file_entries = session.execute(select(FileEntry).where(FileEntry.fileset_id == backup.fileset_id)).scalars().all()
            
            for entry in file_entries:
                dest = target_path / entry.path
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                if entry.blob_id:
                    blob = session.get(Blob, entry.blob_id)
                    data = self.backup_engine.read_chunk(blob.hash)
                    with open(dest, "wb") as f:
                        f.write(data)
                
                # Restore metadata
                os.chmod(dest, entry.mode)
                os.utime(dest, ns=(entry.mtime * 1_000_000_000 + entry.mtime_ns, entry.mtime * 1_000_000_000 + entry.mtime_ns))

    def delete_backup(self, backup_id: int):
        with self.Session() as session:
            backup = session.get(Backup, backup_id)
            if not backup:
                raise ValueError(f"Backup {backup_id} not found")
            
            # 1. Delete file entries associated with the fileset
            # (Note: Filesets might be shared in a full delta implementation, 
            # but in our current native one we create a new one per backup)
            fileset_id = backup.fileset_id
            
            # Delete entries
            from sqlalchemy import delete
            session.execute(delete(FileEntry).where(FileEntry.fileset_id == fileset_id))
            
            # Delete fileset
            fileset = session.get(Fileset, fileset_id)
            if fileset:
                session.delete(fileset)
                
            # Delete backup record
            session.delete(backup)
            session.commit()
            
            # Note: We don't automatically delete Blobs/Chunks here 
            # as they might be used by other backups (deduplication).
            # A separate 'vacuum' task should handle orphaned blob cleanup.
