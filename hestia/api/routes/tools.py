"""
Tools routes for Hestia API.

Lists available tools and their definitions.
"""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from hestia.api.etag import etag_response
from hestia.api.errors import sanitize_for_log
from hestia.api.schemas import (
    ToolsResponse,
    ToolDefinition,
    ToolParameter,
)
from hestia.api.middleware.auth import get_device_token
from hestia.execution import get_tool_registry
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/tools", tags=["tools"])
logger = get_logger()

# Human-readable labels and SF Symbol icons for the Step Builder resource picker
TOOL_CATEGORY_META: Dict[str, Dict[str, str]] = {
    "calendar": {"label": "Calendar", "icon": "calendar"},
    "reminders": {"label": "Reminders", "icon": "checklist"},
    "notes": {"label": "Notes", "icon": "note.text"},
    "mail": {"label": "Mail", "icon": "envelope"},
    "file": {"label": "Files", "icon": "folder"},
    "code": {"label": "Code", "icon": "chevron.left.forwardslash.chevron.right"},
    "git": {"label": "Git", "icon": "arrow.triangle.branch"},
    "shell": {"label": "Shell", "icon": "terminal"},
    "health": {"label": "Health", "icon": "heart.fill"},
    "trading": {"label": "Trading", "icon": "chart.line.uptrend.xyaxis"},
    "investigate": {"label": "Web", "icon": "globe"},
    "general": {"label": "General", "icon": "wrench"},
}


@router.get(
    "",
    response_model=ToolsResponse,
    summary="List available tools",
    description="Get a list of all available tools and their definitions."
)
async def list_tools(
    request: Request,
    response: Response,
    device_id: str = Depends(get_device_token),
):
    """
    List all available tools.

    Returns tool definitions including:
    - Name and description
    - Category
    - Required parameters
    - Whether approval is required

    These are the tools that Hestia can use to perform actions.
    """
    registry = get_tool_registry()

    tools = []
    for tool in registry.list_tools():
        # Convert parameters
        params = {}
        for name, param in tool.parameters.items():
            params[name] = ToolParameter(
                type=param.type.value,
                description=param.description,
                required=param.required,
                default=param.default,
                enum_values=param.enum,
            )

        tools.append(ToolDefinition(
            name=tool.name,
            description=tool.description,
            category=tool.category,
            requires_approval=tool.requires_approval,
            parameters=params,
        ))

    logger.debug(
        "Tools listed",
        component=LogComponent.API,
        data={
            "device_id": device_id,
            "tool_count": len(tools),
        }
    )

    # ETag from tool names (static until deploy)
    etag_source = "|".join(t.name for t in tools)
    cached = etag_response(request, response, etag_source)
    if cached:
        return cached

    return ToolsResponse(
        tools=tools,
        count=len(tools),
    )


@router.get(
    "/categories",
    summary="List tool categories",
    description="Get a list of all tool categories."
)
async def list_categories(
    device_id: str = Depends(get_device_token),
) -> dict:
    """
    List all tool categories with tool details, labels, and icons.

    Returns a structured array of categories, each with human-readable
    metadata and full tool schemas for the workflow Step Builder.
    """
    registry = get_tool_registry()

    # Group tools by category
    groups: Dict[str, list] = {}
    for tool in registry.list_tools():
        cat = tool.category or "general"
        if cat not in groups:
            groups[cat] = []
        groups[cat].append({
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                name: param.to_json_schema()
                for name, param in tool.parameters.items()
            },
            "requires_approval": tool.requires_approval,
        })

    # Build response with metadata
    categories = []
    for cat_id, tools in sorted(groups.items()):
        meta = TOOL_CATEGORY_META.get(cat_id, {"label": cat_id.title(), "icon": "wrench"})
        categories.append({
            "id": cat_id,
            "label": meta["label"],
            "icon": meta["icon"],
            "tools": sorted(tools, key=lambda t: t["name"]),
            "count": len(tools),
        })

    return {
        "categories": categories,
        "total_tools": len(registry),
    }


@router.get(
    "/{tool_name}",
    response_model=ToolDefinition,
    summary="Get tool details",
    description="Get detailed information about a specific tool."
)
async def get_tool_details(
    tool_name: str,
    request: Request,
    response: Response,
    device_id: str = Depends(get_device_token),
):
    """
    Get details about a specific tool.

    Args:
        tool_name: Name of the tool.
        device_id: Device ID from authentication token.

    Returns:
        ToolDefinition with full tool details.

    Raises:
        HTTPException: If tool is not found.
    """
    registry = get_tool_registry()

    tool = registry.get(tool_name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "tool_not_found",
                "message": f"Tool '{tool_name}' not found.",
            }
        )

    # Convert parameters
    params = {}
    for name, param in tool.parameters.items():
        params[name] = ToolParameter(
            type=param.type.value,
            description=param.description,
            required=param.required,
            default=param.default,
            enum_values=param.enum,
        )

    # ETag from tool name + parameter count (static until deploy)
    etag_source = f"{tool.name}:{len(params)}"
    cached = etag_response(request, response, etag_source)
    if cached:
        return cached

    return ToolDefinition(
        name=tool.name,
        description=tool.description,
        category=tool.category,
        requires_approval=tool.requires_approval,
        parameters=params,
    )
