"""
Orders-to-Workflows migration — converts existing orders into workflow DAGs.

Each order becomes a workflow with a schedule trigger node connected
to a run_prompt node. Execution history is migrated as workflow runs.

The migration is idempotent: orders with an existing migrated_from_order_id
are skipped. Original orders are marked COMPLETED (not deleted) for
rollback safety.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from hestia.logging import get_logger, LogComponent
from hestia.workflows.models import (
    SessionStrategy,
    TriggerType,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
    NodeExecution,
    NodeExecutionStatus,
    NodeType,
    RunStatus,
)

logger = get_logger()


def _frequency_to_trigger_config(order: Dict) -> Dict:
    """Convert OrderFrequency to workflow trigger_config."""
    freq_type = order.get("frequency_type", "daily")
    freq_minutes = order.get("frequency_minutes")
    scheduled_time = order.get("scheduled_time", "07:00:00")

    # Parse time components
    parts = scheduled_time.split(":")
    hour = parts[0] if len(parts) > 0 else "7"
    minute = parts[1] if len(parts) > 1 else "0"

    if freq_type == "daily":
        return {"cron": f"{minute} {hour} * * *"}
    elif freq_type == "weekly":
        return {"cron": f"{minute} {hour} * * 1"}  # Monday
    elif freq_type == "monthly":
        return {"cron": f"{minute} {hour} 1 * *"}  # 1st of month
    elif freq_type == "custom" and freq_minutes and int(freq_minutes) >= 15:
        return {"interval_minutes": int(freq_minutes)}
    elif freq_type == "once":
        return {"cron": f"{minute} {hour} * * *"}  # Default to daily
    else:
        return {"cron": f"{minute} {hour} * * *"}


async def migrate_orders_to_workflows(
    order_db: Optional[object] = None,
    workflow_db: Optional[object] = None,
) -> Dict:
    """
    Migrate all orders to workflows.

    Returns summary dict with counts of migrated, skipped, failed.
    """
    from hestia.orders.database import get_order_database
    from hestia.workflows.database import get_workflow_database

    if order_db is None:
        order_db = await get_order_database()
    if workflow_db is None:
        workflow_db = await get_workflow_database()

    # Get all orders
    cursor = await order_db.connection.execute("SELECT * FROM orders")
    order_rows = await cursor.fetchall()

    # Check which orders are already migrated
    wf_cursor = await workflow_db.connection.execute(
        "SELECT migrated_from_order_id FROM workflows WHERE migrated_from_order_id IS NOT NULL"
    )
    already_migrated = {row[0] for row in await wf_cursor.fetchall()}

    migrated = 0
    skipped = 0
    failed = 0

    for row in order_rows:
        order = dict(row)
        order_id = order["id"]

        # Skip already-migrated orders (idempotent)
        if order_id in already_migrated:
            skipped += 1
            continue

        try:
            await _migrate_single_order(order, workflow_db, order_db)
            migrated += 1
        except Exception as e:
            failed += 1
            logger.warning(
                f"Failed to migrate order {order_id}: {type(e).__name__}",
                component=LogComponent.WORKFLOW,
            )

    # Mark migrated orders as COMPLETED
    if migrated > 0:
        for row in order_rows:
            order = dict(row)
            if order["id"] not in already_migrated:
                await order_db.connection.execute(
                    "UPDATE orders SET status = 'completed' WHERE id = ?",
                    (order["id"],),
                )
        await order_db.connection.commit()

    summary = {
        "migrated": migrated,
        "skipped": skipped,
        "failed": failed,
        "total_orders": len(order_rows),
    }

    logger.info(
        f"Order migration complete: {migrated} migrated, {skipped} skipped, {failed} failed",
        component=LogComponent.WORKFLOW,
        data=summary,
    )
    return summary


async def _migrate_single_order(
    order: Dict, workflow_db: object, order_db: object
) -> None:
    """Migrate a single order to a workflow."""
    order_id = order["id"]
    trigger_config = _frequency_to_trigger_config(order)

    # Create workflow
    wf = Workflow(
        name=order.get("name", "Migrated Order"),
        description=f"Migrated from order {order_id}",
        status=WorkflowStatus.DRAFT,
        trigger_type=TriggerType.SCHEDULE,
        trigger_config=trigger_config,
        session_strategy=SessionStrategy.PER_RUN,
        migrated_from_order_id=order_id,
    )
    await workflow_db.store_workflow(wf)

    # Create trigger node
    trigger_node = WorkflowNode(
        workflow_id=wf.id,
        node_type=NodeType.SCHEDULE,
        label="Schedule Trigger",
        config=trigger_config,
    )
    await workflow_db.add_node(trigger_node)

    # Create prompt node
    prompt_node = WorkflowNode(
        workflow_id=wf.id,
        node_type=NodeType.RUN_PROMPT,
        label=order.get("name", "Execute"),
        config={
            "prompt": order.get("prompt", ""),
            "memory_write": False,
            "memory_read": True,
        },
        position_y=100.0,  # Below trigger
    )
    await workflow_db.add_node(prompt_node)

    # Create edge: trigger -> prompt
    edge = WorkflowEdge(
        workflow_id=wf.id,
        source_node_id=trigger_node.id,
        target_node_id=prompt_node.id,
    )
    await workflow_db.add_edge(edge)

    # Migrate execution history
    exec_cursor = await order_db.connection.execute(
        "SELECT * FROM order_executions WHERE order_id = ? ORDER BY timestamp",
        (order_id,),
    )
    exec_rows = await exec_cursor.fetchall()

    for exec_row in exec_rows:
        execution = dict(exec_row)
        run = WorkflowRun(
            workflow_id=wf.id,
            workflow_version=1,
            status=RunStatus.SUCCESS if execution.get("status") == "success" else RunStatus.FAILED,
            started_at=wf.created_at,  # Approximate
            trigger_source="schedule",
            error_message=execution.get("error_message"),
        )
        if execution.get("status") == "success":
            run.complete(success=True)
        else:
            run.complete(success=False, error_message=execution.get("error_message"))

        await workflow_db.create_run(run)

    logger.info(
        f"Migrated order {order_id} -> workflow {wf.id} ({len(exec_rows)} executions)",
        component=LogComponent.WORKFLOW,
    )
