"""
V2 Agent Configuration API routes (.md-based system).

Provides CRUD operations for the .md file-based agent config system.
Coexists with v1 routes (routes/agents.py) during migration.

V2 agents are identified by name (directory slug) rather than slot index.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.middleware.auth import get_current_device
from hestia.api.schemas import (
    AgentConfigResponse,
    AgentConfigListResponse,
    AgentCreateRequest,
    AgentConfigFileResponse,
    AgentConfigFileUpdateRequest,
    AgentArchiveResponse,
    AgentIdentityResponse,
    DailyNoteResponse,
    DailyNoteAppendRequest,
)
from hestia.agents.config_loader import get_config_loader
from hestia.agents.config_writer import get_config_writer
from hestia.agents.config_models import (
    AgentConfigFile,
    AGENT_WRITABLE_FILES,
    AGENT_CONFIRM_FILES,
)
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v2/agents", tags=["agents-v2"])
logger = get_logger()


# =============================================================================
# Helper Functions
# =============================================================================

def _config_to_response(config) -> AgentConfigResponse:
    """Convert AgentConfig to API response."""
    d = config.to_dict()
    return AgentConfigResponse(
        directory_name=d["directory_name"],
        name=d["name"],
        identity=AgentIdentityResponse(**d["identity"]),
        is_default=d["is_default"],
        is_archived=d["is_archived"],
        has_bootstrap=d["has_bootstrap"],
        config_version=d["config_version"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        files=d["files"],
    )


# =============================================================================
# Agent CRUD
# =============================================================================

@router.get(
    "",
    response_model=AgentConfigListResponse,
    summary="List all agents",
    description="List all agent configurations from .md file directories.",
)
async def list_agents(
    include_archived: bool = Query(False, description="Include archived agents"),
    _device: str = Depends(get_current_device),
):
    """List all agents."""
    try:
        loader = await get_config_loader()
        agents = await loader.list_agents(include_archived=include_archived)
        registry = await loader.get_registry()

        return AgentConfigListResponse(
            agents=[_config_to_response(a) for a in agents],
            count=len(agents),
            default_agent=registry.default_agent,
        )
    except Exception as e:
        logger.error(f"Failed to list agents: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list agents",
        )


@router.get(
    "/{agent_name}",
    response_model=AgentConfigResponse,
    summary="Get agent details",
    description="Get a single agent's configuration.",
)
async def get_agent(
    agent_name: str,
    _device: str = Depends(get_current_device),
):
    """Get agent by name."""
    try:
        loader = await get_config_loader()
        config = await loader.get_agent(agent_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        return _config_to_response(config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent '{agent_name}': {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent",
        )


@router.post(
    "",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new agent",
    description="Create a new agent with template .md files.",
)
async def create_agent(
    request: AgentCreateRequest,
    _device: str = Depends(get_current_device),
):
    """Create a new agent."""
    try:
        loader = await get_config_loader()
        config = await loader.create_agent(
            name=request.name,
            slug=request.slug,
        )
        return _config_to_response(config)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create agent: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent",
        )


@router.delete(
    "/{agent_name}",
    response_model=AgentArchiveResponse,
    summary="Archive agent",
    description="Archive (soft-delete) an agent. Moves to .archived/ directory.",
)
async def archive_agent(
    agent_name: str,
    _device: str = Depends(get_current_device),
):
    """Archive an agent."""
    try:
        loader = await get_config_loader()
        success = await loader.archive_agent(agent_name)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        return AgentArchiveResponse(
            agent_name=agent_name,
            message=f"Agent '{agent_name}' archived",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to archive agent '{agent_name}': {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive agent",
        )


# =============================================================================
# Config File Operations
# =============================================================================

@router.get(
    "/{agent_name}/config/{file_name}",
    response_model=AgentConfigFileResponse,
    summary="Read config file",
    description="Read a specific .md config file for an agent.",
)
async def get_config_file(
    agent_name: str,
    file_name: str,
    _device: str = Depends(get_current_device),
):
    """Read a config file."""
    try:
        # Validate file name
        try:
            config_file = AgentConfigFile(file_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown config file: {file_name}. Valid files: {[f.value for f in AgentConfigFile]}",
            )

        loader = await get_config_loader()
        config = await loader.get_agent(agent_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        content = config.get_file_content(config_file)

        return AgentConfigFileResponse(
            agent_name=agent_name,
            file_name=file_name,
            content=content,
            writable_by_agent=config_file in AGENT_WRITABLE_FILES,
            requires_confirmation=config_file in AGENT_CONFIRM_FILES,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read config file: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read config file",
        )


@router.put(
    "/{agent_name}/config/{file_name}",
    response_model=AgentConfigFileResponse,
    summary="Update config file",
    description="Update a specific .md config file for an agent.",
)
async def update_config_file(
    agent_name: str,
    file_name: str,
    request: AgentConfigFileUpdateRequest,
    _device: str = Depends(get_current_device),
):
    """Update a config file."""
    try:
        # Validate file name
        try:
            config_file = AgentConfigFile(file_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown config file: {file_name}",
            )

        writer = await get_config_writer()
        await writer.write_config_file(
            agent_name=agent_name,
            config_file=config_file,
            content=request.content,
            source=request.source,
            confirmed=request.confirmed,
        )

        # Reload and return updated content
        loader = await get_config_loader()
        config = await loader.reload_agent(agent_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found after update",
            )

        return AgentConfigFileResponse(
            agent_name=agent_name,
            file_name=file_name,
            content=config.get_file_content(config_file),
            writable_by_agent=config_file in AGENT_WRITABLE_FILES,
            requires_confirmation=config_file in AGENT_CONFIRM_FILES,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_type = type(e).__name__
        if "Permission" in error_type:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )
        logger.error(f"Failed to update config file: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update config file",
        )


# =============================================================================
# Daily Notes
# =============================================================================

@router.get(
    "/{agent_name}/notes",
    response_model=list[DailyNoteResponse],
    summary="List daily notes",
    description="List recent daily notes for an agent.",
)
async def list_daily_notes(
    agent_name: str,
    limit: int = Query(30, ge=1, le=365, description="Max notes to return"),
    _device: str = Depends(get_current_device),
):
    """List daily notes."""
    try:
        writer = await get_config_writer()
        notes = await writer.list_daily_notes(agent_name, limit=limit)

        return [
            DailyNoteResponse(
                date=note.date.isoformat(),
                content=note.content,
                agent_name=note.agent_name,
            )
            for note in notes
        ]
    except Exception as e:
        logger.error(f"Failed to list daily notes: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list daily notes",
        )


@router.get(
    "/{agent_name}/notes/{note_date}",
    response_model=DailyNoteResponse,
    summary="Read daily note",
    description="Read a specific daily note by date.",
)
async def get_daily_note(
    agent_name: str,
    note_date: str,
    _device: str = Depends(get_current_device),
):
    """Read a daily note by date."""
    try:
        parsed_date = date.fromisoformat(note_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {note_date}. Use YYYY-MM-DD.",
        )

    try:
        writer = await get_config_writer()
        note = await writer.read_daily_note(agent_name, note_date=parsed_date)

        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No daily note for {note_date}",
            )

        return DailyNoteResponse(
            date=note.date.isoformat(),
            content=note.content,
            agent_name=note.agent_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read daily note: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read daily note",
        )


@router.post(
    "/{agent_name}/notes",
    response_model=DailyNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append to daily note",
    description="Append an entry to today's daily note (creates if doesn't exist).",
)
async def append_daily_note(
    agent_name: str,
    request: DailyNoteAppendRequest,
    _device: str = Depends(get_current_device),
):
    """Append to today's daily note."""
    try:
        writer = await get_config_writer()
        note = await writer.append_daily_note(
            agent_name=agent_name,
            entry=request.content,
        )

        return DailyNoteResponse(
            date=note.date.isoformat(),
            content=note.content,
            agent_name=note.agent_name,
        )
    except Exception as e:
        logger.error(f"Failed to append daily note: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to append daily note",
        )


# =============================================================================
# Agent Reload
# =============================================================================

@router.post(
    "/{agent_name}/reload",
    response_model=AgentConfigResponse,
    summary="Reload agent config",
    description="Force-reload an agent's configuration from disk.",
)
async def reload_agent(
    agent_name: str,
    _device: str = Depends(get_current_device),
):
    """Force-reload agent from disk."""
    try:
        loader = await get_config_loader()
        config = await loader.reload_agent(agent_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found",
            )

        return _config_to_response(config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reload agent: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reload agent",
        )
