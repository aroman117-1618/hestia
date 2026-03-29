"""
Workflow database — SQLite with WAL mode for concurrent SSE/REST access.

Tables: workflows, workflow_nodes, workflow_edges, workflow_runs,
node_executions, workflow_versions.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent
from hestia.workflows.models import (
    NodeExecution,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRun,
)

logger = get_logger()

_DB_PATH = Path.home() / "hestia" / "data" / "workflows.db"

# Module-level singleton
_instance: Optional["WorkflowDatabase"] = None


class WorkflowDatabase(BaseDatabase):
    """Workflow database with WAL mode for concurrent SSE streaming."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("workflows", db_path or _DB_PATH)

    async def connect(self) -> None:
        """Open connection with WAL mode for concurrent reads."""
        self._connection = await aiosqlite.connect(self.db_path, isolation_level=None)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()
        await self.connection.execute("PRAGMA journal_mode=WAL")
        logger.info(
            "Workflow database connected (WAL mode)",
            component=LogComponent.WORKFLOW,
        )

    async def _init_schema(self) -> None:
        """Create tables and indexes."""
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                trigger_type TEXT NOT NULL DEFAULT 'manual',
                trigger_config TEXT DEFAULT '{}',
                session_strategy TEXT NOT NULL DEFAULT 'ephemeral',
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                activated_at TEXT,
                last_run_at TEXT,
                run_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                migrated_from_order_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);

            CREATE TABLE IF NOT EXISTS workflow_nodes (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT 'Untitled',
                config TEXT NOT NULL DEFAULT '{}',
                position_x REAL DEFAULT 0,
                position_y REAL DEFAULT 0,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_workflow ON workflow_nodes(workflow_id);

            CREATE TABLE IF NOT EXISTS workflow_edges (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                edge_label TEXT DEFAULT '',
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
                FOREIGN KEY (source_node_id) REFERENCES workflow_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_node_id) REFERENCES workflow_nodes(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_edges_workflow ON workflow_edges(workflow_id);

            CREATE TABLE IF NOT EXISTS workflow_runs (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                workflow_version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pending',
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_ms REAL,
                trigger_source TEXT DEFAULT 'manual',
                error_message TEXT,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_runs_workflow ON workflow_runs(workflow_id);
            CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status);
            CREATE INDEX IF NOT EXISTS idx_runs_started ON workflow_runs(started_at DESC);

            CREATE TABLE IF NOT EXISTS node_executions (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                started_at TEXT,
                completed_at TEXT,
                duration_ms REAL,
                input_data TEXT DEFAULT '{}',
                output_data TEXT DEFAULT '{}',
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (node_id) REFERENCES workflow_nodes(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_node_exec_run ON node_executions(run_id);
            CREATE INDEX IF NOT EXISTS idx_node_exec_node ON node_executions(node_id);

            CREATE TABLE IF NOT EXISTS workflow_versions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_versions_workflow
                ON workflow_versions(workflow_id, version DESC);
        """)

    # ── Workflow CRUD ────────────────────────────────────────────────

    async def store_workflow(self, wf: Workflow) -> str:
        """Insert a new workflow. Returns workflow ID."""
        await self.connection.execute(
            """INSERT INTO workflows
               (id, name, description, status, trigger_type, trigger_config,
                session_strategy, version, created_at, updated_at,
                activated_at, last_run_at, run_count, success_count,
                migrated_from_order_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                wf.id, wf.name, wf.description, wf.status.value,
                wf.trigger_type.value, json.dumps(wf.trigger_config),
                wf.session_strategy.value, wf.version,
                wf.created_at.isoformat(), wf.updated_at.isoformat(),
                wf.activated_at.isoformat() if wf.activated_at else None,
                wf.last_run_at.isoformat() if wf.last_run_at else None,
                wf.run_count, wf.success_count, wf.migrated_from_order_id,
            ),
        )
        await self.connection.commit()
        return wf.id

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        cursor = await self.connection.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return Workflow.from_sqlite_row(dict(row))

    async def update_workflow(self, wf: Workflow) -> None:
        """Update an existing workflow."""
        wf.updated_at = datetime.now(timezone.utc)
        await self.connection.execute(
            """UPDATE workflows SET
               name=?, description=?, status=?, trigger_type=?, trigger_config=?,
               session_strategy=?, version=?, updated_at=?, activated_at=?,
               last_run_at=?, run_count=?, success_count=?, migrated_from_order_id=?
               WHERE id=?""",
            (
                wf.name, wf.description, wf.status.value,
                wf.trigger_type.value, json.dumps(wf.trigger_config),
                wf.session_strategy.value, wf.version,
                wf.updated_at.isoformat(),
                wf.activated_at.isoformat() if wf.activated_at else None,
                wf.last_run_at.isoformat() if wf.last_run_at else None,
                wf.run_count, wf.success_count, wf.migrated_from_order_id,
                wf.id,
            ),
        )
        await self.connection.commit()

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow (cascades to nodes, edges, runs)."""
        cursor = await self.connection.execute(
            "DELETE FROM workflows WHERE id = ?", (workflow_id,)
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def list_workflows(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Workflow], int]:
        """List workflows with optional status filter. Returns (workflows, total)."""
        where = "WHERE status = ?" if status else ""
        params: list = [status] if status else []

        # Count
        count_cursor = await self.connection.execute(
            f"SELECT COUNT(*) FROM workflows {where}", params
        )
        total = (await count_cursor.fetchone())[0]

        # Fetch
        cursor = await self.connection.execute(
            f"SELECT * FROM workflows {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        rows = await cursor.fetchall()
        return [Workflow.from_sqlite_row(dict(r)) for r in rows], total

    # ── Node CRUD ────────────────────────────────────────────────────

    async def add_node(self, node: WorkflowNode) -> str:
        """Insert a node. Returns node ID."""
        await self.connection.execute(
            """INSERT INTO workflow_nodes
               (id, workflow_id, node_type, label, config, position_x, position_y)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                node.id, node.workflow_id, node.node_type.value,
                node.label, json.dumps(node.config),
                node.position_x, node.position_y,
            ),
        )
        await self.connection.commit()
        return node.id

    async def update_node(self, node: WorkflowNode) -> None:
        """Update an existing node."""
        await self.connection.execute(
            """UPDATE workflow_nodes SET
               node_type=?, label=?, config=?, position_x=?, position_y=?
               WHERE id=?""",
            (
                node.node_type.value, node.label, json.dumps(node.config),
                node.position_x, node.position_y, node.id,
            ),
        )
        await self.connection.commit()

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node (cascades edges)."""
        cursor = await self.connection.execute(
            "DELETE FROM workflow_nodes WHERE id = ?", (node_id,)
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get a single node by ID."""
        cursor = await self.connection.execute(
            "SELECT * FROM workflow_nodes WHERE id = ?", (node_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return WorkflowNode.from_sqlite_row(dict(row))

    async def get_nodes_for_workflow(self, workflow_id: str) -> List[WorkflowNode]:
        """Get all nodes for a workflow."""
        cursor = await self.connection.execute(
            "SELECT * FROM workflow_nodes WHERE workflow_id = ? ORDER BY position_y, position_x",
            (workflow_id,),
        )
        rows = await cursor.fetchall()
        return [WorkflowNode.from_sqlite_row(dict(r)) for r in rows]

    # ── Edge CRUD ────────────────────────────────────────────────────

    async def add_edge(self, edge: WorkflowEdge) -> str:
        """Insert an edge. Returns edge ID."""
        await self.connection.execute(
            """INSERT INTO workflow_edges
               (id, workflow_id, source_node_id, target_node_id, edge_label)
               VALUES (?, ?, ?, ?, ?)""",
            (
                edge.id, edge.workflow_id, edge.source_node_id,
                edge.target_node_id, edge.edge_label,
            ),
        )
        await self.connection.commit()
        return edge.id

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        cursor = await self.connection.execute(
            "DELETE FROM workflow_edges WHERE id = ?", (edge_id,)
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def get_edges_for_workflow(self, workflow_id: str) -> List[WorkflowEdge]:
        """Get all edges for a workflow."""
        cursor = await self.connection.execute(
            "SELECT * FROM workflow_edges WHERE workflow_id = ?", (workflow_id,),
        )
        rows = await cursor.fetchall()
        return [WorkflowEdge.from_sqlite_row(dict(r)) for r in rows]

    # ── Run Lifecycle ────────────────────────────────────────────────

    async def create_run(self, run: WorkflowRun) -> str:
        """Insert a new run. Returns run ID."""
        await self.connection.execute(
            """INSERT INTO workflow_runs
               (id, workflow_id, workflow_version, status, started_at,
                completed_at, duration_ms, trigger_source, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id, run.workflow_id, run.workflow_version,
                run.status.value, run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
                run.duration_ms, run.trigger_source, run.error_message,
            ),
        )
        await self.connection.commit()
        return run.id

    async def update_run(self, run: WorkflowRun) -> None:
        """Update a run (typically to mark completed/failed)."""
        await self.connection.execute(
            """UPDATE workflow_runs SET
               status=?, completed_at=?, duration_ms=?, error_message=?
               WHERE id=?""",
            (
                run.status.value,
                run.completed_at.isoformat() if run.completed_at else None,
                run.duration_ms, run.error_message, run.id,
            ),
        )
        await self.connection.commit()

    async def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Get a run by ID."""
        cursor = await self.connection.execute(
            "SELECT * FROM workflow_runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return WorkflowRun.from_sqlite_row(dict(row))

    async def list_runs(
        self,
        workflow_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[WorkflowRun], int]:
        """List runs for a workflow. Returns (runs, total)."""
        count_cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM workflow_runs WHERE workflow_id = ?",
            (workflow_id,),
        )
        total = (await count_cursor.fetchone())[0]

        cursor = await self.connection.execute(
            """SELECT * FROM workflow_runs WHERE workflow_id = ?
               ORDER BY started_at DESC LIMIT ? OFFSET ?""",
            (workflow_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [WorkflowRun.from_sqlite_row(dict(r)) for r in rows], total

    async def list_recent_runs(
        self,
        since: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List recent runs across all workflows (for newsfeed aggregation).

        Args:
            since: ISO datetime string — only runs started after this time.
            limit: Max results.

        Returns:
            List of dicts with run data + workflow name.
        """
        cursor = await self.connection.execute(
            """SELECT r.*, w.name as workflow_name
               FROM workflow_runs r
               JOIN workflows w ON r.workflow_id = w.id
               WHERE r.started_at >= ?
               ORDER BY r.started_at DESC
               LIMIT ?""",
            (since, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def increment_run_counts(
        self, workflow_id: str, success: bool
    ) -> None:
        """Increment run_count (and success_count if successful) on a workflow."""
        if success:
            await self.connection.execute(
                """UPDATE workflows SET
                   run_count = run_count + 1, success_count = success_count + 1,
                   last_run_at = ?
                   WHERE id = ?""",
                (datetime.now(timezone.utc).isoformat(), workflow_id),
            )
        else:
            await self.connection.execute(
                """UPDATE workflows SET
                   run_count = run_count + 1, last_run_at = ?
                   WHERE id = ?""",
                (datetime.now(timezone.utc).isoformat(), workflow_id),
            )
        await self.connection.commit()

    # ── Node Execution ───────────────────────────────────────────────

    async def create_node_execution(self, ne: NodeExecution) -> str:
        """Insert a node execution record. Returns ID."""
        await self.connection.execute(
            """INSERT INTO node_executions
               (id, run_id, node_id, status, started_at, completed_at,
                duration_ms, input_data, output_data, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ne.id, ne.run_id, ne.node_id, ne.status.value,
                ne.started_at.isoformat() if ne.started_at else None,
                ne.completed_at.isoformat() if ne.completed_at else None,
                ne.duration_ms, json.dumps(ne.input_data),
                json.dumps(ne.output_data), ne.error_message,
            ),
        )
        await self.connection.commit()
        return ne.id

    async def update_node_execution(self, ne: NodeExecution) -> None:
        """Update a node execution record."""
        await self.connection.execute(
            """UPDATE node_executions SET
               status=?, started_at=?, completed_at=?, duration_ms=?,
               input_data=?, output_data=?, error_message=?
               WHERE id=?""",
            (
                ne.status.value,
                ne.started_at.isoformat() if ne.started_at else None,
                ne.completed_at.isoformat() if ne.completed_at else None,
                ne.duration_ms, json.dumps(ne.input_data),
                json.dumps(ne.output_data), ne.error_message, ne.id,
            ),
        )
        await self.connection.commit()

    async def get_executions_for_run(self, run_id: str) -> List[NodeExecution]:
        """Get all node executions for a run."""
        cursor = await self.connection.execute(
            "SELECT * FROM node_executions WHERE run_id = ? ORDER BY started_at",
            (run_id,),
        )
        rows = await cursor.fetchall()
        return [NodeExecution.from_sqlite_row(dict(r)) for r in rows]

    # ── Version Snapshots ────────────────────────────────────────────

    async def store_version_snapshot(
        self,
        snapshot_id: str,
        workflow_id: str,
        version: int,
        snapshot: Dict[str, Any],
    ) -> None:
        """Store a snapshot of nodes + edges at activation time."""
        await self.connection.execute(
            """INSERT INTO workflow_versions (id, workflow_id, version, snapshot, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                snapshot_id, workflow_id, version,
                json.dumps(snapshot), datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self.connection.commit()

    async def get_version_snapshot(
        self, workflow_id: str, version: int
    ) -> Optional[Dict[str, Any]]:
        """Get a specific version snapshot."""
        cursor = await self.connection.execute(
            "SELECT snapshot FROM workflow_versions WHERE workflow_id = ? AND version = ?",
            (workflow_id, version),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return json.loads(row["snapshot"])

    # ── Batch Position Update ────────────────────────────────────────

    async def batch_update_positions(
        self, workflow_id: str, positions: list[dict],
    ) -> int:
        """Update position_x/position_y for multiple nodes atomically."""
        updated = 0
        for pos in positions:
            cursor = await self.connection.execute(
                """UPDATE workflow_nodes SET position_x=?, position_y=?
                   WHERE id=? AND workflow_id=?""",
                (pos["position_x"], pos["position_y"], pos["node_id"], workflow_id),
            )
            updated += cursor.rowcount
        await self.connection.commit()
        return updated

    # ── Purge ────────────────────────────────────────────────────────

    async def purge_old_executions(self, days: int = 30) -> int:
        """Delete node_executions older than N days. Returns count deleted."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self.connection.execute(
            "DELETE FROM node_executions WHERE completed_at < ? AND completed_at IS NOT NULL",
            (cutoff,),
        )
        await self.connection.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(
                f"Purged {deleted} node execution records older than {days} days",
                component=LogComponent.WORKFLOW,
            )
        return deleted


# ── Singleton Factory ────────────────────────────────────────────────


async def get_workflow_database(
    db_path: Optional[Path] = None,
) -> WorkflowDatabase:
    """Get or create the singleton workflow database."""
    global _instance
    if _instance is None:
        _instance = WorkflowDatabase(db_path)
        await _instance.connect()
    return _instance


async def close_workflow_database() -> None:
    """Close the singleton workflow database."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
