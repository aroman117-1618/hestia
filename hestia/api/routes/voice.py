"""
Voice journaling routes for Hestia API.

WS2: Voice Journaling — Session 2
Provides REST endpoints for transcript quality checking and journal analysis.

Pipeline:
1. POST /v1/voice/quality-check — LLM flags uncertain words in a transcript
2. POST /v1/voice/journal-analyze — Full analysis: intents, cross-refs, action plan
"""

from fastapi import APIRouter, Depends, HTTPException, status

from hestia.api.schemas import (
    VoiceFlaggedWord,
    VoiceQualityCheckRequest,
    VoiceQualityCheckResponse,
    VoiceJournalIntent,
    VoiceIntentType,
    VoiceCrossReference,
    VoiceCrossReferenceSource,
    VoiceActionPlanItem,
    VoiceJournalAnalyzeRequest,
    VoiceJournalAnalyzeResponse,
    ErrorResponse,
)
from hestia.api.middleware.auth import get_device_token
from hestia.logging import get_logger, LogComponent
from hestia.voice import get_quality_checker, get_journal_analyzer

router = APIRouter(prefix="/v1/voice", tags=["voice"])
logger = get_logger()


# ── POST /v1/voice/quality-check ──────────────────────────────────

@router.post(
    "/quality-check",
    response_model=VoiceQualityCheckResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Quality check a transcript",
    description=(
        "Analyze a voice transcript for potentially misheard words. "
        "Uses LLM to flag homophones, misheard proper nouns, and "
        "uncommon words. Optionally cross-references known entities."
    ),
)
async def quality_check(
    request: VoiceQualityCheckRequest,
    device_id: str = Depends(get_device_token),
) -> VoiceQualityCheckResponse:
    """Quality check a voice transcript."""
    try:
        checker = get_quality_checker()
        report = await checker.check(
            transcript=request.transcript,
            known_entities=request.known_entities,
        )

        logger.info(
            "Voice quality check complete",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "transcript_length": len(request.transcript),
                "flagged_count": len(report.flagged_words),
                "overall_confidence": report.overall_confidence,
                "needs_review": report.needs_review,
            },
        )

        return VoiceQualityCheckResponse(
            transcript=report.transcript,
            flagged_words=[
                VoiceFlaggedWord(
                    word=fw.word,
                    position=fw.position,
                    confidence=fw.confidence,
                    suggestions=fw.suggestions,
                    reason=fw.reason,
                )
                for fw in report.flagged_words
            ],
            overall_confidence=report.overall_confidence,
            needs_review=report.needs_review,
        )

    except Exception as e:
        logger.error(
            f"Voice quality check failed: {type(e).__name__}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "quality_check_failed",
                "message": "Failed to quality check transcript.",
            },
        )


# ── POST /v1/voice/journal-analyze ───────────────────────────────

@router.post(
    "/journal-analyze",
    response_model=VoiceJournalAnalyzeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Analyze a journal transcript",
    description=(
        "Run the full journal analysis pipeline on a confirmed transcript. "
        "Extracts intents, cross-references against calendar/mail/memory/reminders, "
        "and generates an action plan with tool call mappings."
    ),
)
async def journal_analyze(
    request: VoiceJournalAnalyzeRequest,
    device_id: str = Depends(get_device_token),
) -> VoiceJournalAnalyzeResponse:
    """Analyze a confirmed journal transcript."""
    try:
        analyzer = get_journal_analyzer()
        analysis = await analyzer.analyze(
            transcript=request.transcript,
            mode=request.mode or "tia",
        )

        logger.info(
            "Voice journal analysis complete",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "analysis_id": analysis.id,
                "intent_count": len(analysis.intents),
                "cross_ref_count": len(analysis.cross_references),
                "action_count": len(analysis.action_plan),
            },
        )

        return VoiceJournalAnalyzeResponse(
            id=analysis.id,
            transcript=analysis.transcript,
            intents=[
                VoiceJournalIntent(
                    id=intent.id,
                    intent_type=VoiceIntentType(intent.intent_type.value),
                    content=intent.content,
                    confidence=intent.confidence,
                    entities=intent.entities,
                )
                for intent in analysis.intents
            ],
            cross_references=[
                VoiceCrossReference(
                    source=VoiceCrossReferenceSource(cr.source.value),
                    match=cr.match,
                    relevance=cr.relevance,
                    details=cr.details,
                )
                for cr in analysis.cross_references
            ],
            action_plan=[
                VoiceActionPlanItem(
                    id=ap.id,
                    action=ap.action,
                    tool_call=ap.tool_call,
                    arguments=ap.arguments,
                    confidence=ap.confidence,
                    intent_id=ap.intent_id,
                )
                for ap in analysis.action_plan
            ],
            summary=analysis.summary,
            timestamp=analysis.timestamp.isoformat(),
        )

    except Exception as e:
        logger.error(
            f"Voice journal analysis failed: {type(e).__name__}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "journal_analysis_failed",
                "message": "Failed to analyze journal transcript.",
            },
        )
