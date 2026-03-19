#!/usr/bin/env python3
"""
Retroactive LLM-backed reclassification of CONVERSATION and OBSERVATION chunks.

Loads candidates from memory.db, applies the same quality gates as AutoTagger._should_classify,
then calls extract_tags() for LLM classification. Chunks whose suggested_type is promotable
(decision, action_item, preference, research) with confidence >= 0.7 are reclassified.

Default is dry run. Use --apply to write changes to both SQLite and ChromaDB.

Usage:
    python scripts/reclassify-conversations.py              # dry run
    python scripts/reclassify-conversations.py --apply       # write changes
    python scripts/reclassify-conversations.py --limit 50    # process first 50 candidates
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from hestia.memory.tagger import (  # noqa: E402
    AutoTagger,
    PROMO_SIGNALS,
    MIN_CLASSIFICATION_LENGTH,
    CLASSIFICATION_CONFIDENCE_THRESHOLD,
    PROMOTABLE_TYPES,
)
from hestia.memory.models import ChunkType  # noqa: E402


DB_PATH = PROJECT_ROOT / "data" / "memory.db"


def load_candidates(conn: sqlite3.Connection) -> list[dict]:
    """Load CONVERSATION and OBSERVATION chunks that pass quality gates."""
    rows = conn.execute(
        "SELECT id, content, tags, metadata "
        "FROM memory_chunks "
        "WHERE chunk_type IN ('conversation', 'observation') "
        "AND status = 'active'"
    ).fetchall()

    candidates = []
    skipped_short = 0
    skipped_promo = 0
    skipped_folder = 0

    for row in rows:
        chunk_id = row["id"]
        content = row["content"]
        tags_raw = row["tags"]
        metadata_raw = row["metadata"]

        # Parse JSON fields
        try:
            tags_data = json.loads(tags_raw) if tags_raw else {}
        except json.JSONDecodeError:
            tags_data = {}

        try:
            meta_data = json.loads(metadata_raw) if metadata_raw else {}
        except json.JSONDecodeError:
            meta_data = {}

        source = meta_data.get("source", "")

        # Gate 1: minimum length
        if len(content.strip()) < MIN_CLASSIFICATION_LENGTH:
            skipped_short += 1
            continue

        # Gate 2: promotional email filter
        if source == "mail":
            content_lower = content.lower()
            if any(signal in content_lower for signal in PROMO_SIGNALS):
                skipped_promo += 1
                continue

        # Gate 3: notes must be from Intelligence folder
        if source == "notes":
            custom = tags_data.get("custom", {})
            folder = custom.get("folder", "")
            if not folder or "intelligence" not in folder.lower():
                skipped_folder += 1
                continue

        candidates.append({
            "id": chunk_id,
            "content": content,
            "tags": tags_data,
            "metadata": meta_data,
        })

    print(f"\n=== Candidate Selection ===")
    print(f"Total CONVERSATION + OBSERVATION chunks: {len(rows)}")
    print(f"Skipped (too short <{MIN_CLASSIFICATION_LENGTH} chars): {skipped_short}")
    print(f"Skipped (promotional email): {skipped_promo}")
    print(f"Skipped (non-Intelligence notes): {skipped_folder}")
    print(f"Candidates for LLM classification: {len(candidates)}")

    return candidates


async def classify_candidates(
    candidates: list[dict],
    limit: int | None = None,
) -> list[dict]:
    """Run LLM classification on candidates, return promotion list."""
    tagger = AutoTagger()
    to_process = candidates[:limit] if limit else candidates
    total = len(to_process)

    promotions: list[dict] = []
    type_counts: dict[str, int] = {}
    errors = 0

    print(f"\n=== LLM Classification ({total} chunks) ===")
    print(f"This will take ~{total * 1.5 / 60:.0f} minutes at ~1.5s per chunk.\n")

    for i, candidate in enumerate(to_process):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  Processing {i + 1}/{total}...")

        try:
            tags, metadata = await tagger.extract_tags(candidate["content"])
        except Exception:
            errors += 1
            continue

        suggested_type = metadata.suggested_type
        confidence = metadata.type_confidence

        # Track all suggestions
        label = suggested_type or "none"
        type_counts[label] = type_counts.get(label, 0) + 1

        # Check promotion criteria
        if (
            suggested_type
            and suggested_type in PROMOTABLE_TYPES
            and confidence >= CLASSIFICATION_CONFIDENCE_THRESHOLD
        ):
            promotions.append({
                "id": candidate["id"],
                "old_type": "conversation",  # or observation — both eligible
                "new_type": suggested_type,
                "confidence": confidence,
                "preview": candidate["content"][:80],
            })

    print(f"\n=== Classification Results ===")
    print(f"Processed: {total - errors}")
    print(f"Errors: {errors}")
    print(f"\nSuggested type distribution:")
    for type_name, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        marker = " *" if type_name in PROMOTABLE_TYPES else ""
        print(f"  {type_name}: {count}{marker}")
    print(f"\nPromotable (confidence >= {CLASSIFICATION_CONFIDENCE_THRESHOLD}):")
    promo_counts: dict[str, int] = {}
    for p in promotions:
        promo_counts[p["new_type"]] = promo_counts.get(p["new_type"], 0) + 1
    for type_name, count in sorted(promo_counts.items(), key=lambda x: -x[1]):
        print(f"  → {type_name}: {count}")
    print(f"  Total promotions: {len(promotions)}")

    return promotions


def apply_promotions(conn: sqlite3.Connection, promotions: list[dict]) -> None:
    """Write promotions to SQLite and ChromaDB."""
    if not promotions:
        print("\nNo promotions to apply.")
        return

    # SQLite updates
    cursor = conn.cursor()
    for p in promotions:
        cursor.execute(
            "UPDATE memory_chunks SET chunk_type = ? WHERE id = ?",
            (p["new_type"], p["id"]),
        )
    conn.commit()
    print(f"\n  SQLite: updated {len(promotions)} chunks")

    # ChromaDB updates (best-effort)
    try:
        from hestia.memory.vector_store import get_vector_store

        vs = get_vector_store()
        updated = 0
        failed = 0
        for p in promotions:
            try:
                vs._collection.update(
                    ids=[p["id"]],
                    metadatas=[{"chunk_type": p["new_type"]}],
                )
                updated += 1
            except Exception:
                failed += 1
        print(f"  ChromaDB: updated {updated}, failed {failed}")
    except Exception as e:
        print(f"  ChromaDB: skipped ({type(e).__name__}: {e})")
        print("  SQLite changes still stand.")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retroactive LLM-backed reclassification of memory chunks"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry run)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of chunks to process (for testing)",
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help="Path to memory database",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Current state
    total = conn.execute(
        "SELECT COUNT(*) FROM memory_chunks WHERE status = 'active'"
    ).fetchone()[0]
    conv = conn.execute(
        "SELECT COUNT(*) FROM memory_chunks "
        "WHERE chunk_type = 'conversation' AND status = 'active'"
    ).fetchone()[0]
    obs = conn.execute(
        "SELECT COUNT(*) FROM memory_chunks "
        "WHERE chunk_type = 'observation' AND status = 'active'"
    ).fetchone()[0]

    print(f"=== Current State ===")
    print(f"Total active chunks: {total}")
    print(f"CONVERSATION: {conv}")
    print(f"OBSERVATION: {obs}")

    # Load and filter candidates
    candidates = load_candidates(conn)

    if not candidates:
        print("\nNo candidates to classify.")
        conn.close()
        return

    # Run LLM classification
    promotions = await classify_candidates(candidates, limit=args.limit)

    if not args.apply:
        print(f"\n[DRY RUN] No changes written. Use --apply to commit.")
        if promotions:
            print("\nSample promotions:")
            for p in promotions[:10]:
                print(f"  {p['id']}: → {p['new_type']} ({p['confidence']:.2f}) {p['preview']}")
        conn.close()
        return

    # Apply
    apply_promotions(conn, promotions)
    conn.close()

    print(f"\n=== Done ===")
    print(f"Reclassified {len(promotions)} chunks.")
    print("Verify with:")
    print('  sqlite3 data/memory.db "SELECT chunk_type, COUNT(*) FROM memory_chunks WHERE status=\'active\' GROUP BY chunk_type;"')


if __name__ == "__main__":
    asyncio.run(main())
