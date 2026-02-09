"""
Transcript quality checker for Hestia voice journaling.

Uses the inference client (LLM) to analyze transcripts and flag
potentially misheard or uncertain words. Cross-references against
known entities from memory (calendar event names, contact names,
project names) to improve accuracy.
"""

import json
import re
from typing import List, Optional

from hestia.inference import get_inference_client, Message
from hestia.logging import get_logger, LogComponent

from .models import FlaggedWord, QualityReport, TranscriptSegment


# Prompt for quality checking transcripts
QUALITY_CHECK_PROMPT = """You are a speech-to-text quality checker. Analyze this transcript and identify words that may have been incorrectly transcribed from speech.

Transcript:
{transcript}

{context_section}

Identify words that:
1. Sound like common homophones (e.g., "their/there/they're", "to/too/two")
2. Could be misheard proper nouns (names, places, brands)
3. Are uncommon words that might be misheard versions of common words
4. Lack context or seem out of place in the sentence
5. Could be a different word that sounds similar

For each flagged word, provide:
- The word as it appears
- Its character position in the transcript (0-indexed)
- How confident you are it's incorrect (0.0 = probably fine, 1.0 = definitely wrong)
- Alternative suggestions (2-3 most likely corrections)
- The reason for flagging

Respond with ONLY this JSON:
{{
    "flagged_words": [
        {{
            "word": "example",
            "position": 42,
            "confidence": 0.7,
            "suggestions": ["correct1", "correct2"],
            "reason": "homophone"
        }}
    ],
    "overall_confidence": 0.85
}}

If the transcript looks correct with no issues, respond with:
{{
    "flagged_words": [],
    "overall_confidence": 0.95
}}"""


# Threshold below which we flag the report as needing review
REVIEW_CONFIDENCE_THRESHOLD = 0.8

# Singleton instance
_quality_checker: Optional["TranscriptQualityChecker"] = None


class TranscriptQualityChecker:
    """
    Checks transcript quality using LLM analysis.

    Cross-references known entities from memory to catch
    misheard proper nouns and domain-specific terms.
    """

    def __init__(self) -> None:
        """Initialize quality checker."""
        self.logger = get_logger()

    async def check(
        self,
        transcript: str,
        segments: Optional[List[TranscriptSegment]] = None,
        known_entities: Optional[List[str]] = None,
    ) -> QualityReport:
        """
        Quality check a transcript using LLM analysis.

        Args:
            transcript: The full transcript text to check.
            segments: Optional segment-level data with per-segment confidence.
            known_entities: Optional list of known entity names
                (people, calendar events, projects) to help catch misheard proper nouns.

        Returns:
            QualityReport with flagged words and confidence scores.
        """
        if not transcript.strip():
            return QualityReport(
                transcript=transcript,
                overall_confidence=1.0,
                needs_review=False,
            )

        try:
            # Build context section from known entities
            context_section = self._build_context_section(known_entities)

            # Build the prompt
            prompt = QUALITY_CHECK_PROMPT.format(
                transcript=transcript[:3000],  # Limit length
                context_section=context_section,
            )

            # Call inference
            client = get_inference_client()
            response = await client.complete(
                prompt=prompt,
                temperature=0.0,  # Deterministic
                max_tokens=1000,
                validate=False,  # JSON response may not look like normal text
            )

            # Parse the LLM response
            report = self._parse_response(transcript, response.content)

            self.logger.info(
                "Quality check complete",
                component=LogComponent.VOICE,
                data={
                    "transcript_length": len(transcript),
                    "flagged_count": len(report.flagged_words),
                    "overall_confidence": report.overall_confidence,
                    "needs_review": report.needs_review,
                },
            )

            return report

        except Exception as e:
            self.logger.warning(
                f"Quality check failed, returning unchecked transcript: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            # On failure, return the transcript as-is with moderate confidence
            return QualityReport(
                transcript=transcript,
                overall_confidence=0.7,
                needs_review=True,
            )

    def _build_context_section(self, known_entities: Optional[List[str]]) -> str:
        """Build context section for the quality check prompt."""
        if not known_entities:
            return ""

        # Limit to 50 entities to avoid bloating the prompt
        entities = known_entities[:50]
        entity_list = ", ".join(entities)
        return (
            f"Known entities (names, events, projects the user frequently references):\n"
            f"{entity_list}\n\n"
            f"If a word in the transcript sounds like one of these entities but is "
            f"slightly different, it's likely a transcription error.\n"
        )

    def _parse_response(self, transcript: str, response_text: str) -> QualityReport:
        """
        Parse the LLM response into a QualityReport.

        Args:
            transcript: Original transcript.
            response_text: LLM response text (expected JSON).

        Returns:
            QualityReport parsed from the response.
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = self._extract_json(response_text)
            data = json.loads(json_text)

            flagged_words = []
            for fw_data in data.get("flagged_words", []):
                flagged_words.append(FlaggedWord.from_dict(fw_data))

            overall_confidence = data.get("overall_confidence", 0.9)

            # Validate positions are within transcript bounds
            flagged_words = [
                fw for fw in flagged_words
                if 0 <= fw.position < len(transcript)
            ]

            needs_review = (
                overall_confidence < REVIEW_CONFIDENCE_THRESHOLD
                or len(flagged_words) > 0
            )

            return QualityReport(
                transcript=transcript,
                flagged_words=flagged_words,
                overall_confidence=overall_confidence,
                needs_review=needs_review,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.warning(
                f"Failed to parse quality check response: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            # Return with moderate confidence on parse failure
            return QualityReport(
                transcript=transcript,
                overall_confidence=0.7,
                needs_review=True,
            )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # Try to find raw JSON object
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            return brace_match.group(0)

        return text.strip()


def get_quality_checker() -> TranscriptQualityChecker:
    """Get or create the singleton quality checker instance."""
    global _quality_checker
    if _quality_checker is None:
        _quality_checker = TranscriptQualityChecker()
    return _quality_checker
