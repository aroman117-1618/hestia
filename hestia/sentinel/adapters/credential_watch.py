"""
CredentialWatchAdapter — monitors credential files for unexpected process access.

Limitations (be honest about them):
- lsof polling catches only PERSISTENT access (file held open at poll time).
  Fire-and-forget reads (open → read → close in milliseconds) are NOT detected.
- Layer 0 defense (dedicated OS user + egress firewall) is the primary control;
  this adapter is a secondary, best-effort trip-wire.
- Future: eslogger (Apple EndpointSecurity CLI) for real-time file-open events.
  Requires root and Full Disk Access entitlement — not suitable for the current
  Hestia deployment model.

Zero-dependency constraint: stdlib only. No hestia.* imports outside sentinel/.
"""
import os
import subprocess

from hestia.sentinel.adapters.base import BaseAdapter


class CredentialWatchAdapter(BaseAdapter):
    """Poll lsof to detect unexpected process access to credential files.

    Preferred mechanism is eslogger (real-time, EndpointSecurity API), but that
    requires root + Full Disk Access.  lsof is the stdlib-compatible fallback.
    """

    SOURCE = "sentinel.credential_monitor"

    def __init__(
        self,
        watched_paths: list[str],
        process_allowlist: dict[str, list[str]],
    ) -> None:
        """Initialise the adapter.

        Args:
            watched_paths: Absolute paths to credential files to monitor.
            process_allowlist: Maps credential name to allowed process names.
                e.g. {"coinbase-credentials": ["bot_service", "python3"]}
        """
        self._watched_paths = watched_paths
        self._allowlist = process_allowlist

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def poll(self) -> list[dict]:
        """Run lsof, parse output, and return CRITICAL events for rogue access."""
        output = self._run_lsof()
        records = self._parse_lsof_output(output)
        events = []
        for rec in records:
            if not rec["allowed"]:
                events.append(
                    self.make_event(
                        source=self.SOURCE,
                        severity="CRITICAL",
                        event_type="credential_access",
                        summary=(
                            f"Unexpected process '{rec['process']}' (PID {rec['pid']}) "
                            f"accessing {rec['credential']} at {rec['path']}"
                        ),
                        details={
                            "process": rec["process"],
                            "pid": rec["pid"],
                            "path": rec["path"],
                            "credential": rec["credential"],
                        },
                    )
                )
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_lsof(self) -> str:
        """Run lsof against the watched paths and return its stdout as a string.

        Returns an empty string on error (lsof not installed, timeout, etc.).
        """
        try:
            result = subprocess.run(
                ["/usr/sbin/lsof"] + self._watched_paths,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def _parse_lsof_output(self, output: str) -> list[dict]:
        """Parse lsof stdout into access records.

        lsof column layout (space-separated):
            COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME

        The first line is always the header; we skip it.  The last whitespace-
        separated token on each subsequent line is the file path (NAME column).

        Args:
            output: Raw stdout from lsof.

        Returns:
            List of dicts with keys: process, pid, path, credential, allowed.
        """
        records = []
        lines = output.splitlines()
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) < 9:
                continue  # malformed / empty line
            process_name = parts[0]
            pid = parts[1]
            path = parts[-1]
            credential = self._match_credential(path)
            allowed_processes = self._allowlist.get(credential, [])
            allowed = process_name in allowed_processes
            records.append(
                {
                    "process": process_name,
                    "pid": pid,
                    "path": path,
                    "credential": credential,
                    "allowed": allowed,
                }
            )
        return records

    def _match_credential(self, path: str) -> str:
        """Map a file path to a human-readable credential name.

        Matching rules (checked in order):
            1. "coinbase" in path.lower() → "coinbase-credentials"
            2. "cloud_api_key" in path.lower() → "cloud_api_key"
            3. Fallback → basename of the path

        Args:
            path: Absolute file path from lsof output.

        Returns:
            Credential name string used as key in the allowlist.
        """
        lower = path.lower()
        if "coinbase" in lower:
            return "coinbase-credentials"
        if "cloud_api_key" in lower:
            return "cloud_api_key"
        return os.path.basename(path)
