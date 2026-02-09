"""
Behavioral Pattern Detector for Hestia.

Analyzes conversation history to detect recurring patterns like:
- Day-of-week patterns ("You review budget on Fridays")
- Time-of-day patterns ("You check email at 9am")
- After-event patterns ("After meetings, you write notes")

Implements ADR-017: Proactive Intelligence Framework.
"""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from hestia.logging import get_logger, LogComponent
from hestia.proactive.models import (
    BehaviorPattern,
    PatternType,
    ProactiveConfig,
)


# Keywords that suggest specific activities
ACTIVITY_KEYWORDS = {
    "budget": ["budget", "expense", "spending", "finances", "financial", "money"],
    "email": ["email", "mail", "inbox", "message", "reply", "send"],
    "meeting_notes": ["notes", "meeting notes", "summary", "recap", "takeaways"],
    "planning": ["plan", "planning", "schedule", "organize", "agenda"],
    "review": ["review", "check", "look at", "examine", "assess"],
    "report": ["report", "analysis", "summary", "document"],
    "workout": ["workout", "exercise", "gym", "run", "fitness"],
}

# Day names for pattern matching
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_ABBREVS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class PatternDetector:
    """
    Detects behavioral patterns from conversation history.

    Uses memory layer to analyze past conversations and identify
    recurring patterns that can be used for proactive suggestions.
    """

    def __init__(self, config: Optional[ProactiveConfig] = None):
        """
        Initialize the pattern detector.

        Args:
            config: Proactive configuration. If None, uses defaults.
        """
        self.config = config or ProactiveConfig()
        self.logger = get_logger()

        # Cached patterns
        self._patterns: Dict[str, BehaviorPattern] = {}
        self._last_analysis: Optional[datetime] = None

    async def analyze(
        self,
        force_refresh: bool = False,
    ) -> List[BehaviorPattern]:
        """
        Analyze conversation history for patterns.

        Args:
            force_refresh: Force re-analysis even if recently done.

        Returns:
            List of detected patterns.
        """
        if not self.config.pattern_detection_enabled:
            return []

        # Check if we need to refresh
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and self._last_analysis
            and (now - self._last_analysis).total_seconds() < 3600  # 1 hour cache
        ):
            return list(self._patterns.values())

        self.logger.info(
            "Analyzing conversation history for patterns",
            component=LogComponent.ORCHESTRATION,
        )

        try:
            from hestia.memory import get_memory_manager

            manager = await get_memory_manager()

            # Get conversation chunks from the lookback period
            lookback = timedelta(weeks=self.config.pattern_lookback_weeks)
            cutoff = now - lookback

            # Query recent chunks
            chunks = await manager.get_recent(limit=500)

            # Filter to lookback period
            chunks = [c for c in chunks if c.timestamp >= cutoff]

            self.logger.info(
                f"Analyzing {len(chunks)} chunks from past {self.config.pattern_lookback_weeks} weeks",
                component=LogComponent.ORCHESTRATION,
            )

            # Detect patterns
            self._patterns = {}

            day_patterns = self._detect_day_of_week_patterns(chunks)
            for p in day_patterns:
                self._patterns[p.id] = p

            time_patterns = self._detect_time_of_day_patterns(chunks)
            for p in time_patterns:
                self._patterns[p.id] = p

            self._last_analysis = now

            valid_count = sum(1 for p in self._patterns.values() if p.is_valid())
            self.logger.info(
                f"Pattern analysis complete: {len(self._patterns)} patterns, {valid_count} valid",
                component=LogComponent.ORCHESTRATION,
            )

            return list(self._patterns.values())

        except Exception as e:
            self.logger.error(
                f"Pattern analysis failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
            )
            return list(self._patterns.values())

    def _detect_day_of_week_patterns(self, chunks) -> List[BehaviorPattern]:
        """Detect day-of-week recurring patterns."""
        patterns = []

        # Group chunks by day of week and extract activities
        day_activities: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for chunk in chunks:
            day = chunk.timestamp.weekday()
            activities = self._extract_activities(chunk.content)
            for activity in activities:
                day_activities[day][activity] += 1

        # Find patterns with sufficient occurrences
        total_weeks = max(1, self.config.pattern_lookback_weeks)

        for day, activities in day_activities.items():
            for activity, count in activities.items():
                if count >= self.config.pattern_min_occurrences:
                    confidence = min(1.0, count / total_weeks)

                    if confidence >= self.config.pattern_min_confidence:
                        day_name = DAY_NAMES[day].capitalize()
                        pattern = BehaviorPattern(
                            id=f"dow_{day}_{activity}",
                            pattern_type=PatternType.DAY_OF_WEEK,
                            context=f"on {day_name}s",
                            action=f"{activity}",
                            confidence=confidence,
                            occurrences=count,
                            suggestion_template=f"You usually {{action}} {{context}}. Ready for that now?",
                        )
                        patterns.append(pattern)

        return patterns

    def _detect_time_of_day_patterns(self, chunks) -> List[BehaviorPattern]:
        """Detect time-of-day recurring patterns."""
        patterns = []

        # Group chunks by time period and extract activities
        # Periods: morning (5-12), afternoon (12-17), evening (17-21), night (21-5)
        period_activities: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for chunk in chunks:
            hour = chunk.timestamp.hour
            if 5 <= hour < 12:
                period = "morning"
            elif 12 <= hour < 17:
                period = "afternoon"
            elif 17 <= hour < 21:
                period = "evening"
            else:
                period = "night"

            activities = self._extract_activities(chunk.content)
            for activity in activities:
                period_activities[period][activity] += 1

        # Find patterns with sufficient occurrences
        total_days = max(1, self.config.pattern_lookback_weeks * 7)

        for period, activities in period_activities.items():
            for activity, count in activities.items():
                # Expect activity roughly daily in that period
                expected = total_days * 0.3  # 30% of days
                if count >= self.config.pattern_min_occurrences:
                    confidence = min(1.0, count / expected) if expected > 0 else 0

                    if confidence >= self.config.pattern_min_confidence:
                        pattern = BehaviorPattern(
                            id=f"tod_{period}_{activity}",
                            pattern_type=PatternType.TIME_OF_DAY,
                            context=f"in the {period}",
                            action=f"{activity}",
                            confidence=confidence,
                            occurrences=count,
                            suggestion_template=f"You often {{action}} {{context}}. Want to do that now?",
                        )
                        patterns.append(pattern)

        return patterns

    def _extract_activities(self, content: str) -> List[str]:
        """Extract activity keywords from content."""
        content_lower = content.lower()
        found = []

        for activity, keywords in ACTIVITY_KEYWORDS.items():
            if any(kw in content_lower for kw in keywords):
                found.append(activity.replace("_", " "))

        return found

    def get_patterns(self, valid_only: bool = True) -> List[BehaviorPattern]:
        """
        Get cached patterns.

        Args:
            valid_only: Only return patterns meeting confidence/occurrence thresholds.

        Returns:
            List of patterns.
        """
        patterns = list(self._patterns.values())

        if valid_only:
            patterns = [
                p for p in patterns
                if p.is_valid(
                    min_confidence=self.config.pattern_min_confidence,
                    min_occurrences=self.config.pattern_min_occurrences,
                )
            ]

        return sorted(patterns, key=lambda p: -p.confidence)

    def get_applicable_patterns(
        self,
        current_time: datetime,
        valid_only: bool = True,
    ) -> List[BehaviorPattern]:
        """
        Get patterns that apply to the current context.

        Args:
            current_time: Current datetime.
            valid_only: Only return valid patterns.

        Returns:
            List of applicable patterns.
        """
        patterns = self.get_patterns(valid_only=valid_only)
        applicable = []

        day = current_time.weekday()
        hour = current_time.hour

        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 21:
            period = "evening"
        else:
            period = "night"

        for pattern in patterns:
            if pattern.pattern_type == PatternType.DAY_OF_WEEK:
                day_name = DAY_NAMES[day]
                if day_name in pattern.context.lower():
                    applicable.append(pattern)

            elif pattern.pattern_type == PatternType.TIME_OF_DAY:
                if period in pattern.context.lower():
                    applicable.append(pattern)

        return applicable


# Module-level singleton
_detector: Optional[PatternDetector] = None


def get_pattern_detector(config: Optional[ProactiveConfig] = None) -> PatternDetector:
    """Get or create the singleton pattern detector."""
    global _detector
    if _detector is None or config is not None:
        _detector = PatternDetector(config)
    return _detector
