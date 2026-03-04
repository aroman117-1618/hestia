"""
File API routes.

Endpoints for browsing, reading, creating, updating, deleting, and
moving user files, plus an audit trail endpoint.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from hestia.api.middleware.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.files import get_file_manager, PathValidationError
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/files", tags=["files"])
logger = get_logger()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class FileEntryResponse(BaseModel):
    """A single file or directory entry."""
    name: str
    path: str
    type: str
    size: int
    modified: str
    mime_type: Optional[str] = None
    is_hidden: bool = False
    extension: Optional[str] = None


class FileListResponse(BaseModel):
    """Paginated list of file entries."""
    files: List[FileEntryResponse]
    path: str
    parent_path: Optional[str] = None
    total: int


class FileContentResponse(BaseModel):
    """Text content of a file."""
    content: str
    mime_type: str
    size: int
    modified: str
    encoding: str = "utf-8"


class FileCreateRequest(BaseModel):
    """Request to create a new file or directory."""
    path: str = Field(..., description="Parent directory path")
    name: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    type: str = Field(default="file", pattern=r"^(file|directory)$")


class FileUpdateRequest(BaseModel):
    """Request to update file content."""
    content: str


class FileMoveRequest(BaseModel):
    """Request to move/rename a file."""
    source: str
    destination: str


class FileDeleteResponse(BaseModel):
    """Response after deleting a file."""
    deleted: bool
    moved_to_trash: bool


class AuditLogEntryResponse(BaseModel):
    """A single audit log entry."""
    id: str
    operation: str
    path: str
    result: str
    timestamp: str
    destination_path: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""
    logs: List[AuditLogEntryResponse]
    count: int


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "/",
    response_model=FileListResponse,
    summary="List directory",
    description="List files and directories at the given path.",
)
async def list_directory(
    path: str = Query(..., description="Directory path to list"),
    show_hidden: bool = Query(False),
    sort_by: str = Query("name", pattern=r"^(name|date|size|type)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_device_token),
):
    """List files in a directory."""
    manager = await get_file_manager()
    try:
        entries, parent_path = await manager.list_directory(
            path=path,
            user_id=device_id,
            device_id=device_id,
            show_hidden=show_hidden,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )
        return FileListResponse(
            files=[FileEntryResponse(**e.to_dict()) for e in entries],
            path=path,
            parent_path=parent_path,
            total=len(entries),
        )
    except PathValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    except Exception as e:
        logger.error(
            f"File list failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list directory",
        )


@router.get(
    "/content",
    response_model=FileContentResponse,
    summary="Read file content",
    description="Read the text content of a file.",
)
async def read_content(
    path: str = Query(..., description="File path to read"),
    device_id: str = Depends(get_device_token),
):
    """Read text file content."""
    manager = await get_file_manager()
    try:
        content, mime_type, size = await manager.read_content(
            path=path,
            user_id=device_id,
            device_id=device_id,
        )
        # Get modified timestamp from metadata
        entry = await manager.get_metadata(
            path=path,
            user_id=device_id,
            device_id=device_id,
        )
        return FileContentResponse(
            content=content,
            mime_type=mime_type,
            size=size,
            modified=entry.modified.isoformat(),
        )
    except PathValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    except Exception as e:
        logger.error(
            f"File read failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read file",
        )


@router.get(
    "/metadata",
    response_model=FileEntryResponse,
    summary="Get file metadata",
    description="Get metadata for a file or directory without reading content.",
)
async def get_metadata(
    path: str = Query(..., description="File or directory path"),
    device_id: str = Depends(get_device_token),
):
    """Get file or directory metadata."""
    manager = await get_file_manager()
    try:
        entry = await manager.get_metadata(
            path=path,
            user_id=device_id,
            device_id=device_id,
        )
        return FileEntryResponse(**entry.to_dict())
    except PathValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    except Exception as e:
        logger.error(
            f"Metadata fetch failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metadata",
        )


@router.post(
    "/",
    response_model=FileEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create file or directory",
    description="Create a new file or directory at the given path.",
)
async def create_file(
    request: FileCreateRequest,
    device_id: str = Depends(get_device_token),
):
    """Create a new file or directory."""
    manager = await get_file_manager()
    try:
        entry = await manager.create_file(
            parent_path=request.path,
            name=request.name,
            user_id=device_id,
            device_id=device_id,
            content=request.content,
            file_type=request.type,
        )
    except PathValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    except Exception as e:
        logger.error(
            f"File create failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create file",
        )

    logger.info(
        "File created via API",
        component=LogComponent.FILE,
        data={"path": request.path, "name": request.name, "type": request.type},
    )

    return FileEntryResponse(**entry.to_dict())


@router.put(
    "/",
    response_model=FileEntryResponse,
    summary="Update file content",
    description="Update the content of an existing file.",
)
async def update_file(
    path: str = Query(..., description="File path to update"),
    request: FileUpdateRequest = ...,
    device_id: str = Depends(get_device_token),
):
    """Update an existing file's content."""
    manager = await get_file_manager()
    try:
        entry = await manager.update_file(
            path=path,
            content=request.content,
            user_id=device_id,
            device_id=device_id,
        )
    except PathValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    except Exception as e:
        logger.error(
            f"File update failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update file",
        )

    logger.info(
        "File updated via API",
        component=LogComponent.FILE,
        data={"path": path},
    )

    return FileEntryResponse(**entry.to_dict())


@router.delete(
    "/",
    response_model=FileDeleteResponse,
    summary="Delete file",
    description="Soft-delete a file by moving it to the trash directory.",
)
async def delete_file(
    path: str = Query(..., description="File path to delete"),
    device_id: str = Depends(get_device_token),
):
    """Delete a file (moves to trash)."""
    manager = await get_file_manager()
    try:
        deleted, trash_path = await manager.delete_file(
            path=path,
            user_id=device_id,
            device_id=device_id,
        )
    except PathValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    except Exception as e:
        logger.error(
            f"File delete failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        )

    logger.info(
        "File deleted via API",
        component=LogComponent.FILE,
        data={"path": path},
    )

    return FileDeleteResponse(deleted=deleted, moved_to_trash=True)


@router.put(
    "/move",
    response_model=FileEntryResponse,
    summary="Move or rename file",
    description="Move or rename a file or directory.",
)
async def move_file(
    request: FileMoveRequest,
    device_id: str = Depends(get_device_token),
):
    """Move or rename a file."""
    manager = await get_file_manager()
    try:
        entry = await manager.move_file(
            source=request.source,
            destination=request.destination,
            user_id=device_id,
            device_id=device_id,
        )
    except PathValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    except Exception as e:
        logger.error(
            f"File move failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to move file",
        )

    logger.info(
        "File moved via API",
        component=LogComponent.FILE,
        data={"source": request.source, "destination": request.destination},
    )

    return FileEntryResponse(**entry.to_dict())


@router.get(
    "/audit-log",
    response_model=AuditLogListResponse,
    summary="Get audit log",
    description="Get the audit trail of file operations.",
)
async def get_audit_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    operation: Optional[str] = Query(None, description="Filter by operation type"),
    device_id: str = Depends(get_device_token),
):
    """Get file operation audit trail."""
    manager = await get_file_manager()
    try:
        logs = await manager.get_audit_logs(
            user_id=device_id,
            limit=limit,
            offset=offset,
            operation=operation,
        )
        return AuditLogListResponse(
            logs=[
                AuditLogEntryResponse(
                    id=log["id"],
                    operation=log["operation"],
                    path=log["path"],
                    result=log["result"],
                    timestamp=log["timestamp"],
                    destination_path=log.get("destination_path"),
                    metadata=log.get("metadata", {}),
                )
                for log in logs
            ],
            count=len(logs),
        )
    except Exception as e:
        logger.error(
            f"Audit log fetch failed: {sanitize_for_log(e)}",
            component=LogComponent.FILE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch audit log",
        )
