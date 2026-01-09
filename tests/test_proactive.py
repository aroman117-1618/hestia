"""
Tests for Proactive Intelligence module.

Tests cover:
- Models and data structures
- Briefing generation
- Pattern detection
- Interruption policy
- API endpoints
"""

import pytest
from datetime import datetime, time, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.proactive.models import (
    Briefing,
    BriefingSection,
    BehaviorPattern,
    PatternType,
    InterruptionPolicy,
    InterruptionContext,
    ProactiveNotification,
    NotificationPriority,
    ProactiveConfig,
)
from hestia.proactive.briefing import BriefingGenerator
from hestia.proactive.patterns import PatternDetector
from hestia.proactive.policy import InterruptionManager


# =============================================================================
# Model Tests
# =============================================================================

class TestProactiveConfig:
    """Tests for ProactiveConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ProactiveConfig()

        assert config.interruption_policy == InterruptionPolicy.DAILY_ONLY
        assert config.briefing_enabled is True
        assert config.briefing_time == time(7, 0)
        assert config.briefing_days == [0, 1, 2, 3, 4]  # Mon-Fri
        assert config.quiet_hours_enabled is True
        assert config.pattern_detection_enabled is True
        assert config.pattern_min_confidence == 0.7
        assert config.pattern_min_occurrences == 3

    def test_is_quiet_hours_daytime(self):
        """Test quiet hours detection during daytime."""
        config = ProactiveConfig(
            quiet_hours_enabled=True,
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(7, 0),
        )

        # 2pm should not be quiet hours
        assert config.is_quiet_hours(time(14, 0)) is False

        # 11pm should be quiet hours
        assert config.is_quiet_hours(time(23, 0)) is True

        # 3am should be quiet hours
        assert config.is_quiet_hours(time(3, 0)) is True

        # 8am should not be quiet hours
        assert config.is_quiet_hours(time(8, 0)) is False

    def test_is_quiet_hours_disabled(self):
        """Test quiet hours when disabled."""
        config = ProactiveConfig(quiet_hours_enabled=False)

        assert config.is_quiet_hours(time(23, 0)) is False
        assert config.is_quiet_hours(time(3, 0)) is False

    def test_should_send_briefing(self):
        """Test briefing schedule detection."""
        config = ProactiveConfig(
            briefing_enabled=True,
            briefing_time=time(7, 0),
            briefing_days=[0, 1, 2, 3, 4],  # Mon-Fri
        )

        # Monday at 7:00 AM
        monday_7am = datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc)  # Monday
        assert config.should_send_briefing(monday_7am) is True

        # Monday at 3:00 PM
        monday_3pm = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        assert config.should_send_briefing(monday_3pm) is False

        # Saturday at 7:00 AM
        saturday_7am = datetime(2024, 1, 20, 7, 0, tzinfo=timezone.utc)  # Saturday
        assert config.should_send_briefing(saturday_7am) is False

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        config = ProactiveConfig(
            interruption_policy=InterruptionPolicy.PROACTIVE,
            briefing_time=time(8, 30),
            weather_location="New York,US",
        )

        data = config.to_dict()
        restored = ProactiveConfig.from_dict(data)

        assert restored.interruption_policy == InterruptionPolicy.PROACTIVE
        assert restored.briefing_time == time(8, 30)
        assert restored.weather_location == "New York,US"


class TestBehaviorPattern:
    """Tests for BehaviorPattern model."""

    def test_is_valid(self):
        """Test pattern validity check."""
        pattern = BehaviorPattern(
            id="test_pattern",
            pattern_type=PatternType.DAY_OF_WEEK,
            context="on Fridays",
            action="review budget",
            confidence=0.85,
            occurrences=5,
        )

        assert pattern.is_valid() is True
        assert pattern.is_valid(min_confidence=0.9) is False
        assert pattern.is_valid(min_occurrences=10) is False

    def test_generate_suggestion(self):
        """Test suggestion generation."""
        pattern = BehaviorPattern(
            id="test_pattern",
            pattern_type=PatternType.DAY_OF_WEEK,
            context="on Fridays",
            action="review budget",
            confidence=0.85,
            occurrences=5,
        )

        suggestion = pattern.generate_suggestion()
        assert "review budget" in suggestion
        assert "on Fridays" in suggestion

    def test_custom_suggestion_template(self):
        """Test custom suggestion template."""
        pattern = BehaviorPattern(
            id="test_pattern",
            pattern_type=PatternType.TIME_OF_DAY,
            context="in the morning",
            action="check email",
            confidence=0.8,
            occurrences=10,
            suggestion_template="Time to {action}? You usually do this {context}.",
        )

        suggestion = pattern.generate_suggestion()
        assert "Time to check email?" in suggestion
        assert "in the morning" in suggestion


class TestInterruptionContext:
    """Tests for InterruptionContext model."""

    def test_can_interrupt_never_policy(self):
        """Test that NEVER policy blocks all interruptions."""
        context = InterruptionContext(
            current_time=datetime.now(timezone.utc),
            day_of_week=0,
            is_focus_mode=False,
            is_busy_calendar=False,
            is_quiet_hours=False,
        )

        assert context.can_interrupt(InterruptionPolicy.NEVER, NotificationPriority.HIGH) is False
        assert context.can_interrupt(InterruptionPolicy.NEVER, NotificationPriority.URGENT) is False

    def test_can_interrupt_urgent_overrides(self):
        """Test that URGENT priority overrides most restrictions."""
        context = InterruptionContext(
            current_time=datetime.now(timezone.utc),
            day_of_week=0,
            is_focus_mode=True,
            is_busy_calendar=True,
            is_quiet_hours=True,
        )

        # URGENT should override for non-NEVER policies
        assert context.can_interrupt(InterruptionPolicy.DAILY_ONLY, NotificationPriority.URGENT) is True
        assert context.can_interrupt(InterruptionPolicy.PROACTIVE, NotificationPriority.URGENT) is True

    def test_can_interrupt_respects_focus_mode(self):
        """Test that Focus mode blocks non-urgent interruptions."""
        context = InterruptionContext(
            current_time=datetime.now(timezone.utc),
            day_of_week=0,
            is_focus_mode=True,
            is_busy_calendar=False,
            is_quiet_hours=False,
        )

        assert context.can_interrupt(InterruptionPolicy.PROACTIVE, NotificationPriority.HIGH) is False
        assert context.can_interrupt(InterruptionPolicy.PROACTIVE, NotificationPriority.MEDIUM) is False

    def test_can_interrupt_respects_calendar(self):
        """Test that busy calendar blocks non-urgent interruptions."""
        context = InterruptionContext(
            current_time=datetime.now(timezone.utc),
            day_of_week=0,
            is_focus_mode=False,
            is_busy_calendar=True,
            is_quiet_hours=False,
        )

        assert context.can_interrupt(InterruptionPolicy.PROACTIVE, NotificationPriority.MEDIUM) is False

    def test_can_interrupt_proactive_allows(self):
        """Test that PROACTIVE policy allows interruptions when context is clear."""
        context = InterruptionContext(
            current_time=datetime.now(timezone.utc),
            day_of_week=0,
            is_focus_mode=False,
            is_busy_calendar=False,
            is_quiet_hours=False,
        )

        assert context.can_interrupt(InterruptionPolicy.PROACTIVE, NotificationPriority.MEDIUM) is True
        assert context.can_interrupt(InterruptionPolicy.PROACTIVE, NotificationPriority.LOW) is True


class TestBriefing:
    """Tests for Briefing model."""

    def test_to_text(self):
        """Test briefing text generation."""
        briefing = Briefing(
            greeting="Good morning.",
            timestamp=datetime.now(timezone.utc),
            sections=[
                BriefingSection(
                    title="Calendar",
                    content="You have 3 meetings today.",
                    priority=90,
                ),
                BriefingSection(
                    title="Weather",
                    content="Rain expected at 2pm.",
                    priority=50,
                ),
            ],
            suggestions=["You usually review budget on Fridays."],
        )

        text = briefing.to_text()
        assert "Good morning." in text
        assert "3 meetings" in text
        assert "Rain" in text
        assert "budget" in text

    def test_to_dict(self):
        """Test briefing serialization."""
        briefing = Briefing(
            greeting="Good afternoon.",
            timestamp=datetime.now(timezone.utc),
            calendar_summary="No meetings today.",
            overdue_count=2,
        )

        data = briefing.to_dict()
        assert data["greeting"] == "Good afternoon."
        assert data["calendar"]["summary"] == "No meetings today."
        assert data["reminders"]["overdue_count"] == 2


# =============================================================================
# Briefing Generator Tests
# =============================================================================

class TestBriefingGenerator:
    """Tests for BriefingGenerator."""

    @pytest.fixture
    def generator(self):
        """Create a test briefing generator."""
        config = ProactiveConfig(weather_enabled=False)
        return BriefingGenerator(config)

    def test_generate_greeting_morning(self, generator):
        """Test morning greeting generation."""
        morning = datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc)
        greeting = generator._generate_greeting(morning)
        assert "morning" in greeting.lower()

    def test_generate_greeting_afternoon(self, generator):
        """Test afternoon greeting generation."""
        afternoon = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)
        greeting = generator._generate_greeting(afternoon)
        assert "afternoon" in greeting.lower()

    def test_generate_greeting_evening(self, generator):
        """Test evening greeting generation."""
        evening = datetime(2024, 1, 15, 19, 0, tzinfo=timezone.utc)
        greeting = generator._generate_greeting(evening)
        assert "evening" in greeting.lower()

    @pytest.mark.asyncio
    async def test_generate_briefing_basic(self, generator):
        """Test basic briefing generation."""
        with patch.object(generator, '_get_calendar_data', new_callable=AsyncMock) as mock_cal, \
             patch.object(generator, '_get_reminders_data', new_callable=AsyncMock) as mock_rem, \
             patch.object(generator, '_get_tasks_data', new_callable=AsyncMock) as mock_tasks:

            mock_cal.return_value = {"events": [], "count": 0}
            mock_rem.return_value = {"overdue": [], "due_today": [], "overdue_count": 0, "due_today_count": 0}
            mock_tasks.return_value = {"pending_count": 0, "awaiting_approval_count": 0, "total": 0}

            briefing = await generator.generate()

            assert briefing.greeting is not None
            assert briefing.timestamp is not None

    @pytest.mark.asyncio
    async def test_generate_briefing_with_events(self, generator):
        """Test briefing generation with calendar events."""
        with patch.object(generator, '_get_calendar_data', new_callable=AsyncMock) as mock_cal, \
             patch.object(generator, '_get_reminders_data', new_callable=AsyncMock) as mock_rem, \
             patch.object(generator, '_get_tasks_data', new_callable=AsyncMock) as mock_tasks:

            mock_cal.return_value = {
                "events": [
                    {"title": "Standup", "start": "2024-01-15T09:00:00Z", "is_all_day": False},
                    {"title": "Review", "start": "2024-01-15T14:00:00Z", "is_all_day": False},
                ],
                "count": 2,
            }
            mock_rem.return_value = {"overdue": [], "due_today": [], "overdue_count": 0, "due_today_count": 0}
            mock_tasks.return_value = {"pending_count": 0, "awaiting_approval_count": 0, "total": 0}

            briefing = await generator.generate()

            assert briefing.calendar_summary is not None
            assert "2 meetings" in briefing.calendar_summary
            assert len(briefing.calendar_events) == 2


# =============================================================================
# Pattern Detector Tests
# =============================================================================

class TestPatternDetector:
    """Tests for PatternDetector."""

    @pytest.fixture
    def detector(self):
        """Create a test pattern detector."""
        config = ProactiveConfig(
            pattern_min_confidence=0.7,
            pattern_min_occurrences=3,
            pattern_lookback_weeks=4,
        )
        return PatternDetector(config)

    def test_extract_activities(self, detector):
        """Test activity extraction from content."""
        content = "I need to review the budget and send some emails"
        activities = detector._extract_activities(content)

        assert "budget" in activities
        assert "email" in activities

    def test_extract_activities_no_match(self, detector):
        """Test activity extraction with no keywords."""
        content = "Hello, how are you doing today?"
        activities = detector._extract_activities(content)

        assert len(activities) == 0

    def test_get_patterns_valid_only(self, detector):
        """Test getting valid patterns only."""
        # Add some patterns manually
        detector._patterns = {
            "valid": BehaviorPattern(
                id="valid",
                pattern_type=PatternType.DAY_OF_WEEK,
                context="on Fridays",
                action="review budget",
                confidence=0.85,
                occurrences=5,
            ),
            "invalid": BehaviorPattern(
                id="invalid",
                pattern_type=PatternType.DAY_OF_WEEK,
                context="on Mondays",
                action="check email",
                confidence=0.5,  # Below threshold
                occurrences=2,  # Below threshold
            ),
        }

        valid_patterns = detector.get_patterns(valid_only=True)
        all_patterns = detector.get_patterns(valid_only=False)

        assert len(valid_patterns) == 1
        assert len(all_patterns) == 2
        assert valid_patterns[0].id == "valid"


# =============================================================================
# Interruption Manager Tests
# =============================================================================

class TestInterruptionManager:
    """Tests for InterruptionManager."""

    @pytest.fixture
    def manager(self):
        """Create a test interruption manager."""
        config = ProactiveConfig(
            interruption_policy=InterruptionPolicy.PROACTIVE,
            quiet_hours_enabled=True,
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(7, 0),
        )
        return InterruptionManager(config)

    def test_can_interrupt_clear_context(self, manager):
        """Test interruption allowed with clear context."""
        with patch.object(manager, '_check_focus_mode', return_value=False), \
             patch.object(manager, '_check_calendar_busy', return_value=False):

            # Mock config to not be in quiet hours
            manager.config.quiet_hours_enabled = False

            assert manager.can_interrupt(NotificationPriority.MEDIUM) is True

    def test_can_interrupt_focus_mode_blocks(self, manager):
        """Test Focus mode blocks interruption."""
        with patch.object(manager, '_check_focus_mode', return_value=True), \
             patch.object(manager, '_check_calendar_busy', return_value=False):

            manager.config.quiet_hours_enabled = False

            assert manager.can_interrupt(NotificationPriority.MEDIUM) is False
            assert manager.can_interrupt(NotificationPriority.URGENT) is True  # Urgent overrides

    def test_should_send_briefing_respects_policy(self, manager):
        """Test briefing schedule respects NEVER policy."""
        manager.config.interruption_policy = InterruptionPolicy.NEVER

        assert manager.should_send_briefing() is False

    def test_get_next_briefing_time(self, manager):
        """Test next briefing time calculation."""
        manager.config.briefing_enabled = True
        manager.config.briefing_time = time(7, 0)
        manager.config.briefing_days = [0, 1, 2, 3, 4]  # Mon-Fri

        next_time = manager.get_next_briefing_time()

        assert next_time is not None
        assert next_time.hour == 7
        assert next_time.minute == 0
        assert next_time.weekday() in [0, 1, 2, 3, 4]

    def test_get_next_briefing_disabled(self, manager):
        """Test no next briefing when disabled."""
        manager.config.briefing_enabled = False

        assert manager.get_next_briefing_time() is None


# =============================================================================
# Integration Tests
# =============================================================================

class TestProactiveIntegration:
    """Integration tests for proactive features."""

    @pytest.mark.asyncio
    async def test_full_briefing_flow(self):
        """Test complete briefing generation flow."""
        config = ProactiveConfig(weather_enabled=False)
        generator = BriefingGenerator(config)
        detector = PatternDetector(config)

        # Add a test pattern
        detector._patterns = {
            "friday_budget": BehaviorPattern(
                id="friday_budget",
                pattern_type=PatternType.DAY_OF_WEEK,
                context="on Fridays",
                action="review budget",
                confidence=0.85,
                occurrences=5,
            ),
        }

        with patch.object(generator, '_get_calendar_data', new_callable=AsyncMock) as mock_cal, \
             patch.object(generator, '_get_reminders_data', new_callable=AsyncMock) as mock_rem, \
             patch.object(generator, '_get_tasks_data', new_callable=AsyncMock) as mock_tasks:

            mock_cal.return_value = {"events": [], "count": 0}
            mock_rem.return_value = {"overdue": [], "due_today": [], "overdue_count": 0, "due_today_count": 0}
            mock_tasks.return_value = {"pending_count": 0, "awaiting_approval_count": 0, "total": 0}

            patterns = detector.get_patterns()
            briefing = await generator.generate(patterns=patterns)

            # Check briefing was generated
            assert briefing.greeting is not None
            assert briefing.timestamp is not None

            # Check serialization works
            data = briefing.to_dict()
            assert "greeting" in data
            assert "timestamp" in data


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
