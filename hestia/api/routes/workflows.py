"""
Workflow API routes — CRUD, lifecycle, execution, SSE streaming.

15 endpoints under /v1/workflows.
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.logging import get_logger, LogComponent
from hestia.workflows.manager import get_workflow_manager
from hestia.workflows.scheduler import get_workflow_scheduler

logger = get_logger()

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


# ── Schemas ──────────────────────────────────────────────────────────


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    trigger_type: str = Field("manual", pattern="^(manual|schedule)$")
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    session_strategy: str = Field("ephemeral", pattern="^(ephemeral|per_run|persistent)$")


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    trigger_type: Optional[str] = Field(None, pattern="^(manual|schedule)$")
    trigger_config: Optional[Dict[str, Any]] = None
    session_strategy: Optional[str] = Field(None, pattern="^(ephemeral|per_run|persistent)$")


class NodeCreateRequest(BaseModel):
    node_type: str = Field(...)
    label: str = Field("Untitled", max_length=200)
    config: Dict[str, Any] = Field(default_factory=dict)
    position_x: float = Field(0.0)
    position_y: float = Field(0.0)


class NodeUpdateRequest(BaseModel):
    label: Optional[str] = Field(None, max_length=200)
    config: Optional[Dict[str, Any]] = None
    node_type: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class EdgeCreateRequest(BaseModel):
    source_node_id: str = Field(...)
    target_node_id: str = Field(...)
    edge_label: str = Field("")


class LayoutUpdateRequest(BaseModel):
    positions: List[Dict[str, Any]] = Field(
        ..., description="List of {node_id, position_x, position_y}"
    )


class StepCreateRequest(BaseModel):
    """A user-facing 'Step' that compiles to one or more backend DAG nodes."""

    title: str
    prompt: Optional[str] = None
    trigger: str = Field("immediate", description="immediate or delay")
    delay_seconds: Optional[float] = None
    resources: Optional[List[str]] = None  # Category IDs: ["calendar", "mail"]
    position_x: float = Field(0.0)
    position_y: float = Field(0.0)
    after_node_id: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────


def _expand_resource_categories(categories: List[str]) -> List[str]:
    """Expand resource category IDs to individual tool names."""
    from hestia.execution import get_tool_registry

    registry = get_tool_registry()
    tool_names = []
    for cat in categories:
        tools = registry.get_tools_by_category(cat)
        tool_names.extend(t.name for t in tools)
    return tool_names


# ── Workflow CRUD ────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_workflow(
    request: WorkflowCreateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Create a new workflow."""
    try:
        manager = await get_workflow_manager()
        wf = await manager.create_workflow(
            name=request.name,
            description=request.description,
            trigger_type=request.trigger_type,
            trigger_config=request.trigger_config,
            session_strategy=request.session_strategy,
        )
        return {"workflow": wf.to_dict()}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(
            "Failed to create workflow",
            component=LogComponent.WORKFLOW,
            data={"error": sanitize_for_log(e)},
        )
        return JSONResponse({"error": "Failed to create workflow"}, status_code=500)


@router.get("")
async def list_workflows(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List workflows with optional status filter."""
    manager = await get_workflow_manager()
    workflows, total = await manager.list_workflows(status, limit, offset)
    return {
        "workflows": [wf.to_dict() for wf in workflows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get workflow detail with nodes and edges."""
    manager = await get_workflow_manager()
    detail = await manager.get_workflow_detail(workflow_id)
    if not detail:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)
    return {"workflow": detail}


@router.patch("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    request: WorkflowUpdateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Update workflow metadata."""
    try:
        manager = await get_workflow_manager()
        kwargs = {k: v for k, v in request.model_dump().items() if v is not None}
        updated = await manager.update_workflow(workflow_id, **kwargs)
        if not updated:
            return JSONResponse({"error": "Workflow not found"}, status_code=404)
        return {"workflow": updated.to_dict()}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.patch("/{workflow_id}/layout")
async def batch_update_layout(
    workflow_id: str,
    request: LayoutUpdateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Batch update node positions (from canvas drag operations)."""
    try:
        manager = await get_workflow_manager()
        updated = await manager.batch_update_layout(workflow_id, request.positions)
        return {"updated": updated, "workflow_id": workflow_id}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        logger.error(
            "Failed to update layout",
            component=LogComponent.WORKFLOW,
            data={"error": sanitize_for_log(e)},
        )
        return JSONResponse({"error": "Failed to update layout"}, status_code=500)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Delete a workflow and all its nodes, edges, and runs."""
    manager = await get_workflow_manager()
    scheduler = await get_workflow_scheduler()
    scheduler.unschedule_workflow(workflow_id)
    deleted = await manager.delete_workflow(workflow_id)
    if not deleted:
        return JSONResponse({"error": "Workflow not found"}, status_code=404)
    return {"workflow_id": workflow_id, "deleted": True}


# ── Step-to-DAG Translation ──────────────────────────────────────────


@router.post("/{workflow_id}/nodes/from-step")
async def create_node_from_step(
    workflow_id: str,
    request: StepCreateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Create workflow node(s) from a user-facing Step definition."""
    if not request.prompt:
        return JSONResponse({"error": "Step must have a prompt"}, status_code=400)

    manager = await get_workflow_manager()
    created_nodes: List[Dict[str, Any]] = []
    created_edges: List[Dict[str, Any]] = []

    # Resolve resource categories → tool names
    allowed_tools = None
    if request.resources:
        allowed_tools = _expand_resource_categories(request.resources)

    pos_x = request.position_x
    pos_y = request.position_y
    first_node_id: Optional[str] = None

    # If delayed trigger, insert a DELAY node first
    if request.trigger == "delay" and request.delay_seconds:
        delay_node = await manager.add_node(
            workflow_id=workflow_id,
            node_type="delay",
            label=f"Wait {int(request.delay_seconds)}s",
            config={"delay_seconds": request.delay_seconds},
            position_x=pos_x,
            position_y=pos_y,
        )
        created_nodes.append(delay_node.to_dict())
        first_node_id = delay_node.id
        pos_y += 150

    # Create the main run_prompt node
    prompt_config: Dict[str, Any] = {"prompt": request.prompt}
    if allowed_tools:
        prompt_config["allowed_tools"] = allowed_tools

    prompt_node = await manager.add_node(
        workflow_id=workflow_id,
        node_type="run_prompt",
        label=request.title,
        config=prompt_config,
        position_x=pos_x,
        position_y=pos_y,
    )
    created_nodes.append(prompt_node.to_dict())

    # Connect delay → prompt if delay was created
    if first_node_id:
        edge = await manager.add_edge(
            workflow_id=workflow_id,
            source_node_id=first_node_id,
            target_node_id=prompt_node.id,
        )
        created_edges.append(edge.to_dict())
    else:
        first_node_id = prompt_node.id

    # Connect after_node → first new node
    if request.after_node_id:
        edge = await manager.add_edge(
            workflow_id=workflow_id,
            source_node_id=request.after_node_id,
            target_node_id=first_node_id,
        )
        created_edges.append(edge.to_dict())

    return {
        "nodes": created_nodes,
        "edges": created_edges,
    }


# ── Node CRUD ────────────────────────────────────────────────────────


@router.post("/{workflow_id}/nodes", status_code=201)
async def add_node(
    workflow_id: str,
    request: NodeCreateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Add a node to a workflow."""
    try:
        manager = await get_workflow_manager()
        node = await manager.add_node(
            workflow_id=workflow_id,
            node_type=request.node_type,
            label=request.label,
            config=request.config,
            position_x=request.position_x,
            position_y=request.position_y,
        )
        return {"node": node.to_dict()}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.patch("/{workflow_id}/nodes/{node_id}")
async def update_node(
    workflow_id: str,
    node_id: str,
    request: NodeUpdateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Update a node's config, label, or position."""
    try:
        manager = await get_workflow_manager()
        kwargs = {k: v for k, v in request.model_dump().items() if v is not None}
        updated = await manager.update_node(node_id, **kwargs)
        if not updated:
            return JSONResponse({"error": "Node not found"}, status_code=404)
        return {"node": updated.to_dict()}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.delete("/{workflow_id}/nodes/{node_id}")
async def delete_node(
    workflow_id: str,
    node_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Delete a node (cascades edges)."""
    manager = await get_workflow_manager()
    deleted = await manager.delete_node(node_id)
    if not deleted:
        return JSONResponse({"error": "Node not found"}, status_code=404)
    return {"node_id": node_id, "deleted": True}


# ── Edge CRUD ────────────────────────────────────────────────────────


@router.post("/{workflow_id}/edges", status_code=201)
async def add_edge(
    workflow_id: str,
    request: EdgeCreateRequest,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Add an edge (validates no cycle)."""
    try:
        manager = await get_workflow_manager()
        edge = await manager.add_edge(
            workflow_id=workflow_id,
            source_node_id=request.source_node_id,
            target_node_id=request.target_node_id,
            edge_label=request.edge_label,
        )
        return {"edge": edge.to_dict()}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.delete("/{workflow_id}/edges/{edge_id}")
async def delete_edge(
    workflow_id: str,
    edge_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Delete an edge."""
    manager = await get_workflow_manager()
    deleted = await manager.delete_edge(edge_id)
    if not deleted:
        return JSONResponse({"error": "Edge not found"}, status_code=404)
    return {"edge_id": edge_id, "deleted": True}


# ── Lifecycle ────────────────────────────────────────────────────────


@router.post("/{workflow_id}/activate")
async def activate_workflow(
    workflow_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Activate a workflow — snapshots version and enables scheduling."""
    try:
        manager = await get_workflow_manager()
        scheduler = await get_workflow_scheduler()
        wf = await manager.activate(workflow_id)
        if wf.trigger_type.value == "schedule":
            scheduler.schedule_workflow(wf)
        return {"workflow": wf.to_dict(), "message": f"Activated v{wf.version}"}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Deactivate a workflow — stops scheduling."""
    try:
        manager = await get_workflow_manager()
        scheduler = await get_workflow_scheduler()
        wf = await manager.deactivate(workflow_id)
        scheduler.unschedule_workflow(workflow_id)
        return {"workflow": wf.to_dict(), "message": "Deactivated"}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ── Execution ────────────────────────────────────────────────────────


@router.post("/{workflow_id}/trigger")
async def trigger_workflow(
    workflow_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Manually trigger a workflow execution."""
    try:
        manager = await get_workflow_manager()
        run = await manager.trigger(workflow_id, trigger_source="manual")
        return {
            "run": run.to_dict(),
            "message": f"Run {run.status.value}",
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(
            "Workflow trigger failed",
            component=LogComponent.WORKFLOW,
            data={"workflow_id": workflow_id, "error": sanitize_for_log(e)},
        )
        return JSONResponse({"error": "Workflow execution failed"}, status_code=500)


@router.get("/{workflow_id}/runs")
async def list_runs(
    workflow_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List run history for a workflow."""
    manager = await get_workflow_manager()
    runs, total = await manager.list_runs(workflow_id, limit, offset)
    return {
        "runs": [r.to_dict() for r in runs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ── SSE Stream ───────────────────────────────────────────────────────


@router.get("/stream")
async def workflow_stream(
    _token: str = Depends(get_device_token),
) -> StreamingResponse:
    """SSE stream for workflow execution events."""
    manager = await get_workflow_manager()
    event_bus = manager.event_bus
    queue = event_bus.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
