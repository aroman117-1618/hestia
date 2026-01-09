"""
Log viewer CLI for Hestia.

Provides filtering, tailing, and display of structured logs.

Usage:
    python -m hestia.logging.viewer [options]

Options:
    --tail N              Show last N entries (default: 20)
    --follow              Continuously watch for new entries
    --filter KEY=VALUE    Filter by field (can be repeated)
    --severity LEVEL      Minimum severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    --component NAME      Filter by component
    --event-type TYPE     Filter by event type
    --request-id ID       Filter by request ID
    --after DATETIME      Show entries after this time (ISO format or relative like "1h", "30m")
    --before DATETIME     Show entries before this time
    --json                Output raw JSON
    --audit               View audit log instead of general log
    --stats               Show log statistics
"""

import argparse
import json
import sys
import time
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Any
from dataclasses import dataclass


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Severity colors
    DEBUG = "\033[36m"      # Cyan
    INFO = "\033[32m"       # Green
    WARNING = "\033[33m"    # Yellow
    ERROR = "\033[31m"      # Red
    CRITICAL = "\033[35m"   # Magenta

    # Component colors
    COMPONENT = "\033[34m"  # Blue
    TIME = "\033[90m"       # Gray
    REQUEST_ID = "\033[33m" # Yellow


SEVERITY_COLORS = {
    "DEBUG": Colors.DEBUG,
    "INFO": Colors.INFO,
    "WARNING": Colors.WARNING,
    "ERROR": Colors.ERROR,
    "CRITICAL": Colors.CRITICAL,
    "LOW": Colors.DEBUG,
    "MEDIUM": Colors.INFO,
    "HIGH": Colors.WARNING,
}


@dataclass
class LogFilter:
    """Filter criteria for log entries."""
    severity: Optional[str] = None
    component: Optional[str] = None
    event_type: Optional[str] = None
    request_id: Optional[str] = None
    after: Optional[datetime] = None
    before: Optional[datetime] = None
    custom_filters: Optional[Dict[str, str]] = None

    def matches(self, entry: Dict[str, Any]) -> bool:
        """Check if entry matches all filter criteria."""
        # Severity filter (minimum level)
        if self.severity:
            severity_order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL",
                            "LOW", "MEDIUM", "HIGH"]
            entry_severity = entry.get("severity", "INFO")
            if entry_severity not in severity_order:
                entry_severity = "INFO"
            if severity_order.index(entry_severity) < severity_order.index(self.severity):
                return False

        # Component filter
        if self.component and entry.get("component") != self.component:
            return False

        # Event type filter
        if self.event_type and entry.get("event_type") != self.event_type:
            return False

        # Request ID filter
        if self.request_id and entry.get("request_id") != self.request_id:
            return False

        # Time filters
        if self.after or self.before:
            timestamp_str = entry.get("timestamp", "")
            try:
                entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if self.after and entry_time < self.after:
                    return False
                if self.before and entry_time > self.before:
                    return False
            except ValueError:
                pass

        # Custom filters
        if self.custom_filters:
            for key, value in self.custom_filters.items():
                # Support nested keys with dot notation
                entry_value = self._get_nested(entry, key)
                if str(entry_value) != value:
                    return False

        return True

    def _get_nested(self, d: Dict, key: str) -> Any:
        """Get nested dictionary value using dot notation."""
        keys = key.split('.')
        value = d
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value


def parse_time(time_str: str) -> datetime:
    """Parse time string, supporting ISO format and relative times."""
    # Try relative time first (1h, 30m, 2d, etc.)
    relative_match = re.match(r'^(\d+)([smhd])$', time_str.lower())
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        now = datetime.now(timezone.utc)
        deltas = {
            's': timedelta(seconds=amount),
            'm': timedelta(minutes=amount),
            'h': timedelta(hours=amount),
            'd': timedelta(days=amount),
        }
        return now - deltas[unit]

    # Try ISO format
    try:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}")


def read_log_entries(
    log_path: Path,
    limit: int = 0,
    log_filter: Optional[LogFilter] = None
) -> List[Dict[str, Any]]:
    """Read and filter log entries from file."""
    if not log_path.exists():
        return []

    entries = []

    with open(log_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                if log_filter is None or log_filter.matches(entry):
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    # Return last N entries if limit specified
    if limit > 0:
        return entries[-limit:]
    return entries


def tail_log(
    log_path: Path,
    log_filter: Optional[LogFilter] = None,
    output_json: bool = False
) -> Iterator[Dict[str, Any]]:
    """Tail log file, yielding new entries."""
    if not log_path.exists():
        log_path.touch()

    with open(log_path, 'r') as f:
        # Go to end of file
        f.seek(0, 2)

        while True:
            line = f.readline()
            if line:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if log_filter is None or log_filter.matches(entry):
                            yield entry
                    except json.JSONDecodeError:
                        continue
            else:
                time.sleep(0.5)


def format_entry(entry: Dict[str, Any], use_colors: bool = True) -> str:
    """Format log entry for display."""
    timestamp = entry.get("timestamp", "")
    severity = entry.get("severity", "INFO")
    component = entry.get("component", "system")
    event_type = entry.get("event_type", "log")
    message = entry.get("message", "")
    request_id = entry.get("request_id", "")
    data = entry.get("data", {})
    duration_ms = entry.get("duration_ms")

    # Format timestamp (show only time if today)
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if dt.date() == datetime.now(timezone.utc).date():
            time_str = dt.strftime("%H:%M:%S")
        else:
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        time_str = timestamp[:19]

    if use_colors:
        sev_color = SEVERITY_COLORS.get(severity, Colors.INFO)
        parts = [
            f"{Colors.TIME}{time_str}{Colors.RESET}",
            f"{sev_color}{severity:8}{Colors.RESET}",
            f"{Colors.COMPONENT}[{component}]{Colors.RESET}",
        ]

        if request_id:
            parts.append(f"{Colors.REQUEST_ID}{request_id}{Colors.RESET}")

        parts.append(message)

        if duration_ms is not None:
            parts.append(f"{Colors.DIM}({duration_ms:.1f}ms){Colors.RESET}")

        line = " ".join(parts)

        # Add data if present
        if data:
            data_str = json.dumps(data, separators=(',', ':'))
            if len(data_str) > 100:
                data_str = data_str[:100] + "..."
            line += f"\n  {Colors.DIM}{data_str}{Colors.RESET}"

    else:
        parts = [time_str, severity, f"[{component}]"]
        if request_id:
            parts.append(request_id)
        parts.append(message)
        if duration_ms is not None:
            parts.append(f"({duration_ms:.1f}ms)")

        line = " ".join(parts)

        if data:
            data_str = json.dumps(data, separators=(',', ':'))
            if len(data_str) > 100:
                data_str = data_str[:100] + "..."
            line += f"\n  {data_str}"

    return line


def show_stats(entries: List[Dict[str, Any]]) -> None:
    """Display log statistics."""
    if not entries:
        print("No entries found.")
        return

    # Count by severity
    severity_counts: Dict[str, int] = {}
    component_counts: Dict[str, int] = {}
    event_counts: Dict[str, int] = {}

    for entry in entries:
        severity = entry.get("severity", "UNKNOWN")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

        component = entry.get("component", "unknown")
        component_counts[component] = component_counts.get(component, 0) + 1

        event_type = entry.get("event_type", "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    print(f"\n{Colors.BOLD}Log Statistics{Colors.RESET}")
    print(f"Total entries: {len(entries)}")

    # Time range
    try:
        first_time = datetime.fromisoformat(entries[0].get("timestamp", "").replace('Z', '+00:00'))
        last_time = datetime.fromisoformat(entries[-1].get("timestamp", "").replace('Z', '+00:00'))
        print(f"Time range: {first_time.strftime('%Y-%m-%d %H:%M')} to {last_time.strftime('%Y-%m-%d %H:%M')}")
    except (ValueError, IndexError):
        pass

    print(f"\n{Colors.BOLD}By Severity:{Colors.RESET}")
    for severity in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "LOW", "MEDIUM", "HIGH"]:
        count = severity_counts.get(severity, 0)
        if count > 0:
            color = SEVERITY_COLORS.get(severity, Colors.INFO)
            print(f"  {color}{severity:12}{Colors.RESET}: {count}")

    print(f"\n{Colors.BOLD}By Component:{Colors.RESET}")
    for component, count in sorted(component_counts.items(), key=lambda x: -x[1]):
        print(f"  {Colors.COMPONENT}{component:16}{Colors.RESET}: {count}")

    print(f"\n{Colors.BOLD}By Event Type:{Colors.RESET}")
    for event_type, count in sorted(event_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {event_type:24}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Hestia Log Viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--tail", "-n", type=int, default=20,
        help="Show last N entries (default: 20)"
    )
    parser.add_argument(
        "--follow", "-f", action="store_true",
        help="Continuously watch for new entries"
    )
    parser.add_argument(
        "--filter", "-F", action="append", dest="filters",
        help="Filter by field KEY=VALUE (can be repeated)"
    )
    parser.add_argument(
        "--severity", "-s",
        help="Minimum severity level"
    )
    parser.add_argument(
        "--component", "-c",
        help="Filter by component"
    )
    parser.add_argument(
        "--event-type", "-e",
        help="Filter by event type"
    )
    parser.add_argument(
        "--request-id", "-r",
        help="Filter by request ID"
    )
    parser.add_argument(
        "--after", "-a",
        help="Show entries after this time (ISO format or relative like '1h', '30m')"
    )
    parser.add_argument(
        "--before", "-b",
        help="Show entries before this time"
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output raw JSON"
    )
    parser.add_argument(
        "--audit", action="store_true",
        help="View audit log instead of general log"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show log statistics"
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colored output"
    )
    parser.add_argument(
        "--log-dir",
        help="Log directory (default: ~/hestia/logs)"
    )

    args = parser.parse_args()

    # Determine log path
    log_dir = Path(args.log_dir) if args.log_dir else Path.home() / "hestia" / "logs"
    log_file = "audit.log" if args.audit else "hestia.log"
    log_path = log_dir / log_file

    # Build filter
    custom_filters = {}
    if args.filters:
        for f in args.filters:
            if '=' in f:
                key, value = f.split('=', 1)
                custom_filters[key] = value

    log_filter = LogFilter(
        severity=args.severity.upper() if args.severity else None,
        component=args.component,
        event_type=args.event_type,
        request_id=args.request_id,
        after=parse_time(args.after) if args.after else None,
        before=parse_time(args.before) if args.before else None,
        custom_filters=custom_filters if custom_filters else None
    )

    use_colors = not args.no_color and sys.stdout.isatty()

    # Stats mode
    if args.stats:
        entries = read_log_entries(log_path, limit=0, log_filter=log_filter)
        show_stats(entries)
        return

    # Follow mode
    if args.follow:
        print(f"Following {log_path}... (Ctrl+C to stop)")
        try:
            for entry in tail_log(log_path, log_filter):
                if args.json:
                    print(json.dumps(entry))
                else:
                    print(format_entry(entry, use_colors))
        except KeyboardInterrupt:
            print("\nStopped.")
        return

    # Normal mode - read last N entries
    entries = read_log_entries(log_path, limit=args.tail, log_filter=log_filter)

    if not entries:
        print(f"No log entries found in {log_path}")
        return

    for entry in entries:
        if args.json:
            print(json.dumps(entry))
        else:
            print(format_entry(entry, use_colors))


if __name__ == "__main__":
    main()
