"""SentinelConfig — loads and exposes sentinel configuration from JSON files.

No hestia.* imports. No third-party dependencies. stdlib only.
"""
import json
import os


class SentinelConfig:
    """Loads sentinel config, DNS allowlist, and process allowlist from a directory."""

    def __init__(self, config_dir: str) -> None:
        self._config_dir = config_dir
        self._master: dict = {}
        self._dns_domains: list[str] = []
        self._process_allowlist: dict = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-read all config files from disk."""
        self._load()

    # Master config properties

    @property
    def containment_enabled(self) -> bool:
        return bool(self._master.get("containment_enabled", False))

    @property
    def learning_mode(self) -> bool:
        return bool(self._master.get("learning_mode", True))

    @property
    def file_integrity_interval(self) -> int:
        return int(self._master.get("file_integrity_interval_seconds", 300))

    @property
    def credential_watch_interval(self) -> int:
        return int(self._master.get("credential_watch_interval_seconds", 30))

    @property
    def dns_monitor_enabled(self) -> bool:
        return bool(self._master.get("dns_monitor_enabled", True))

    @property
    def heartbeat_url(self) -> str:
        return str(self._master.get("heartbeat_url", ""))

    @property
    def heartbeat_interval(self) -> int:
        return int(self._master.get("heartbeat_interval_seconds", 300))

    @property
    def daily_digest_hour(self) -> int:
        return int(self._master.get("daily_digest_hour", 8))

    @property
    def max_crashes(self) -> int:
        return int(self._master.get("max_crashes_before_shutdown", 3))

    @property
    def crash_window(self) -> int:
        return int(self._master.get("crash_window_seconds", 300))

    # ------------------------------------------------------------------
    # Domain / process checks
    # ------------------------------------------------------------------

    def is_domain_allowed(self, domain: str) -> bool:
        """Return True if *domain* matches any entry in the DNS allowlist.

        Wildcard rules:
          - ``*.apple.com``  matches ``www.apple.com`` and ``apple.com`` itself.
          - A wildcard rule does NOT match if the domain merely *ends with* the
            suffix string — the match is anchored so that
            ``evil.apple.com.attacker.net`` is rejected.
        """
        domain = domain.lower().rstrip(".")
        for entry in self._dns_domains:
            entry = entry.lower()
            if entry.startswith("*."):
                base = entry[2:]  # e.g. "apple.com"
                # Match the apex itself OR a direct subdomain
                if domain == base or domain.endswith("." + base):
                    return True
            else:
                if domain == entry:
                    return True
        return False

    def is_process_allowed(self, credential_name: str, process_name: str) -> bool:
        """Return True if *process_name* is in the allowlist for *credential_name*."""
        allowed = self._process_allowlist.get("credential_access", {}).get(
            credential_name, None
        )
        if allowed is None:
            return False
        return process_name in allowed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._master = self._read_json("sentinel.json")
        dns_data = self._read_json("sentinel-dns-allowlist.json")
        self._dns_domains = dns_data.get("domains", [])
        self._process_allowlist = self._read_json("sentinel-process-allowlist.json")

    def _read_json(self, filename: str) -> dict:
        path = os.path.join(self._config_dir, filename)
        with open(path, "r") as f:
            return json.load(f)
