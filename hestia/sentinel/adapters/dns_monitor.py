"""DNS Monitor Adapter — supplementary audit trail for Sentinel.

Reads mDNSResponder logs via the macOS ``log`` command and emits events for
unknown domains and DNS query bursts.

Limitations (by design — egress firewall is the primary defense):
- Bypassed by direct-IP connections (no DNS lookup).
- Bypassed by DNS-over-HTTPS (DoH) — queries go to HTTPS, not mDNSResponder.
- Does not detect exfil via allowed-domain subdomains (e.g. allowed CDN bucket names).
- Log output depends on macOS log streaming permissions; may be incomplete under
  strict privacy settings.

This adapter is a secondary, belt-and-suspenders signal only. Never treat it as
a complete or reliable block on malicious egress.

Stdlib only. No hestia.* imports outside hestia/sentinel/.
"""
import re
import subprocess
import time
from typing import Callable

from hestia.sentinel.adapters.base import BaseAdapter


class DNSMonitorAdapter(BaseAdapter):
    """Poll mDNSResponder logs for unknown or bursting DNS queries.

    Parameters
    ----------
    is_domain_allowed:
        Callable that returns True if a domain is on the allow-list.
    """

    SOURCE = "sentinel.dns_monitor"
    BURST_THRESHOLD = 3
    BURST_WINDOW_SECONDS = 60

    # Extract the queried domain from compact mDNSResponder log lines.
    # mDNSResponder emits lines like: "... q=example.com. IN ..."
    # The trailing dot marks the DNS root; we strip it in _extract_domains.
    DOMAIN_RE = re.compile(r'q=([a-zA-Z0-9._-]+)\.\s')

    def __init__(self, is_domain_allowed: Callable[[str], bool]) -> None:
        self._is_domain_allowed = is_domain_allowed
        self._recent_unknowns: list[tuple[float, str]] = []  # (timestamp, domain)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def poll(self) -> list[dict]:
        """Read DNS logs, extract queried domains, and classify them.

        Returns a (possibly empty) list of Sentinel event dicts.
        """
        lines = self._read_dns_log()
        domains = self._extract_domains(lines)
        return self._classify_domains(sorted(domains))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_dns_log(self) -> list[str]:
        """Run ``log show`` and return output lines.

        Returns an empty list on any error so that a log-read failure is
        non-fatal — the adapter simply emits no events for that poll cycle.
        """
        try:
            result = subprocess.run(
                [
                    "/usr/bin/log",
                    "show",
                    "--last", "1m",
                    "--predicate", 'subsystem == "com.apple.mDNSResponder"',
                    "--style", "compact",
                ],
                capture_output=True,
                timeout=15,
            )
            return result.stdout.decode("utf-8", errors="replace").splitlines()
        except Exception:
            return []

    def _extract_domains(self, log_lines: list[str]) -> set[str]:
        """Parse mDNSResponder log lines and return the set of queried domains.

        - Lowercases all domains.
        - Strips trailing dots (DNS root notation).
        - Filters out single-label names (no dot = not a routable domain).
        """
        domains: set[str] = set()
        for line in log_lines:
            match = self.DOMAIN_RE.search(line)
            if match:
                domain = match.group(1).lower()
                if "." in domain:
                    domains.add(domain)
        return domains

    def _classify_domains(self, domains: list[str]) -> list[dict]:
        """Classify each domain and emit LOW / HIGH events as appropriate.

        Side-effects:
        - Unknown domains are appended to ``_recent_unknowns``.
        - Entries older than ``BURST_WINDOW_SECONDS`` are pruned each call.
        - A HIGH ``dns_burst`` event is emitted when
          ``len(_recent_unknowns) >= BURST_THRESHOLD`` after appending.
        """
        events: list[dict] = []
        now = time.time()

        for domain in domains:
            if not self._is_domain_allowed(domain):
                self._recent_unknowns.append((now, domain))
                events.append(
                    self.make_event(
                        source=self.SOURCE,
                        severity="LOW",
                        event_type="dns_unknown_domain",
                        summary=f"Unknown DNS query: {domain}",
                        details={"domain": domain},
                    )
                )

        # Prune entries outside the burst window
        cutoff = now - self.BURST_WINDOW_SECONDS
        self._recent_unknowns = [
            (ts, d) for ts, d in self._recent_unknowns if ts >= cutoff
        ]

        # Emit burst alert if threshold is met or exceeded
        if len(self._recent_unknowns) >= self.BURST_THRESHOLD:
            burst_domains = [d for _, d in self._recent_unknowns]
            events.append(
                self.make_event(
                    source=self.SOURCE,
                    severity="HIGH",
                    event_type="dns_burst",
                    summary=(
                        f"DNS query burst: {len(self._recent_unknowns)} unknown "
                        f"domains in {self.BURST_WINDOW_SECONDS}s window"
                    ),
                    details={"domains": burst_domains, "count": len(self._recent_unknowns)},
                )
            )

        return events
