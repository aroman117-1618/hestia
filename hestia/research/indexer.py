"""Batch indexer for entity references across Hestia modules.

Scans workflow steps and research canvas boards for mentions of known Research
entities, then upserts references into the entity_references table.  The
UNIQUE(entity_id, module, item_id) constraint on the table makes repeated runs
idempotent — duplicates are silently ignored.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from hestia.logging import LogComponent, get_logger

if TYPE_CHECKING:
    from hestia.research.database import ResearchDatabase
    from hestia.workflows.database import WorkflowDatabase

logger = get_logger()


async def index_workflow_references(
    research_db: "ResearchDatabase",
    workflow_db: "WorkflowDatabase",
) -> int:
    """Scan workflow nodes for entity name mentions; upsert entity_references.

    Checks every WorkflowNode's config dict (prompt text, tool arguments, etc.)
    for occurrences of each entity's canonical_name.  Only plain-text substring
    matching is used — no LLM involved — so this is fast and cheap.

    Returns the number of new references inserted (duplicates are ignored).
    """
    from hestia.research.references import EntityReference, ReferenceModule

    if not research_db._connection or not workflow_db.connection:
        return 0

    # Fetch all entities (in batches to avoid loading millions of rows)
    entities = await research_db.list_entities(limit=500)
    if not entities:
        return 0

    # Fetch all workflows, then their nodes
    workflows, _ = await workflow_db.list_workflows(limit=500)
    if not workflows:
        return 0

    inserted = 0
    for workflow in workflows:
        nodes = await workflow_db.get_nodes_for_workflow(workflow.id)
        for node in nodes:
            # Serialise the entire node config to a searchable string
            node_text = json.dumps(node.config).lower()
            if not node_text:
                continue

            for entity in entities:
                if entity.canonical_name and entity.canonical_name.lower() in node_text:
                    ref = EntityReference(
                        entity_id=entity.id,
                        module=ReferenceModule.WORKFLOW,
                        item_id=workflow.id,
                        context=f"{workflow.name} / {node.label}",
                        user_id=entity.user_id,
                    )
                    try:
                        await research_db.add_entity_reference(ref)
                        inserted += 1
                    except Exception:
                        # UNIQUE conflict is handled by INSERT OR IGNORE; other
                        # errors are swallowed so one bad row never aborts the run.
                        pass

    logger.info(
        "index_workflow_references_done",
        component=LogComponent.RESEARCH,
        data={"inserted": inserted},
    )
    return inserted


async def index_research_canvas_references(
    research_db: "ResearchDatabase",
) -> int:
    """Index entities pinned to research canvas boards.

    Parses the layout_json of every board for nodes whose id looks like an
    entity UUID and creates a RESEARCH_CANVAS reference for each.  Boards store
    their layout as a React Flow JSON blob; entity nodes carry a ``data.entityId``
    field that was written by the canvas when the node was created.

    Returns the number of new references inserted.
    """
    from hestia.research.references import EntityReference, ReferenceModule

    if not research_db._connection:
        return 0

    boards = await research_db.list_boards()
    if not boards:
        return 0

    # Build a quick lookup of valid entity IDs
    entities = await research_db.list_entities(limit=1000)
    entity_ids = {e.id for e in entities}
    entity_user: dict[str, str] = {e.id: e.user_id for e in entities}

    inserted = 0
    for board in boards:
        try:
            layout = json.loads(board.layout_json) if board.layout_json else {}
        except json.JSONDecodeError:
            continue

        nodes = layout.get("nodes", [])
        for node in nodes:
            # Canvas entity nodes carry the entity ID in node.data.entityId
            node_data = node.get("data") or {}
            entity_id = node_data.get("entityId") or node_data.get("entity_id")
            if not entity_id or entity_id not in entity_ids:
                continue

            ref = EntityReference(
                entity_id=entity_id,
                module=ReferenceModule.RESEARCH_CANVAS,
                item_id=board.id,
                context=board.name,
                user_id=entity_user.get(entity_id, ""),
            )
            try:
                await research_db.add_entity_reference(ref)
                inserted += 1
            except Exception:
                pass

    logger.info(
        "index_research_canvas_references_done",
        component=LogComponent.RESEARCH,
        data={"inserted": inserted},
    )
    return inserted


async def run_batch_index(
    research_db: "ResearchDatabase",
    workflow_db: Optional["WorkflowDatabase"] = None,
) -> dict[str, int]:
    """Run all indexers and return a count dict keyed by module name.

    Callers may omit workflow_db (e.g. in tests) to skip workflow scanning.
    """
    counts: dict[str, int] = {}

    if workflow_db is not None:
        counts["workflow"] = await index_workflow_references(research_db, workflow_db)

    counts["research_canvas"] = await index_research_canvas_references(research_db)

    logger.info("batch_reference_index_complete", component=LogComponent.RESEARCH, data={"counts": counts})
    return counts
