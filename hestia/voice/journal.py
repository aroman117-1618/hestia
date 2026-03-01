"""
Journal analyzer for Hestia voice journaling.

Processes confirmed transcripts through a multi-stage pipeline:
1. Intent extraction (LLM parses structured intents from free-form speech)
2. Cross-referencing (queries calendar, mail, memory, reminders)
3. Action plan generation (LLM maps intents + context to actionable items)
"""

import asyncio
import json
import re
from typing import List, Optional

from hestia.inference import get_inference_client
from hestia.logging import get_logger, LogComponent

from .models import (
    ActionPlanItem,
    CrossReference,
    CrossReferenceSource,
    JournalAnalysis,
    JournalIntent,
)


# Prompt for intent extraction
INTENT_EXTRACTION_PROMPT = """You are a personal assistant analyzing a voice journal entry. Extract all actionable intents from this transcript.

Transcript:
{transcript}

For each intent, identify:
- type: one of "action_item", "reminder", "note", "decision", "reflection", "follow_up"
- content: a concise description of the intent
- confidence: 0.0-1.0 how clear the intent is
- entities: specific names, dates, projects, or things mentioned

Respond with ONLY this JSON:
{{
    "intents": [
        {{
            "intent_type": "action_item",
            "content": "Follow up with contractor about kitchen timeline",
            "confidence": 0.9,
            "entities": ["contractor", "kitchen"]
        }}
    ]
}}"""


# Prompt for action plan generation
ACTION_PLAN_PROMPT = """You are a personal assistant creating an action plan from journal intents and contextual data.

Intents extracted from voice journal:
{intents_json}

Context from cross-referencing:
{context_json}

Available tools:
- create_reminder: Create a reminder (args: title, due_date, list_name, notes)
- create_event: Create a calendar event (args: title, start_date, end_date, location, notes)
- create_note: Create a note (args: title, content, folder)
- search_notes: Search existing notes (args: query)

For each intent, generate an action plan item:
- action: human-readable description
- tool_call: the tool to use (or null if no tool applies)
- arguments: tool arguments as a dict
- confidence: 0.0-1.0
- intent_id: the ID of the related intent

Respond with ONLY this JSON:
{{
    "action_plan": [
        {{
            "action": "Create a reminder to follow up with contractor",
            "tool_call": "create_reminder",
            "arguments": {{"title": "Follow up with contractor - kitchen timeline", "notes": "Check on progress"}},
            "confidence": 0.85,
            "intent_id": "intent-abc123"
        }}
    ],
    "summary": "Brief 1-2 sentence summary of the journal entry and planned actions"
}}"""


# Singleton instance
_journal_analyzer: Optional["JournalAnalyzer"] = None


class JournalAnalyzer:
    """
    Analyzes journal transcripts through a multi-stage pipeline.

    Pipeline:
    1. Extract intents from transcript (LLM)
    2. Cross-reference intents against calendar, mail, memory, reminders
    3. Generate action plan with tool call mappings (LLM)

    All Apple ecosystem queries are wrapped in try/except to gracefully
    handle unavailable services (CLI tools not installed, permissions denied).
    """

    def __init__(self) -> None:
        """Initialize journal analyzer."""
        self.logger = get_logger()

    async def analyze(
        self,
        transcript: str,
        mode: str = "tia",
    ) -> JournalAnalysis:
        """
        Run the full journal analysis pipeline.

        Args:
            transcript: Confirmed transcript text.
            mode: Current Hestia mode (tia/mira/olly).

        Returns:
            JournalAnalysis with intents, cross-references, and action plan.
        """
        analysis = JournalAnalysis.create(transcript)

        try:
            # Stage 1: Extract intents
            intents = await self._extract_intents(transcript)
            analysis.intents = intents

            self.logger.info(
                f"Extracted {len(intents)} intents from journal",
                component=LogComponent.VOICE,
                data={"intent_types": [i.intent_type.value for i in intents]},
            )

            if not intents:
                analysis.summary = "No actionable intents found in journal entry."
                return analysis

            # Stage 2: Cross-reference
            cross_refs = await self._cross_reference(intents)
            analysis.cross_references = cross_refs

            # Stage 3: Generate action plan
            action_plan, summary = await self._generate_action_plan(intents, cross_refs)
            analysis.action_plan = action_plan
            analysis.summary = summary

            self.logger.info(
                "Journal analysis complete",
                component=LogComponent.VOICE,
                data={
                    "intent_count": len(intents),
                    "cross_ref_count": len(cross_refs),
                    "action_count": len(action_plan),
                },
            )

        except Exception as e:
            self.logger.error(
                f"Journal analysis failed: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            analysis.summary = f"Analysis incomplete due to error: {type(e).__name__}"

        return analysis

    async def _extract_intents(self, transcript: str) -> List[JournalIntent]:
        """
        Extract structured intents from transcript using LLM.

        Args:
            transcript: The full transcript text.

        Returns:
            List of extracted JournalIntents.
        """
        prompt = INTENT_EXTRACTION_PROMPT.format(transcript=transcript[:3000])

        client = get_inference_client()
        response = await client.complete(
            prompt=prompt,
            temperature=0.0,
            max_tokens=1500,
            validate=False,
        )

        return self._parse_intents_response(response.content)

    async def _cross_reference(
        self,
        intents: List[JournalIntent],
    ) -> List[CrossReference]:
        """
        Cross-reference intents against calendar, mail, memory, and reminders.

        Runs all queries in parallel for speed. Each source is wrapped
        in try/except to handle unavailable services gracefully.

        Args:
            intents: Extracted intents to cross-reference.

        Returns:
            List of CrossReference matches.
        """
        # Collect all entity names and content for searching
        search_terms = set()
        for intent in intents:
            search_terms.update(intent.entities)
            # Extract key nouns from content (first 3 significant words)
            words = [w for w in intent.content.split() if len(w) > 3]
            search_terms.update(words[:3])

        # Run all cross-reference queries in parallel
        results = await asyncio.gather(
            self._xref_calendar(),
            self._xref_reminders(),
            self._xref_mail(list(search_terms)),
            self._xref_memory(list(search_terms)),
            return_exceptions=True,
        )

        cross_refs: List[CrossReference] = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.warning(
                    f"Cross-reference source failed: {result}",
                    component=LogComponent.VOICE,
                )
                continue
            if isinstance(result, list):
                cross_refs.extend(result)

        return cross_refs

    async def _xref_calendar(self) -> List[CrossReference]:
        """Query today's and upcoming calendar events."""
        try:
            from hestia.apple.calendar import CalendarClient
            cal = CalendarClient()
            events = await cal.get_today_events()
            upcoming = await cal.get_upcoming_events(days=3)
            all_events = events + upcoming

            refs = []
            for event in all_events:
                refs.append(CrossReference(
                    source=CrossReferenceSource.CALENDAR,
                    match=f"{event.title} ({event.start.strftime('%b %d %H:%M') if event.start else 'no date'})",
                    relevance=0.7,
                    details={
                        "event_id": event.id,
                        "title": event.title,
                        "start": event.start.isoformat() if event.start else None,
                        "location": event.location,
                    },
                ))
            return refs
        except Exception as e:
            self.logger.debug(
                f"Calendar cross-reference unavailable: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            return []

    async def _xref_reminders(self) -> List[CrossReference]:
        """Query incomplete and overdue reminders."""
        try:
            from hestia.apple.reminders import RemindersClient
            rem = RemindersClient()
            incomplete = await rem.get_incomplete()
            overdue = await rem.get_overdue()
            all_reminders = incomplete + overdue

            refs = []
            for reminder in all_reminders[:20]:  # Limit
                refs.append(CrossReference(
                    source=CrossReferenceSource.REMINDERS,
                    match=reminder.title,
                    relevance=0.8 if reminder in overdue else 0.5,
                    details={
                        "reminder_id": reminder.id,
                        "title": reminder.title,
                        "due_date": reminder.due_date.isoformat() if reminder.due_date else None,
                        "is_overdue": reminder in overdue,
                    },
                ))
            return refs
        except Exception as e:
            self.logger.debug(
                f"Reminders cross-reference unavailable: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            return []

    async def _xref_mail(self, search_terms: List[str]) -> List[CrossReference]:
        """Search recent emails for matching content."""
        try:
            from hestia.apple.mail import MailClient
            mail = MailClient()
            async with mail:
                recent = await mail.get_recent_emails(days=3, limit=20)

            refs = []
            for email in recent:
                # Check if any search term appears in subject
                subject_lower = (email.subject or "").lower()
                matched = any(term.lower() in subject_lower for term in search_terms if len(term) > 3)
                if matched:
                    refs.append(CrossReference(
                        source=CrossReferenceSource.MAIL,
                        match=f"From {email.sender}: {email.subject}",
                        relevance=0.6,
                        details={
                            "message_id": email.message_id,
                            "subject": email.subject,
                            "sender": email.sender,
                            "date": email.date.isoformat() if email.date else None,
                        },
                    ))
            return refs
        except Exception as e:
            self.logger.debug(
                f"Mail cross-reference unavailable: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            return []

    async def _xref_memory(self, search_terms: List[str]) -> List[CrossReference]:
        """Search memory for relevant prior context."""
        try:
            from hestia.memory.manager import MemoryManager, get_memory_manager
            manager = await get_memory_manager()

            refs = []
            # Search for each significant term
            for term in search_terms[:5]:  # Limit to 5 searches
                if len(term) < 4:
                    continue
                results = await manager.search(query=term, limit=2)
                for result in results:
                    refs.append(CrossReference(
                        source=CrossReferenceSource.MEMORY,
                        match=result.chunk.content[:100],
                        relevance=result.relevance_score,
                        details={
                            "chunk_id": result.chunk.id,
                            "chunk_type": result.chunk.chunk_type.value,
                            "relevance": result.relevance_score,
                        },
                    ))
            return refs
        except Exception as e:
            self.logger.debug(
                f"Memory cross-reference unavailable: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            return []

    async def _generate_action_plan(
        self,
        intents: List[JournalIntent],
        cross_refs: List[CrossReference],
    ) -> tuple[List[ActionPlanItem], str]:
        """
        Generate action plan from intents and cross-reference context.

        Args:
            intents: Extracted intents.
            cross_refs: Cross-reference matches.

        Returns:
            Tuple of (action plan items, summary string).
        """
        intents_json = json.dumps([i.to_dict() for i in intents], indent=2)
        context_json = json.dumps([cr.to_dict() for cr in cross_refs], indent=2)

        prompt = ACTION_PLAN_PROMPT.format(
            intents_json=intents_json[:2000],
            context_json=context_json[:2000],
        )

        client = get_inference_client()
        response = await client.complete(
            prompt=prompt,
            temperature=0.1,  # Slight creativity for action descriptions
            max_tokens=2000,
            validate=False,
        )

        return self._parse_action_plan_response(response.content, intents)

    def _parse_intents_response(self, response_text: str) -> List[JournalIntent]:
        """Parse LLM response into JournalIntents."""
        try:
            json_text = self._extract_json(response_text)
            data = json.loads(json_text)

            intents = []
            for intent_data in data.get("intents", []):
                try:
                    intent = JournalIntent.from_dict(intent_data)
                    intents.append(intent)
                except (KeyError, ValueError) as e:
                    self.logger.debug(
                        f"Skipping malformed intent: {type(e).__name__}",
                        component=LogComponent.VOICE,
                    )
            return intents

        except (json.JSONDecodeError, TypeError) as e:
            self.logger.warning(
                f"Failed to parse intents response: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            return []

    def _parse_action_plan_response(
        self,
        response_text: str,
        intents: List[JournalIntent],
    ) -> tuple[List[ActionPlanItem], str]:
        """Parse LLM response into action plan items and summary."""
        try:
            json_text = self._extract_json(response_text)
            data = json.loads(json_text)

            items = []
            for item_data in data.get("action_plan", []):
                try:
                    item = ActionPlanItem.from_dict(item_data)
                    items.append(item)
                except (KeyError, ValueError) as e:
                    self.logger.debug(
                        f"Skipping malformed action plan item: {type(e).__name__}",
                        component=LogComponent.VOICE,
                    )

            summary = data.get("summary", "")
            return items, summary

        except (json.JSONDecodeError, TypeError) as e:
            self.logger.warning(
                f"Failed to parse action plan response: {type(e).__name__}",
                component=LogComponent.VOICE,
            )
            return [], ""

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, handling markdown code blocks."""
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            return brace_match.group(0)

        return text.strip()


def get_journal_analyzer() -> JournalAnalyzer:
    """Get or create the singleton journal analyzer instance."""
    global _journal_analyzer
    if _journal_analyzer is None:
        _journal_analyzer = JournalAnalyzer()
    return _journal_analyzer
