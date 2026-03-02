"""
Mode management routes for Hestia API.

Handles persona mode switching and information.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from hestia.api.errors import sanitize_for_log
from hestia.api.schemas import (
    ModeResponse,
    ModeEnum,
    ModeSwitchRequest,
    ModeSwitchResponse,
    PersonaInfo,
    ErrorResponse,
)
from hestia.api.middleware.auth import get_device_token
from hestia.orchestration.mode import get_mode_manager, Mode
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/mode", tags=["mode"])
logger = get_logger()


def _mode_to_enum(mode: Mode) -> ModeEnum:
    """Convert internal Mode to API ModeEnum."""
    return ModeEnum(mode.value)


def _enum_to_mode(mode_enum: ModeEnum) -> Mode:
    """Convert API ModeEnum to internal Mode."""
    return Mode(mode_enum.value)


def _persona_to_info(persona_dict: dict) -> PersonaInfo:
    """Convert persona dict to PersonaInfo schema."""
    return PersonaInfo(
        mode=ModeEnum(persona_dict["mode"]),
        name=persona_dict["name"],
        full_name=persona_dict["full_name"],
        description=persona_dict["description"],
        traits=persona_dict["traits"],
    )


@router.get(
    "",
    response_model=ModeResponse,
    summary="Get current mode",
    description="Get the current active mode and list of available modes."
)
async def get_current_mode(
    device_id: str = Depends(get_device_token),
) -> ModeResponse:
    """
    Get current mode information.

    Returns the currently active persona and a list of all available modes.
    """
    mode_manager = get_mode_manager()

    current_persona = mode_manager.get_persona_info()

    return ModeResponse(
        current=_persona_to_info(current_persona),
        available=[ModeEnum.TIA, ModeEnum.MIRA, ModeEnum.OLLY],
    )


@router.post(
    "/switch",
    response_model=ModeSwitchResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid mode"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="Switch mode",
    description="Switch to a different persona mode."
)
async def switch_mode(
    request: ModeSwitchRequest,
    device_id: str = Depends(get_device_token),
) -> ModeSwitchResponse:
    """
    Switch to a different mode.

    Available modes:
    - tia: Default mode for daily operations and quick queries
    - mira: Learning mode for Socratic teaching and research
    - olly: Project mode for focused development work

    Args:
        request: ModeSwitchRequest with target mode.
        device_id: Device ID from authentication token.

    Returns:
        ModeSwitchResponse with previous and new mode information.
    """
    mode_manager = get_mode_manager()

    try:
        target_mode = _enum_to_mode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_mode",
                "message": f"Invalid mode: {request.mode}. Must be one of: tia, mira, olly"
            }
        )

    previous_mode = mode_manager.current_mode
    mode_manager.switch_mode(target_mode)

    new_persona = mode_manager.get_persona_info(target_mode)

    logger.info(
        "Mode switched",
        component=LogComponent.API,
        data={
            "device_id": device_id,
            "previous_mode": previous_mode.value,
            "new_mode": target_mode.value,
        }
    )

    return ModeSwitchResponse(
        previous_mode=_mode_to_enum(previous_mode),
        current_mode=_mode_to_enum(target_mode),
        persona=_persona_to_info(new_persona),
    )


@router.get(
    "/{mode_name}",
    response_model=PersonaInfo,
    responses={
        404: {"model": ErrorResponse, "description": "Mode not found"},
    },
    summary="Get mode details",
    description="Get detailed information about a specific mode."
)
async def get_mode_details(
    mode_name: str,
    device_id: str = Depends(get_device_token),
) -> PersonaInfo:
    """
    Get details about a specific mode.

    Args:
        mode_name: Name of the mode (tia, mira, olly).
        device_id: Device ID from authentication token.

    Returns:
        PersonaInfo with mode details.
    """
    mode_manager = get_mode_manager()

    try:
        mode = Mode(mode_name.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "mode_not_found",
                "message": f"Mode '{mode_name}' not found. Available modes: tia, mira, olly"
            }
        )

    persona = mode_manager.get_persona_info(mode)
    return _persona_to_info(persona)
