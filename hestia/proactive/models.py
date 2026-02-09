"""
Data models for Proactive Intelligence.

Implements ADR-017: Proactive Intelligence Framework.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import List, Optional, Dict, Any


class InterruptionPolicy(Enum):
    """User preference for proactive interruptions."""
    NEVER = "never"           # No proactive notifications
    DAILY_ONLY = "daily"      # Only daily briefing at scheduled time
    PROACTIVE = "proactive"   # Allow context-aware proactive suggestions


class NotificationPriority(Enum):
    """Priority levels for proactive notifications."""
    LOW = "low"               # Can wait, batch with others
    MEDIUM = "medium"         # Timely but not urgent
    HIGH = "high"             # Time-sensitive, may interrupt
    URGENT = "urgent"         # Override quiet hours (emergency only)


class PatternType(Enum):
    """Types of behavioral patterns detected."""
    DAY_OF_WEEK = "day_of_week"       # "You review budget on Fridays"
    TIME_OF_DAY = "time_of_day"       # "You usually check email at 9am"
    AFTER_EVENT = "after_event"        # "After meetings, you write notes"
    RECURRING = "recurring"            # "Every Monday you plan the week"
    CONTEXTUAL = "contextual"          # "When traveling, you check weather"


@dataclass
class BriefingSection:
    """A section of the daily briefing."""
    title: str
    content: str
    priority: int = 0  # Higher = more important, shown first
    icon: Optional[str] = None  # SF Symbol name for iOS


@dataclass
class Briefing:
    """
    Daily briefing generated for the user.

    Example output:
    "Good morning. You have 3 meetings today (9am standup, 2pm design review,
    4pm 1:1 with Sarah). 2 overdue reminders: project review, email mom.
    Rain forecast 2-4pm—might want an umbrella. You usually review the
    budget on Fridays. Want me to prepare a summary?"
    """
    greeting: str
    timestamp: datetime
    sections: List[BriefingSection] = field(default_factory=list)

    # Structured data for UI rendering
    calendar_summary: Optional[str] = None
    calendar_events: List[Dict[str, Any]] = field(default_factory=list)

    reminders_summary: Optional[str] = None
    overdue_count: int = 0
    due_today_count: int = 0

    tasks_summary: Optional[str] = None
    pending_task_count: int = 0

    weather_summary: Optional[str] = None
    weather_data: Optional[Dict[str, Any]] = None

    health_summary: Optional[str] = None
    health_data: Optional[Dict[str, Any]] = None

    suggestions: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Convert briefing to natural language text."""
        parts = [self.greeting]

        for section in sorted(self.sections, key=lambda s: -s.priority):
            parts.append(section.content)

        if self.suggestions:
            parts.append(" ".join(self.suggestions))

        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "greeting": self.greeting,
            "timestamp": self.timestamp.isoformat(),
            "text": self.to_text(),
            "calendar": {
                "summary": self.calendar_summary,
                "events": self.calendar_events,
            },
            "reminders": {
                "summary": self.reminders_summary,
                "overdue_count": self.overdue_count,
                "due_today_count": self.due_today_count,
            },
            "tasks": {
                "summary": self.tasks_summary,
                "pending_count": self.pending_task_count,
            },
            "weather": {
                "summary": self.weather_summary,
                "data": self.weather_data,
            },
            "health": {
                "summary": self.health_summary,
                "data": self.health_data,
            },
            "suggestions": self.suggestions,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "priority": s.priority,
                    "icon": s.icon,
                }
                for s in self.sections
            ],
        }


@dataclass
class BehaviorPattern:
    """
    A detected behavioral pattern from conversation history.

    Patterns are used to make proactive suggestions:
    "You usually review the budget on Friday afternoons. Ready for that now?"
    """
    id: str
    pattern_type: PatternType
    context: str              # "Friday afternoon", "After meetings"
    action: str               # "reviews weekly budget", "writes notes"
    confidence: float         # 0.0 to 1.0
    occurrences: int          # Number of times observed
    last_triggered: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    # For generating suggestions
    suggestion_template: Optional[str] = None

    def is_valid(self, min_confidence: float = 0.7, min_occurrences: int = 3) -> bool:
        """Check if pattern meets threshold for suggestions."""
        return self.confidence >= min_confidence and self.occurrences >= min_occurrences

    def generate_suggestion(self) -> str:
        """Generate a suggestion based on this pattern."""
        if self.suggestion_template:
            return self.suggestion_template.format(
                context=self.context,
                action=self.action,
            )
        return f"You usually {self.action} {self.context}. Ready for that now?"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "type": self.pattern_type.value,
            "context": self.context,
            "action": self.action,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "is_valid": self.is_valid(),
            "suggestion": self.generate_suggestion() if self.is_valid() else None,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class InterruptionContext:
    """
    Current context for interruption decision.

    Used to decide whether to interrupt the user with a notification.
    """
    current_time: datetime
    day_of_week: int          # 0=Monday, 6=Sunday
    is_focus_mode: bool       # macOS/iOS Focus mode active
    is_busy_calendar: bool    # In a meeting or event
    is_quiet_hours: bool      # Within configured quiet hours
    last_interaction: Optional[datetime] = None
    active_session: bool = False

    def can_interrupt(self, policy: InterruptionPolicy, priority: NotificationPriority) -> bool:
        """Determine if interruption is allowed based on context and policy."""
        # Never interrupt if policy is NEVER
        if policy == InterruptionPolicy.NEVER:
            return False

        # Urgent overrides everything except NEVER policy
        if priority == NotificationPriority.URGENT:
            return True

        # Don't interrupt during focus mode
        if self.is_focus_mode:
            return False

        # Don't interrupt during calendar events
        if self.is_busy_calendar:
            return False

        # Don't interrupt during quiet hours (unless high priority)
        if self.is_quiet_hours and priority != NotificationPriority.HIGH:
            return False

        # DAILY_ONLY allows only scheduled briefings (handled separately)
        if policy == InterruptionPolicy.DAILY_ONLY:
            return False

        # PROACTIVE allows interruptions
        return policy == InterruptionPolicy.PROACTIVE


@dataclass
class ProactiveNotification:
    """
    A proactive notification to show the user.
    """
    id: str
    title: str
    body: str
    priority: NotificationPriority
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_for: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None

    # Source information
    source_type: str = "system"  # "briefing", "pattern", "reminder", "weather"
    source_id: Optional[str] = None

    # Action data
    action_type: Optional[str] = None  # "open_briefing", "open_reminder", etc.
    action_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "dismissed_at": self.dismissed_at.isoformat() if self.dismissed_at else None,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "action_type": self.action_type,
            "action_data": self.action_data,
        }


@dataclass
class ProactiveConfig:
    """
    User configuration for proactive features.
    """
    # Policy
    interruption_policy: InterruptionPolicy = InterruptionPolicy.DAILY_ONLY

    # Briefing schedule
    briefing_enabled: bool = True
    briefing_time: time = field(default_factory=lambda: time(7, 0))  # 7:00 AM
    briefing_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri

    # Quiet hours
    quiet_hours_enabled: bool = True
    quiet_hours_start: time = field(default_factory=lambda: time(22, 0))  # 10:00 PM
    quiet_hours_end: time = field(default_factory=lambda: time(7, 0))    # 7:00 AM

    # Pattern detection
    pattern_detection_enabled: bool = True
    pattern_min_confidence: float = 0.7
    pattern_min_occurrences: int = 3
    pattern_lookback_weeks: int = 4

    # Weather (requires API key)
    weather_enabled: bool = True
    weather_location: Optional[str] = None  # City name or coordinates

    def is_quiet_hours(self, current_time: time) -> bool:
        """Check if current time is within quiet hours."""
        if not self.quiet_hours_enabled:
            return False

        start = self.quiet_hours_start
        end = self.quiet_hours_end

        # Handle overnight quiet hours (e.g., 10pm to 7am)
        if start > end:
            return current_time >= start or current_time < end
        else:
            return start <= current_time < end

    def should_send_briefing(self, current: datetime) -> bool:
        """Check if briefing should be sent at current time."""
        if not self.briefing_enabled:
            return False

        # Check day of week (0=Monday)
        if current.weekday() not in self.briefing_days:
            return False

        # Check time (within 5 minute window)
        current_minutes = current.hour * 60 + current.minute
        briefing_minutes = self.briefing_time.hour * 60 + self.briefing_time.minute

        return abs(current_minutes - briefing_minutes) <= 5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "interruption_policy": self.interruption_policy.value,
            "briefing": {
                "enabled": self.briefing_enabled,
                "time": self.briefing_time.isoformat(),
                "days": self.briefing_days,
            },
            "quiet_hours": {
                "enabled": self.quiet_hours_enabled,
                "start": self.quiet_hours_start.isoformat(),
                "end": self.quiet_hours_end.isoformat(),
            },
            "patterns": {
                "enabled": self.pattern_detection_enabled,
                "min_confidence": self.pattern_min_confidence,
                "min_occurrences": self.pattern_min_occurrences,
                "lookback_weeks": self.pattern_lookback_weeks,
            },
            "weather": {
                "enabled": self.weather_enabled,
                "location": self.weather_location,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProactiveConfig":
        """Create config from dictionary."""
        config = cls()

        if "interruption_policy" in data:
            config.interruption_policy = InterruptionPolicy(data["interruption_policy"])

        if "briefing" in data:
            b = data["briefing"]
            config.briefing_enabled = b.get("enabled", True)
            if "time" in b:
                config.briefing_time = time.fromisoformat(b["time"])
            if "days" in b:
                config.briefing_days = b["days"]

        if "quiet_hours" in data:
            q = data["quiet_hours"]
            config.quiet_hours_enabled = q.get("enabled", True)
            if "start" in q:
                config.quiet_hours_start = time.fromisoformat(q["start"])
            if "end" in q:
                config.quiet_hours_end = time.fromisoformat(q["end"])

        if "patterns" in data:
            p = data["patterns"]
            config.pattern_detection_enabled = p.get("enabled", True)
            config.pattern_min_confidence = p.get("min_confidence", 0.7)
            config.pattern_min_occurrences = p.get("min_occurrences", 3)
            config.pattern_lookback_weeks = p.get("lookback_weeks", 4)

        if "weather" in data:
            w = data["weather"]
            config.weather_enabled = w.get("enabled", True)
            config.weather_location = w.get("location")

        return config
