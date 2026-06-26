import hashlib
from typing import BinaryIO

class HashingService:
    @staticmethod
    def calculate_sha256(file_obj: BinaryIO) -> str:
        """
        Calculates SHA-256 hash of a binary file stream in 1MB chunks.
        Resets the file stream pointer to the beginning after hashing.
        """
        sha256 = hashlib.sha256()
        # Reset file pointer to beginning before read
        file_obj.seek(0)
        while chunk := file_obj.read(1024 * 1024):  # Read in 1MB chunks
            sha256.update(chunk)
        # Reset file pointer back to beginning so downstream readers can consume it
        file_obj.seek(0)
        return sha256.hexdigest()
