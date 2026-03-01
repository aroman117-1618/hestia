"""
User profile configuration API routes.

Endpoints for managing markdown-based user identity, commands, and daily notes.
All routes require JWT device authentication.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_current_device
from hestia.logging import get_logger
from hestia.user.config_loader import get_user_config_loader
from hestia.user.config_models import UserConfigFile
from hestia.user.config_writer import get_user_config_writer

logger = get_logger()

router = APIRouter(prefix="/v1/user-profile", tags=["user-profile"])


# ─── Request/Response Models ─────────────────────


class UserProfileResponse(BaseModel):
    """Full user profile summary."""
    name: str
    identity: dict
    has_setup: bool
    config_version: str
    created_at: str
    updated_at: str
    files: dict


class FileContentResponse(BaseModel):
    """Content of a single config file."""
    file_name: str
    content: str
    exists: bool


class FileUpdateRequest(BaseModel):
    """Request to update a config file."""
    content: str = Field(..., min_length=0, max_length=50000)
    source: str = Field(default="user", pattern="^(user|agent|system)$")


class CommandResponse(BaseModel):
    """Single command summary."""
    name: str
    description: str
    resources: list
    has_system_instructions: bool


class CommandListResponse(BaseModel):
    """List of available commands."""
    commands: list
    count: int


class DailyNoteResponse(BaseModel):
    """Single daily note."""
    date: str
    content: str


class DailyNoteAppendRequest(BaseModel):
    """Request to append to daily note."""
    content: str = Field(..., min_length=1, max_length=10000)


class CommandCreateRequest(BaseModel):
    """Request to create/update a command."""
    name: str = Field(..., min_length=1, max_length=50, pattern="^[a-z0-9-]+$")
    content: str = Field(..., min_length=1, max_length=50000)


# ─── Profile Endpoints ───────────────────────────


@router.get("", response_model=UserProfileResponse)
async def get_user_profile(
    _device: str = Depends(get_current_device),
) -> UserProfileResponse:
    """Get user profile summary."""
    try:
        loader = await get_user_config_loader()
        config = await loader.load()
        data = config.to_dict()
        return UserProfileResponse(**data)
    except Exception as e:
        logger.error(f"Failed to get user profile: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user profile",
        )


@router.get("/files/{file_name}", response_model=FileContentResponse)
async def get_config_file(
    file_name: str,
    _device: str = Depends(get_current_device),
) -> FileContentResponse:
    """Get content of a specific user profile file."""
    try:
        config_file = _resolve_file_name(file_name)
        loader = await get_user_config_loader()
        config = await loader.load()
        content = config.get_file_content(config_file)

        return FileContentResponse(
            file_name=config_file.value,
            content=content,
            exists=bool(content.strip()),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown file: {file_name}",
        )
    except Exception as e:
        logger.error(f"Failed to read config file: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read file",
        )


@router.put("/files/{file_name}")
async def update_config_file(
    file_name: str,
    request: FileUpdateRequest,
    _device: str = Depends(get_current_device),
) -> dict:
    """Update a user profile file."""
    try:
        config_file = _resolve_file_name(file_name)
        writer = await get_user_config_writer()
        await writer.write_config_file(config_file, request.content, request.source)

        return {"status": "ok", "file_name": config_file.value}
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown file: {file_name}",
        )
    except PermissionError as e:
        logger.warning(f"Permission denied writing {file_name}: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied for this file",
        )
    except Exception as e:
        logger.error(f"Failed to write config file: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write file",
        )


@router.post("/reload")
async def reload_profile(
    _device: str = Depends(get_current_device),
) -> dict:
    """Force-reload user profile from disk."""
    try:
        loader = await get_user_config_loader()
        loader.invalidate_cache()
        loader.invalidate_commands_cache()
        config = await loader.load(force_reload=True)
        return {"status": "ok", "name": config.name}
    except Exception as e:
        logger.error(f"Failed to reload profile: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reload profile",
        )


# ─── Commands Endpoints ──────────────────────────


@router.get("/commands", response_model=CommandListResponse)
async def list_commands(
    _device: str = Depends(get_current_device),
) -> CommandListResponse:
    """List all available commands."""
    try:
        loader = await get_user_config_loader()
        commands = await loader.load_commands()
        return CommandListResponse(
            commands=[cmd.to_dict() for cmd in commands.values()],
            count=len(commands),
        )
    except Exception as e:
        logger.error(f"Failed to list commands: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list commands",
        )


@router.get("/commands/{command_name}")
async def get_command(
    command_name: str,
    _device: str = Depends(get_current_device),
) -> dict:
    """Get a single command with full content."""
    try:
        loader = await get_user_config_loader()
        cmd = await loader.get_command(command_name)
        if cmd is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Command '{command_name}' not found",
            )
        return {
            **cmd.to_dict(),
            "content": cmd.raw_content,
            "system_instructions": cmd.system_instructions,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get command: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get command",
        )


@router.put("/commands/{command_name}")
async def update_command(
    command_name: str,
    request: CommandCreateRequest,
    _device: str = Depends(get_current_device),
) -> dict:
    """Create or update a command."""
    try:
        # Validate reserved names
        reserved = {"chat", "health", "mode", "memory", "session", "tool", "task"}
        if request.name in reserved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Command name '{request.name}' is reserved",
            )

        writer = await get_user_config_writer()
        await writer.write_command(request.name, request.content)
        return {"status": "ok", "name": request.name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to write command: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write command",
        )


@router.delete("/commands/{command_name}")
async def delete_command(
    command_name: str,
    _device: str = Depends(get_current_device),
) -> dict:
    """Delete a command."""
    try:
        writer = await get_user_config_writer()
        deleted = await writer.delete_command(command_name)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Command '{command_name}' not found",
            )
        return {"status": "ok", "name": command_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete command: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete command",
        )


# ─── Daily Notes Endpoints ───────────────────────


@router.get("/notes")
async def list_daily_notes(
    limit: int = 30,
    _device: str = Depends(get_current_device),
) -> dict:
    """List daily notes, most recent first."""
    try:
        loader = await get_user_config_loader()
        notes = await loader.list_daily_notes(limit=limit)
        return {
            "notes": [
                {"date": n.date.isoformat(), "content": n.content}
                for n in notes
            ],
            "count": len(notes),
        }
    except Exception as e:
        logger.error(f"Failed to list daily notes: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list notes",
        )


@router.get("/notes/{note_date}")
async def get_daily_note(
    note_date: str,
    _device: str = Depends(get_current_device),
) -> DailyNoteResponse:
    """Get a specific daily note."""
    try:
        parsed_date = date.fromisoformat(note_date)
        loader = await get_user_config_loader()
        note = await loader.get_daily_note(parsed_date)
        if note is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No note for {note_date}",
            )
        return DailyNoteResponse(date=note.date.isoformat(), content=note.content)
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format (use YYYY-MM-DD)",
        )
    except Exception as e:
        logger.error(f"Failed to read daily note: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read note",
        )


@router.post("/notes")
async def append_daily_note(
    request: DailyNoteAppendRequest,
    note_date: Optional[str] = None,
    _device: str = Depends(get_current_device),
) -> DailyNoteResponse:
    """Append to today's daily note (or specified date)."""
    try:
        parsed_date = date.fromisoformat(note_date) if note_date else date.today()
        writer = await get_user_config_writer()
        note = await writer.append_daily_note(request.content, parsed_date)
        return DailyNoteResponse(date=note.date.isoformat(), content=note.content)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format (use YYYY-MM-DD)",
        )
    except Exception as e:
        logger.error(f"Failed to append daily note: {sanitize_for_log(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to append note",
        )


# ─── Helpers ─────────────────────────────────────


def _resolve_file_name(file_name: str) -> UserConfigFile:
    """Resolve a file name string to UserConfigFile enum."""
    # Accept both "MIND.md" and "MIND" and "mind"
    normalized = file_name.upper()
    if not normalized.endswith(".MD"):
        normalized += ".MD"

    # Handle USER-IDENTITY specially
    if normalized in ("USER-IDENTITY.MD", "IDENTITY.MD", "USER_IDENTITY.MD"):
        return UserConfigFile.IDENTITY

    for cf in UserConfigFile:
        if cf.value.upper() == normalized:
            return cf

    raise ValueError(f"Unknown config file: {file_name}")
