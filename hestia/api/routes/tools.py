"""
Tools routes for Hestia API.

Lists available tools and their definitions.
"""

from fastapi import APIRouter, Depends

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


@router.get(
    "",
    response_model=ToolsResponse,
    summary="List available tools",
    description="Get a list of all available tools and their definitions."
)
async def list_tools(
    device_id: str = Depends(get_device_token),
) -> ToolsResponse:
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
    List all tool categories with tool counts.

    Returns a dictionary mapping category names to the number of
    tools in each category.
    """
    registry = get_tool_registry()

    categories = {}
    for tool in registry.list_tools():
        category = tool.category
        if category not in categories:
            categories[category] = {
                "count": 0,
                "tools": [],
            }
        categories[category]["count"] += 1
        categories[category]["tools"].append(tool.name)

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
    device_id: str = Depends(get_device_token),
) -> ToolDefinition:
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
    from fastapi import HTTPException, status

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
            enum_values=param.enum_values,
        )

    return ToolDefinition(
        name=tool.name,
        description=tool.description,
        category=tool.category,
        requires_approval=tool.requires_approval,
        parameters=params,
    )
