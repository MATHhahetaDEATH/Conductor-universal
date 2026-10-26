from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, BigInteger, ForeignKey, JSON, LargeBinary, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class DbMeta(Base):
    __tablename__ = 'db_meta'
    magic: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    hash_method: Mapped[str] = mapped_column(String)

class Blob(Base):
    __tablename__ = 'blob'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    compress: Mapped[str] = mapped_column(String)
    raw_size: Mapped[int] = mapped_column(BigInteger)
    stored_size: Mapped[int] = mapped_column(BigInteger)

class Chunk(Base):
    __tablename__ = 'chunk'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    compress: Mapped[str] = mapped_column(String)
    raw_size: Mapped[int] = mapped_column(BigInteger)
    stored_size: Mapped[int] = mapped_column(BigInteger)

class ChunkGroup(Base):
    __tablename__ = 'chunk_group'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer)

class ChunkGroupChunkBinding(Base):
    __tablename__ = 'chunk_group_chunk_binding'
    chunk_group_id: Mapped[int] = mapped_column(ForeignKey('chunk_group.id'), primary_key=True)
    chunk_offset: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey('chunk.id'), index=True)

class BlobChunkGroupBinding(Base):
    __tablename__ = 'blob_chunk_group_binding'
    blob_id: Mapped[int] = mapped_column(ForeignKey('blob.id'), primary_key=True)
    chunk_group_offset: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_group_id: Mapped[int] = mapped_column(ForeignKey('chunk_group.id'), index=True)

class Fileset(Base):
    __tablename__ = 'fileset'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_id: Mapped[int] = mapped_column(Integer, default=0) # 0 for base, >0 for delta
    file_count: Mapped[int] = mapped_column(BigInteger)
    total_raw_size: Mapped[int] = mapped_column(BigInteger)

class FileEntry(Base):
    __tablename__ = 'file_entry'
    fileset_id: Mapped[int] = mapped_column(ForeignKey('fileset.id'), primary_key=True)
    path: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[int] = mapped_column(Integer) # 0: file, 1: dir, 2: symlink
    mode: Mapped[int] = mapped_column(Integer)
    uid: Mapped[int] = mapped_column(Integer)
    gid: Mapped[int] = mapped_column(Integer)
    mtime: Mapped[int] = mapped_column(BigInteger)
    mtime_ns: Mapped[int] = mapped_column(Integer)
    
    blob_id: Mapped[Optional[int]] = mapped_column(ForeignKey('blob.id'), index=True)
    symlink_target: Mapped[Optional[str]] = mapped_column(String)

class Backup(Base):
    __tablename__ = 'backup'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    creator: Mapped[str] = mapped_column(String)
    comment: Mapped[str] = mapped_column(String)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    
    fileset_id: Mapped[int] = mapped_column(ForeignKey('fileset.id'))
    
    file_count: Mapped[int] = mapped_column(BigInteger)
    total_raw_size: Mapped[int] = mapped_column(BigInteger)
