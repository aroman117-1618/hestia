"""
SelfCheck — SHA-256 manifest generation and verification for self-integrity.

Zero-dependency constraint: stdlib only (hashlib, json).
"""

import hashlib
import json


class SelfCheck:
    """Generates and verifies SHA-256 manifests of file contents."""

    CHUNK_SIZE = 8192

    @staticmethod
    def hash_file(path: str) -> str:
        """Return the SHA-256 hex digest of a file, read in 8192-byte chunks."""
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(SelfCheck.CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def generate_manifest(file_paths: list[str]) -> dict[str, str]:
        """Return a path -> SHA-256 hex digest mapping, sorted by path."""
        return {path: SelfCheck.hash_file(path) for path in sorted(file_paths)}

    @staticmethod
    def verify(manifest: dict[str, str]) -> bool:
        """Return False if any file is missing or its hash doesn't match."""
        for path, expected_hash in manifest.items():
            try:
                actual_hash = SelfCheck.hash_file(path)
            except (OSError, FileNotFoundError):
                return False
            if actual_hash != expected_hash:
                return False
        return True

    @staticmethod
    def save_manifest(manifest: dict[str, str], path: str) -> None:
        """Write manifest to a JSON file."""
        with open(path, "w") as f:
            json.dump(manifest, f, indent=2)

    @staticmethod
    def load_manifest(path: str) -> dict[str, str]:
        """Read manifest from a JSON file."""
        with open(path) as f:
            return json.load(f)
