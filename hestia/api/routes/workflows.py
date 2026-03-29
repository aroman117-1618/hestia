"""
Workflow API routes — CRUD, lifecycle, execution, refinement, SSE streaming.

19 endpoints under /v1/workflows.
"""

import asyncio
import json as json_mod
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.inference import InferenceClient
from hestia.logging import get_logger, LogComponent
from hestia.memory.manager import get_memory_manager
from hestia.user.config_loader import get_user_config_loader
from hestia.user.config_models import UserConfigFile
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


class RefinePromptRequest(BaseModel):
    prompt: str = Field(...)
    inference_route: str = Field("", pattern="^(|local|smart_cloud|full_cloud)$")


class PromptVariationSchema(BaseModel):
    label: str
    prompt: str
    explanation: str
    model_suitability: str


class RefinePromptResponse(BaseModel):
    variations: List[PromptVariationSchema]
    context_used: List[str]


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


def get_inference_client() -> InferenceClient:
    """Get inference client singleton for refinement."""
    from hestia.inference.client import get_inference_client as _get_client

    return _get_client()


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
    """Manually trigger a workflow execution.

    Creates the run record and returns immediately. Execution proceeds
    in the background — the client can poll /runs or listen to SSE for updates.
    """
    try:
        manager = await get_workflow_manager()
        run = await manager.create_run(workflow_id, trigger_source="manual")

        # Fire execution in background — don't block the HTTP response
        async def _background_execute() -> None:
            try:
                await manager.execute_run(run)
            except Exception as exc:
                logger.error(
                    "Background workflow execution failed",
                    component=LogComponent.WORKFLOW,
                    data={"run_id": run.id, "error": sanitize_for_log(exc)},
                )

        asyncio.create_task(_background_execute())

        return {
            "run": run.to_dict(),
            "message": "Run started",
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


@router.get("/{workflow_id}/runs/{run_id}")
async def get_run_detail(
    workflow_id: str,
    run_id: str,
    _token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get run detail with per-node execution data."""
    manager = await get_workflow_manager()
    detail = await manager.get_run_detail(run_id)
    if not detail:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return {"run": detail}


# ── Prompt Refinement ────────────────────────────────────────────────


_REFINE_SYSTEM_PROMPT = """\
You are a prompt engineering expert for Hestia, a personal AI assistant.

Your task: take the user's raw workflow prompt and produce 2-3 improved variations.

## Context About the User
{user_context}

## Relevant Memories
{memory_context}

## Target Inference
The prompt will execute on: {inference_target}
- "local" = Qwen 3.5 9B, 32K context — keep prompts concise, structured, avoid broad file scanning
- "smart_cloud" = local-first with cloud fallback — moderate complexity is fine
- "full_cloud" = Anthropic/OpenAI, 200K context — can handle rich, detailed prompts

## Instructions
1. Analyze the prompt for: vague scope, missing output format, context overflow risk, missed personalization opportunities
2. Generate 2-3 variations with different strategies (e.g., Focused, Thorough, Structured)
3. For each variation, consider the user's priorities, projects, and preferences from the context above
4. Tag each with model_suitability: "cloud_optimized", "local_friendly", or "universal"

Return ONLY valid JSON in this exact format:
{{"variations": [
  {{"label": "...", "prompt": "...", "explanation": "...", "model_suitability": "..."}},
  ...
]}}"""


@router.post("/refine-prompt")
async def refine_prompt(
    request: RefinePromptRequest,
    _token: str = Depends(get_device_token),
) -> JSONResponse:
    """Refine a workflow prompt using local inference with personal context."""
    if not request.prompt.strip():
        return JSONResponse(status_code=400, content={"error": "Prompt cannot be empty"})

    context_used: List[str] = []

    # Load full user profile (safe — local inference only)
    user_context = ""
    try:
        loader = await get_user_config_loader()
        user_config = await loader.load()
        user_context = user_config.context_block
        # Add topic files for richer context
        topic_ctx = user_config.get_topic_context([
            UserConfigFile.BODY, UserConfigFile.SPIRIT, UserConfigFile.VITALS,
        ])
        if topic_ctx:
            user_context = f"{user_context}\n\n{topic_ctx}" if user_context else topic_ctx
        if user_context:
            context_used.append("user_profile")
    except Exception as e:
        logger.warning(
            f"Failed to load user profile for refinement: {type(e).__name__}",
            component=LogComponent.WORKFLOW,
        )

    # Search memory for relevant context
    memory_context = ""
    try:
        mem_manager = await get_memory_manager()
        results = await mem_manager.search(request.prompt, limit=5)
        if results:
            memory_context = "\n".join(
                f"- {r.content}" for r in results
            )
            context_used.append("memory")
    except Exception as e:
        logger.warning(
            f"Failed to search memory for refinement: {type(e).__name__}",
            component=LogComponent.WORKFLOW,
        )

    # Build system prompt
    inference_target = request.inference_route or "smart_cloud"
    system = _REFINE_SYSTEM_PROMPT.format(
        user_context=user_context or "(No user profile loaded)",
        memory_context=memory_context or "(No relevant memories found)",
        inference_target=inference_target,
    )

    # Call local inference
    try:
        inference = get_inference_client()
        response = await inference.complete(
            prompt=f"Refine this workflow prompt:\n\n{request.prompt}",
            system=system,
            force_tier="primary",
            format="json",
            temperature=0.7,
            max_tokens=2048,
        )
    except Exception as e:
        logger.error(
            f"Refinement inference failed: {type(e).__name__}",
            component=LogComponent.WORKFLOW,
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Refinement requires local inference", "detail": type(e).__name__},
        )

    # Parse response
    variations = []
    try:
        parsed = json_mod.loads(response.content)
        raw_variations = parsed.get("variations", [])
        for v in raw_variations:
            variations.append({
                "label": v.get("label", "Improved"),
                "prompt": v.get("prompt", ""),
                "explanation": v.get("explanation", ""),
                "model_suitability": v.get("model_suitability", "universal"),
            })
    except (json_mod.JSONDecodeError, KeyError, TypeError):
        # Fallback: treat entire response as single improved prompt
        variations.append({
            "label": "Improved",
            "prompt": response.content.strip(),
            "explanation": "Direct refinement from local model.",
            "model_suitability": "universal",
        })

    if not variations:
        variations.append({
            "label": "Improved",
            "prompt": request.prompt,
            "explanation": "No refinements generated.",
            "model_suitability": "universal",
        })

    return JSONResponse(content={
        "variations": variations,
        "context_used": context_used,
    })


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
