"""
Proactive Intelligence Module for Hestia.

Implements ADR-017: Proactive Intelligence Framework.

This module provides:
- Daily briefing generation (calendar, reminders, weather, suggestions)
- Behavioral pattern detection from conversation history
- Interruption policy management (respects Focus mode, quiet hours)
- Notification scheduling and queuing

The goal is the "Jarvis moment" - anticipating user needs proactively.
"""

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
from hestia.proactive.briefing import (
    BriefingGenerator,
    get_briefing_generator,
)
from hestia.proactive.patterns import (
    PatternDetector,
    get_pattern_detector,
)
from hestia.proactive.policy import (
    InterruptionManager,
    get_interruption_manager,
)
from hestia.proactive.config_store import (
    load_config,
    save_config,
    get_proactive_config,
    update_proactive_config,
)

__all__ = [
    # Models
    "Briefing",
    "BriefingSection",
    "BehaviorPattern",
    "PatternType",
    "InterruptionPolicy",
    "InterruptionContext",
    "ProactiveNotification",
    "NotificationPriority",
    "ProactiveConfig",
    # Generators
    "BriefingGenerator",
    "get_briefing_generator",
    # Pattern Detection
    "PatternDetector",
    "get_pattern_detector",
    # Policy
    "InterruptionManager",
    "get_interruption_manager",
    # Config Persistence
    "load_config",
    "save_config",
    "get_proactive_config",
    "update_proactive_config",
]
