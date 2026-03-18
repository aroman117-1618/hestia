#!/usr/bin/env python3
"""
Historical Apple data backfill — goes directly to CLI tools for full history.

The InboxManager only fetches recent items (7-day window). For backfill we
bypass it and query the Swift CLI tools directly with a 6-month window, then
store chunks via MemoryManager with dedup.

Usage:
  source .venv/bin/activate
  python scripts/backfill-apple-data.py --phase calendar [--days-back 180]
  python scripts/backfill-apple-data.py --phase reminders [--days-back 180]
  python scripts/backfill-apple-data.py --phase email [--days-back 180]
"""

import argparse
import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

CLI_DIR = Path.home() / ".hestia" / "bin"
DEFAULT_USER_ID = "default"

# Quality filters
SKIP_CALENDAR_PATTERNS = [
    re.compile(r"^(Lunch|Break|Standup|Daily|1:1)$", re.IGNORECASE),
]

SKIP_REMINDER_COMPLETED_DAYS = 30  # Skip completed reminders older than 30 days


async def backfill_calendar(days_back: int, verbose: bool) -> None:
    """Backfill calendar events from the CLI tool."""
    from hestia.memory import get_memory_manager
    from hestia.memory.models import (
        ChunkType, MemoryScope, MemorySource, ChunkMetadata, ChunkTags,
    )

    cli = CLI_DIR / "hestia-calendar-cli"
    if not cli.exists():
        print(f"CLI not found: {cli}")
        return

    after = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    before = datetime.now().strftime("%Y-%m-%d")

    print(f"Querying calendar: {after} to {before}")
    result = subprocess.run(
        [str(cli), "list-events", "--after", after, "--before", before],
        capture_output=True, text=True, timeout=30,
    )
    data = json.loads(result.stdout)
    if not data.get("success"):
        print(f"CLI error: {data.get('error')}")
        return

    events = data.get("data", {}).get("events", [])
    print(f"Found {len(events)} calendar events")

    # Quality gate
    filtered = []
    skipped_routine = 0
    skipped_allday = 0
    for event in events:
        title = event.get("title", "")
        if event.get("isAllDay", False):
            skipped_allday += 1
            continue
        if any(p.match(title) for p in SKIP_CALENDAR_PATTERNS):
            skipped_routine += 1
            continue
        filtered.append(event)

    print(f"After quality gate: {len(filtered)} kept, {skipped_routine} routine skipped, {skipped_allday} all-day skipped")

    memory_mgr = await get_memory_manager()
    db = memory_mgr.database
    stored = 0
    deduped = 0

    for event in filtered:
        event_id = event.get("id", uuid4().hex[:12])
        source_id = f"calendar:{event_id}"

        # Dedup check
        if await db.check_duplicate("calendar", source_id):
            deduped += 1
            continue

        # Build content
        title = event.get("title", "Untitled")
        start = event.get("start", "")[:16]
        end = event.get("end", "")[:16]
        location = event.get("location", "")
        notes = event.get("notes", "")
        calendar_name = event.get("calendar", "")
        attendees = event.get("attendees", [])

        content_parts = [f"Calendar: {title}"]
        if start:
            content_parts.append(f"When: {start} - {end}")
        if location:
            content_parts.append(f"Where: {location}")
        if calendar_name:
            content_parts.append(f"Calendar: {calendar_name}")
        if attendees:
            content_parts.append(f"With: {', '.join(a.get('name', a.get('email', '?')) for a in attendees[:5])}")
        if notes:
            content_parts.append(f"Notes: {notes[:500]}")

        content = "\n".join(content_parts)
        chunk_id = f"chunk-{uuid4().hex[:12]}"

        # Extract people from attendees for entity resolution
        people = [a.get("name", "") for a in attendees if a.get("name")]

        try:
            timestamp = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else datetime.now(timezone.utc)
        except ValueError:
            timestamp = datetime.now(timezone.utc)

        from hestia.memory.models import ChunkMetadata, ChunkTags
        chunk_obj = await memory_mgr.store(
            content=content,
            chunk_type=ChunkType.SOURCE_STRUCTURED,
            tags=ChunkTags(topics=[calendar_name] if calendar_name else [], people=people),
            metadata=ChunkMetadata(source=MemorySource.CALENDAR.value, confidence=0.5, token_count=len(content.split()), is_sensitive=False),
            session_id=f"backfill-calendar-{datetime.now().strftime('%Y%m%d')}",
            auto_tag=False,
            scope=MemoryScope.LONG_TERM,
        )
        await db.record_dedup("calendar", source_id, chunk_obj.id, f"backfill-{datetime.now().strftime('%Y%m%d')}")
        stored += 1

        if verbose:
            print(f"  + {start[:10]} {title}")

    print(f"\nStored: {stored}, Deduped: {deduped}")


async def backfill_reminders(days_back: int, verbose: bool) -> None:
    """Backfill reminders from the CLI tool."""
    from hestia.memory import get_memory_manager
    from hestia.memory.models import (
        ChunkType, MemoryScope, MemorySource,
    )

    cli = CLI_DIR / "hestia-reminders-cli"
    if not cli.exists():
        print(f"CLI not found: {cli}")
        return

    print("Querying reminders (all lists)...")
    result = subprocess.run(
        [str(cli), "list-reminders"],
        capture_output=True, text=True, timeout=30,
    )
    data = json.loads(result.stdout)
    if not data.get("success"):
        print(f"CLI error: {data.get('error')}")
        return

    reminders = data.get("data", {}).get("reminders", [])
    print(f"Found {len(reminders)} reminders")

    # Also get completed
    result2 = subprocess.run(
        [str(cli), "list-reminders", "--completed"],
        capture_output=True, text=True, timeout=30,
    )
    data2 = json.loads(result2.stdout)
    if data2.get("success"):
        completed = data2.get("data", {}).get("reminders", [])
        print(f"Found {len(completed)} completed reminders")
        reminders.extend(completed)

    # Quality gate: skip completed > 30 days old
    cutoff = datetime.now() - timedelta(days=SKIP_REMINDER_COMPLETED_DAYS)
    filtered = []
    skipped = 0
    for r in reminders:
        if r.get("isCompleted"):
            completed_date = r.get("completedDate", "")
            if completed_date:
                try:
                    cd = datetime.fromisoformat(completed_date.replace("Z", "+00:00"))
                    if cd.replace(tzinfo=None) < cutoff:
                        skipped += 1
                        continue
                except ValueError:
                    pass
        # Skip empty reminders
        if not r.get("title", "").strip():
            skipped += 1
            continue
        filtered.append(r)

    print(f"After quality gate: {len(filtered)} kept, {skipped} skipped")

    memory_mgr = await get_memory_manager()
    db = memory_mgr.database
    stored = 0
    deduped = 0

    for r in filtered:
        reminder_id = r.get("id", uuid4().hex[:12])
        source_id = f"reminders:{reminder_id}"

        if await db.check_duplicate("reminders", source_id):
            deduped += 1
            continue

        title = r.get("title", "")
        notes = r.get("notes", "")
        due = r.get("dueDate", "")
        list_name = r.get("list", "")
        is_completed = r.get("isCompleted", False)
        priority = r.get("priority", 0)

        content_parts = [f"Reminder: {title}"]
        if due:
            content_parts.append(f"Due: {due[:16]}")
        if list_name:
            content_parts.append(f"List: {list_name}")
        if notes:
            content_parts.append(f"Notes: {notes[:500]}")
        if is_completed:
            content_parts.append("Status: Completed")
        if priority > 0:
            content_parts.append(f"Priority: {'High' if priority >= 5 else 'Medium'}")

        content = "\n".join(content_parts)
        chunk_id = f"chunk-{uuid4().hex[:12]}"

        try:
            timestamp = datetime.fromisoformat(due.replace("Z", "+00:00")) if due else datetime.now(timezone.utc)
        except ValueError:
            timestamp = datetime.now(timezone.utc)

        from hestia.memory.models import ChunkMetadata, ChunkTags
        chunk_obj = await memory_mgr.store(
            content=content,
            chunk_type=ChunkType.SOURCE_STRUCTURED,
            tags=ChunkTags(topics=[list_name] if list_name else []),
            metadata=ChunkMetadata(source=MemorySource.REMINDERS.value, confidence=0.6, token_count=len(content.split()), is_sensitive=False),
            session_id=f"backfill-reminders-{datetime.now().strftime('%Y%m%d')}",
            auto_tag=False,
            scope=MemoryScope.LONG_TERM,
        )
        await db.record_dedup("reminders", source_id, chunk_obj.id, f"backfill-{datetime.now().strftime('%Y%m%d')}")
        stored += 1

        if verbose:
            status = "done" if is_completed else "open"
            print(f"  + [{status}] {title}")

    print(f"\nStored: {stored}, Deduped: {deduped}")


async def backfill_notes(verbose: bool) -> None:
    """Backfill notes from the CLI tool via NotesClient."""
    from hestia.apple.notes import NotesClient
    from hestia.memory import get_memory_manager
    from hestia.memory.models import (
        ChunkType, MemoryScope, MemorySource, ChunkMetadata, ChunkTags,
    )

    client = NotesClient()
    print("Querying all notes...")

    try:
        notes = await client.list_notes()
    except Exception as e:
        print(f"Failed to list notes: {type(e).__name__}: {e}")
        return

    print(f"Found {len(notes)} notes")

    # Quality gate: skip empty/stub notes
    filtered = []
    skipped = 0
    for note in notes:
        if not note.title or len(note.title.strip()) < 3:
            skipped += 1
            continue
        filtered.append(note)

    print(f"After quality gate: {len(filtered)} kept, {skipped} empty/stub skipped")

    memory_mgr = await get_memory_manager()
    db = memory_mgr.database
    stored = 0
    deduped = 0

    for note in filtered:
        source_id = f"notes:{note.id}"

        if await db.check_duplicate("notes", source_id):
            deduped += 1
            continue

        # Fetch full note content
        try:
            full_note = await client.get_note(note.id)
            body = full_note.body or ""
        except Exception:
            body = ""

        # Build content
        content_parts = [f"Note: {note.title}"]
        if note.folder:
            content_parts.append(f"Folder: {note.folder}")
        if body:
            # Truncate at 2000 chars (matching bridge limit)
            content_parts.append(body[:2000])

        content = "\n".join(content_parts)

        # Skip if content is too short after assembly
        if len(content) < 20:
            skipped += 1
            continue

        chunk_obj = await memory_mgr.store(
            content=content,
            chunk_type=ChunkType.OBSERVATION,
            tags=ChunkTags(topics=[note.folder] if note.folder else []),
            metadata=ChunkMetadata(
                source=MemorySource.NOTES.value,
                confidence=0.7,  # Notes are intentional — higher base confidence
                token_count=len(content.split()),
                is_sensitive=False,
            ),
            session_id=f"backfill-notes-{datetime.now().strftime('%Y%m%d')}",
            auto_tag=False,
            scope=MemoryScope.LONG_TERM,
        )
        await db.record_dedup("notes", source_id, chunk_obj.id, f"backfill-{datetime.now().strftime('%Y%m%d')}")
        stored += 1

        if verbose:
            print(f"  + [{note.folder}] {note.title}")

    print(f"\nStored: {stored}, Deduped: {deduped}, Skipped: {skipped}")


async def backfill_email(days_back: int, verbose: bool) -> None:
    """Backfill emails from the local Mail.app Envelope Index database.

    Uses direct SQLite writes to memory.db (skips ChromaDB embedding which
    hangs without the full server). Embeddings are generated on next server
    start when ChromaDB syncs with SQLite.
    """
    from hestia.apple.mail import MailClient, MailError
    import aiosqlite

    client = MailClient()
    hours = days_back * 24

    print(f"Querying Mail.app database (last {days_back} days)...")

    try:
        emails = await client.get_recent_emails(hours=hours, limit=2000)
    except MailError as e:
        print(f"Mail access failed: {e}")
        print("Ensure Full Disk Access is granted for this process.")
        return
    finally:
        await client.close()

    print(f"Found {len(emails)} emails")

    # Quality gate
    SKIP_SENDERS = [
        "noreply", "no-reply", "donotreply", "mailer-daemon",
        "notifications@", "newsletter@", "updates@", "info@",
        "support@", "billing@", "receipts@",
    ]
    filtered = []
    skipped = 0
    for email in emails:
        sender = str(email.sender_email or "").lower()
        subject = str(email.subject or "").lower()

        if any(skip in sender for skip in SKIP_SENDERS):
            skipped += 1
            continue
        if not subject or len(subject.strip()) < 3:
            skipped += 1
            continue
        if subject.startswith("re: re: re:") or "unsubscribe" in subject:
            skipped += 1
            continue
        filtered.append(email)

    print(f"After quality gate: {len(filtered)} kept, {skipped} noise skipped")

    # Direct SQLite insert (bypasses ChromaDB embedding hang)
    db_path = Path("data/memory.db")
    if not db_path.exists():
        print(f"Memory DB not found: {db_path}")
        return

    conn = await aiosqlite.connect(str(db_path))
    stored = 0
    deduped = 0
    batch_id = f"backfill-email-{datetime.now().strftime('%Y%m%d')}"

    for email in filtered:
        source_id = f"mail:{email.message_id or str(email.subject)}"

        # Dedup check
        row = await conn.execute(
            "SELECT 1 FROM source_dedup WHERE source = ? AND source_id = ?",
            ("mail", source_id),
        )
        if await row.fetchone():
            deduped += 1
            continue

        sender_display = email.sender_name or email.sender_email or "Unknown"
        content_parts = [f"Email from {sender_display}: {email.subject}"]
        if email.snippet:
            content_parts.append(str(email.snippet)[:1500])

        content = "\n".join(content_parts)
        if len(content) < 20:
            skipped += 1
            continue

        chunk_id = f"chunk-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        people = [sender_display] if sender_display != "Unknown" else []

        import json
        metadata = json.dumps({
            "source": "mail",
            "confidence": 0.5,
            "token_count": len(content.split()),
            "is_sensitive": False,
        })
        tags = json.dumps({
            "topics": [],
            "entities": [],
            "people": people,
        })

        await conn.execute(
            """INSERT OR IGNORE INTO memory_chunks
               (id, session_id, content, chunk_type, scope, status, timestamp, metadata, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chunk_id, batch_id, content, "observation", "long_term", "active", now, metadata, tags),
        )
        await conn.execute(
            "INSERT OR IGNORE INTO source_dedup (source, source_id, chunk_id, batch_id) VALUES (?, ?, ?, ?)",
            ("mail", source_id, chunk_id, batch_id),
        )
        stored += 1

        if verbose and stored <= 50:
            print(f"  + {sender_display}: {email.subject}")

        # Commit every 100
        if stored % 100 == 0:
            await conn.commit()
            print(f"  ... {stored} stored so far")

    await conn.commit()
    await conn.close()
    print(f"\nStored: {stored}, Deduped: {deduped}, Skipped: {skipped}")
    print("Note: ChromaDB embeddings will be generated on next server start.")


async def run_phase(phase: str, days_back: int, verbose: bool) -> None:
    """Run a backfill phase."""
    print(f"\n=== Backfill Phase: {phase.upper()} ===")
    print(f"Days back: {days_back}\n")

    if phase == "calendar":
        await backfill_calendar(days_back, verbose)
    elif phase == "reminders":
        await backfill_reminders(days_back, verbose)
    elif phase == "notes":
        await backfill_notes(verbose)
    elif phase == "email":
        await backfill_email(days_back, verbose)
    else:
        print(f"Unknown phase: {phase}")

    print(f"\n=== Phase {phase.upper()} complete ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Apple ecosystem data")
    parser.add_argument("--phase", required=True, choices=["notes", "reminders", "calendar", "email"])
    parser.add_argument("--days-back", type=int, default=180, help="How far back (default: 180 days)")
    parser.add_argument("--verbose", action="store_true", help="Show each item stored")
    args = parser.parse_args()

    asyncio.run(run_phase(args.phase, args.days_back, args.verbose))


if __name__ == "__main__":
    main()
