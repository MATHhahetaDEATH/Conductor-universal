import os
import hashlib
import zstandard as zstd
from pathlib import Path
from typing import List, Tuple, Generator
import blake3
from fastcdc import fastcdc

class BackupEngine:
    def __init__(self, storage_root: str):
        self.storage_root = Path(storage_root)
        self.blobs_dir = self.storage_root / "blobs"
        self.temp_dir = self.storage_root / "temp"
        
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.compressor = zstd.ZstdCompressor(level=3)
        self.decompressor = zstd.ZstdDecompressor()

    def get_blob_path(self, blob_hash: str) -> Path:
        """Returns the sharded path for a blob hash."""
        return self.blobs_dir / blob_hash[0:2] / blob_hash[2:4] / blob_hash

    def store_chunk(self, data: bytes) -> Tuple[str, int]:
        """Compresses and stores a chunk if it doesn't exist. Returns (hash, stored_size)."""
        raw_hash = blake3.blake3(data).hexdigest()
        target_path = self.get_blob_path(raw_hash)
        
        if target_path.exists():
            return raw_hash, target_path.stat().st_size
        
        compressed_data = self.compressor.compress(data)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use a temp file for atomic write
        temp_file = self.temp_dir / f"tmp_{raw_hash}"
        with open(temp_file, "wb") as f:
            f.write(compressed_data)
        
        temp_file.replace(target_path)
        return raw_hash, len(compressed_data)

    def read_chunk(self, chunk_hash: str) -> bytes:
        """Reads and decompress a chunk."""
        target_path = self.get_blob_path(chunk_hash)
        if not target_path.exists():
            raise FileNotFoundError(f"Chunk {chunk_hash} not found")
            
        with open(target_path, "rb") as f:
            compressed_data = f.read()
        return self.decompressor.decompress(compressed_data)

    def chunk_file(self, file_path: Path) -> Generator[bytes, None, None]:
        """Generates chunks from a file using FastCDC."""
        with open(file_path, "rb") as f:
            # Stats for Conductor: using 64KB - 256KB chunks
            for chunk in fastcdc(f, min_size=65536, avg_size=131072, max_size=262144):
                yield chunk.data
