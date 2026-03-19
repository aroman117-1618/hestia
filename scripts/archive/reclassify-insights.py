#!/usr/bin/env python3
"""
Reclassify misclassified INSIGHT chunks from Claude history imports.

Sprint 25.5 data quality plan — Issue 2.

Phase 1: Heuristic filter downgrades procedural/low-quality INSIGHT → CONVERSATION
Phase 2: Remaining INSIGHTs → OBSERVATION (new taxonomy type)

Run with: python scripts/reclassify-insights.py [--dry-run] [--verbose]
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# Patterns that indicate procedural/low-quality content (not genuine insights)
LOW_QUALITY_PATTERNS = [
    # Assistant procedural responses
    re.compile(r"^(The user wants|Great!|Sure|OK|Let me|I'll|I've|Here's|Done)", re.IGNORECASE),
    re.compile(r"^(Looking at|Checking|Running|Starting|Updating|Now let)", re.IGNORECASE),
    re.compile(r"^(Perfect|Excellent|Good|Alright|Understood|Got it)", re.IGNORECASE),
    # Code references (not insights)
    re.compile(r"(ExecutionStatus|models\.py|import |def |class |async def|\.swift)"),
    re.compile(r"^```"),  # Code blocks
    # Very short content
    re.compile(r"^.{0,30}$"),
    # Status updates
    re.compile(r"^(All tests pass|Build succeeded|Commit |Pushed to|Deployed|Merged)", re.IGNORECASE),
    # Pure questions with no insight
    re.compile(r"^(What |How |Where |When |Why |Can you|Could you|Should I)", re.IGNORECASE),
]

# Bracket prefix pattern (from StringExtensions.swift)
BRACKET_PREFIX = re.compile(r"^\[[^\]]+\]:\s*")


def strip_bracket_prefixes(text: str) -> str:
    """Strip leading [PREFIX]: patterns from imported content."""
    result = text
    while BRACKET_PREFIX.match(result):
        result = BRACKET_PREFIX.sub("", result, count=1)
    return result if result else text


def is_low_quality(content: str) -> bool:
    """Check if content matches any low-quality heuristic pattern."""
    cleaned = strip_bracket_prefixes(content).strip()
    return any(p.search(cleaned) for p in LOW_QUALITY_PATTERNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclassify misclassified INSIGHT chunks")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--verbose", action="store_true", help="Show each reclassified chunk")
    parser.add_argument("--db", default="data/memory.db", help="Path to memory database")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Phase 0: Current state
    total = conn.execute(
        "SELECT COUNT(*) FROM memory_chunks WHERE status = 'active'"
    ).fetchone()[0]
    insights = conn.execute(
        "SELECT COUNT(*) FROM memory_chunks WHERE chunk_type = 'insight' AND status = 'active'"
    ).fetchone()[0]
    claude_insights = conn.execute(
        "SELECT COUNT(*) FROM memory_chunks WHERE chunk_type = 'insight' "
        "AND json_extract(metadata, '$.source') = 'claude_history' AND status = 'active'"
    ).fetchone()[0]

    print(f"\n=== Current State ===")
    print(f"Total active chunks: {total}")
    print(f"INSIGHT chunks: {insights}")
    print(f"  From Claude history: {claude_insights}")
    print()

    # Phase 1: Heuristic reclassification (INSIGHT → CONVERSATION for low-quality)
    rows = conn.execute(
        "SELECT id, content, json_extract(metadata, '$.source') as source "
        "FROM memory_chunks WHERE chunk_type = 'insight' AND status = 'active'"
    ).fetchall()

    downgrade_to_conversation = []
    upgrade_to_observation = []

    for row in rows:
        content = row["content"]
        if is_low_quality(content):
            downgrade_to_conversation.append(row["id"])
            if args.verbose:
                preview = strip_bracket_prefixes(content)[:80]
                print(f"  → CONVERSATION: {preview}")
        else:
            upgrade_to_observation.append(row["id"])
            if args.verbose:
                preview = strip_bracket_prefixes(content)[:80]
                print(f"  → OBSERVATION:  {preview}")

    print(f"\n=== Reclassification Plan ===")
    print(f"INSIGHT → CONVERSATION (low-quality): {len(downgrade_to_conversation)}")
    print(f"INSIGHT → OBSERVATION (kept):         {len(upgrade_to_observation)}")
    print(f"Total unchanged:                      {insights - len(downgrade_to_conversation) - len(upgrade_to_observation)}")
    print()

    if args.dry_run:
        print("[DRY RUN] No changes written.")
        conn.close()
        return

    # Phase 2: Apply reclassification
    confirm = input("Apply reclassification? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        conn.close()
        return

    cursor = conn.cursor()

    if downgrade_to_conversation:
        placeholders = ",".join(["?"] * len(downgrade_to_conversation))
        cursor.execute(
            f"UPDATE memory_chunks SET chunk_type = 'conversation' WHERE id IN ({placeholders})",
            downgrade_to_conversation,
        )
        print(f"  Downgraded {cursor.rowcount} chunks to CONVERSATION")

    if upgrade_to_observation:
        placeholders = ",".join(["?"] * len(upgrade_to_observation))
        cursor.execute(
            f"UPDATE memory_chunks SET chunk_type = 'observation' WHERE id IN ({placeholders})",
            upgrade_to_observation,
        )
        print(f"  Upgraded {cursor.rowcount} chunks to OBSERVATION")

    conn.commit()
    conn.close()

    print("\n=== Done ===")
    print(f"Reclassified {len(downgrade_to_conversation) + len(upgrade_to_observation)} chunks.")
    print("Run with --dry-run first to preview. Verify with:")
    print("  sqlite3 data/memory.db \"SELECT chunk_type, COUNT(*) FROM memory_chunks WHERE status='active' GROUP BY chunk_type;\"")


if __name__ == "__main__":
    main()
