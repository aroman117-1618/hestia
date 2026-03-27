"""
SentinelService — main service daemon for the Hestia Sentinel.

Runs all adapters on their configured poll intervals, stores events, dispatches
alerts, sends heartbeats, and performs a self-check on startup.

Zero-dependency constraint: stdlib only. No hestia.* imports outside sentinel/.
"""
import glob
import json
import os
import signal
import sys
import time
from typing import List, Optional, Tuple

from hestia.sentinel.alerter import SentinelAlerter
from hestia.sentinel.adapters.base import BaseAdapter
from hestia.sentinel.adapters.credential_watch import CredentialWatchAdapter
from hestia.sentinel.adapters.dns_monitor import DNSMonitorAdapter
from hestia.sentinel.adapters.file_integrity import FileIntegrityAdapter
from hestia.sentinel.baseline import BaselineManager
from hestia.sentinel.config import SentinelConfig
from hestia.sentinel.self_check import SelfCheck
from hestia.sentinel.store import SentinelStore

# Tick interval in seconds — inner loop sleep.
_TICK = 5


def _find_site_packages(repo_root: str) -> Optional[str]:
    """Return the site-packages path inside the repo .venv, or None."""
    pattern = os.path.join(repo_root, ".venv", "lib", "python*", "site-packages")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def _load_watched_paths(config_dir: str) -> List[str]:
    """Read credential file paths to monitor from config/known-credential-paths.json.

    Falls back to a hardcoded list of likely credential files in the repo data/
    directory when the config file is absent.
    """
    config_path = os.path.join(config_dir, "known-credential-paths.json")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            return json.load(f).get("paths", [])
    # Fallback: watch encrypted credential files in data/
    data_dir = os.path.join(os.path.dirname(config_dir), "data")
    paths = []
    for entry in os.scandir(data_dir) if os.path.isdir(data_dir) else []:
        if entry.is_file() and (
            "coinbase" in entry.name.lower() or "cloud_api_key" in entry.name.lower()
        ):
            paths.append(entry.path)
    return paths


class SentinelService:
    """Orchestrates all Sentinel adapters and the main polling loop."""

    def __init__(self, repo_root: str) -> None:
        self._repo_root = repo_root
        self._running = False

        config_dir = os.path.join(repo_root, "config")
        db_path = os.path.join(repo_root, "data", "sentinel_events.db")

        self._config = SentinelConfig(config_dir)
        self._store = SentinelStore(db_path)

        ntfy_topic = self._config._master.get("ntfy_topic", "hestia-sentinel")
        self._alerter = SentinelAlerter(
            ntfy_topic=ntfy_topic,
            heartbeat_url=self._config.heartbeat_url,
            learning_mode=self._config.learning_mode,
        )

        self._adapters: List[Tuple[str, BaseAdapter, int]] = self._setup_adapters()

        # Track last poll time per adapter name.
        self._last_poll: dict = {name: 0.0 for name, _, _ in self._adapters}
        self._last_heartbeat: float = 0.0

        # Register shutdown signal handlers.
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_adapters(self) -> List[Tuple[str, BaseAdapter, int]]:
        """Return a list of (name, adapter, interval_seconds) tuples."""
        adapters: List[Tuple[str, BaseAdapter, int]] = []

        # --- File integrity ---
        site_packages = _find_site_packages(self._repo_root)
        if site_packages:
            baseline_path = os.path.join(self._repo_root, "data", "pth_baseline.json")
            baseline_mgr = BaselineManager(baseline_path)

            # Bootstrap the baseline on first run.
            if not os.path.isfile(baseline_path):
                print(
                    f"[sentinel] Bootstrapping .pth baseline from {site_packages}",
                    flush=True,
                )
                baseline_mgr.create_baseline(site_packages)

            adapters.append((
                "file_integrity",
                FileIntegrityAdapter(site_packages, baseline_mgr),
                self._config.file_integrity_interval,
            ))
        else:
            print(
                "[sentinel] WARNING: .venv site-packages not found — file_integrity adapter disabled",
                flush=True,
            )

        # --- Credential watch ---
        config_dir = os.path.join(self._repo_root, "config")
        watched_paths = _load_watched_paths(config_dir)
        process_allowlist: dict = self._config._process_allowlist.get(
            "credential_access", {}
        )
        adapters.append((
            "credential_watch",
            CredentialWatchAdapter(watched_paths, process_allowlist),
            self._config.credential_watch_interval,
        ))

        # --- DNS monitor ---
        if self._config.dns_monitor_enabled:
            adapters.append((
                "dns_monitor",
                DNSMonitorAdapter(self._config.is_domain_allowed),
                60,  # poll every minute — reads last-1m of log
            ))

        return adapters

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        print(f"[sentinel] Received signal {signum} — shutting down gracefully.", flush=True)
        self._running = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Sentinel service main loop."""
        self._store.initialize()

        # Self-check on startup.
        self._run_self_check()

        adapter_names = [name for name, _, _ in self._adapters]
        print(
            f"[sentinel] Starting — "
            f"learning_mode={self._config.learning_mode}, "
            f"containment={self._config.containment_enabled}, "
            f"adapters={adapter_names}",
            flush=True,
        )

        self._running = True
        while self._running:
            now = time.time()

            for name, adapter, interval in self._adapters:
                if now - self._last_poll[name] >= interval:
                    self._poll_adapter(name, adapter)
                    self._last_poll[name] = now

            # Heartbeat
            if (
                self._config.heartbeat_url
                and now - self._last_heartbeat >= self._config.heartbeat_interval
            ):
                self._alerter.send_heartbeat()
                self._last_heartbeat = now

            time.sleep(_TICK)

        print("[sentinel] Shutdown complete.", flush=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _poll_adapter(self, name: str, adapter: BaseAdapter) -> None:
        """Poll one adapter, store events, and dispatch alerts."""
        try:
            events = adapter.poll()
        except Exception as exc:
            print(f"[sentinel] ERROR polling {name}: {exc}", flush=True)
            return

        for event in events:
            try:
                self._store.insert_event(
                    event_id=event["event_id"],
                    source=event["source"],
                    severity=event["severity"],
                    event_type=event["event_type"],
                    summary=event["summary"],
                    details=json.dumps(event.get("details", {})),
                    action_taken=event.get("action_taken"),
                )
            except Exception as exc:
                print(f"[sentinel] ERROR storing event from {name}: {exc}", flush=True)

            try:
                self._alerter.alert(event)
            except Exception as exc:
                print(f"[sentinel] ERROR alerting for event from {name}: {exc}", flush=True)

    def _run_self_check(self) -> None:
        """Verify Sentinel module integrity against a stored manifest, if present."""
        sentinel_dir = os.path.dirname(__file__)
        manifest_path = os.path.join(sentinel_dir, "sentinel_manifest.json")

        if not os.path.isfile(manifest_path):
            print("[sentinel] No self-check manifest found — skipping integrity check.", flush=True)
            return

        try:
            manifest = SelfCheck.load_manifest(manifest_path)
            ok = SelfCheck.verify(manifest)
            if ok:
                print("[sentinel] Self-check PASSED.", flush=True)
            else:
                print("[sentinel] CRITICAL: Self-check FAILED — sentinel files may have been tampered with!", flush=True)
        except Exception as exc:
            print(f"[sentinel] WARNING: Self-check error: {exc}", flush=True)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    """CLI entry point.  Accepts an optional repo_root positional argument."""
    if len(sys.argv) > 1:
        repo_root = sys.argv[1]
    else:
        # Default: two levels above this file (hestia/sentinel/service.py → hestia/)
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    repo_root = os.path.abspath(repo_root)
    print(f"[sentinel] repo_root={repo_root}", flush=True)

    service = SentinelService(repo_root)

    print(
        f"[sentinel] Configuration — "
        f"learning_mode={service._config.learning_mode}, "
        f"containment={service._config.containment_enabled}",
        flush=True,
    )
    adapter_names = [name for name, _, _ in service._adapters]
    print(f"[sentinel] Adapters: {adapter_names}", flush=True)

    service.run()


if __name__ == "__main__":
    main()
