"""BaselineManager — snapshot and diff .pth files in a site-packages directory.

Stdlib only. No hestia.* imports.
"""
import hashlib
import json
import os


def _hash_file(path: str) -> str:
    """Return the SHA-256 hex digest of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_pth_hashes(site_packages_path: str) -> dict[str, str]:
    """Return {filename: sha256_hex} for every .pth file in site_packages_path."""
    result: dict[str, str] = {}
    for entry in os.scandir(site_packages_path):
        if entry.is_file() and entry.name.endswith(".pth"):
            result[entry.name] = _hash_file(entry.path)
    return result


class BaselineManager:
    """Manages a JSON baseline of .pth file hashes for a site-packages directory."""

    def __init__(self, baseline_path: str) -> None:
        self._baseline_path = baseline_path

    def create_baseline(self, site_packages_path: str) -> None:
        """Snapshot all .pth file hashes and write them to the baseline JSON file."""
        hashes = _collect_pth_hashes(site_packages_path)
        with open(self._baseline_path, "w") as f:
            json.dump(hashes, f, indent=2)

    def diff(self, site_packages_path: str) -> list[dict]:
        """Compare current .pth files against the baseline.

        Returns a list of change dicts, each with:
          - type: "new_pth" or "modified_pth"
          - path: absolute path to the file
          - hash: current sha256 hex digest
          - baseline_hash: previous hash (only present for "modified_pth")
        """
        with open(self._baseline_path) as f:
            baseline: dict[str, str] = json.load(f)

        current = _collect_pth_hashes(site_packages_path)
        changes: list[dict] = []

        for name, current_hash in current.items():
            abs_path = os.path.join(site_packages_path, name)
            if name not in baseline:
                changes.append({
                    "type": "new_pth",
                    "path": abs_path,
                    "hash": current_hash,
                })
            elif current_hash != baseline[name]:
                changes.append({
                    "type": "modified_pth",
                    "path": abs_path,
                    "hash": current_hash,
                    "baseline_hash": baseline[name],
                })

        return changes
