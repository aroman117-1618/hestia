"""Golden dataset validation for agent routing accuracy."""

import pytest
from hestia.orchestration.router import AgentRouter
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig
from hestia.council.models import IntentType


GOLDEN_DATASET = [
    # (intent, content, expected_route)

    # ── Simple queries -> HESTIA_SOLO ────────────────────────────────────
    (IntentType.CHAT, "hey", AgentRoute.HESTIA_SOLO),
    (IntentType.CHAT, "thanks", AgentRoute.HESTIA_SOLO),
    (IntentType.CHAT, "good morning", AgentRoute.HESTIA_SOLO),
    (IntentType.CHAT, "how are you today", AgentRoute.HESTIA_SOLO),
    (IntentType.CALENDAR_QUERY, "what's on my calendar today", AgentRoute.HESTIA_SOLO),
    (IntentType.REMINDER_QUERY, "what are my reminders", AgentRoute.HESTIA_SOLO),
    (IntentType.WEATHER_QUERY, "what's the weather", AgentRoute.HESTIA_SOLO),
    (IntentType.NOTE_SEARCH, "find my sprint notes", AgentRoute.HESTIA_SOLO),
    (IntentType.MAIL_QUERY, "check my email", AgentRoute.HESTIA_SOLO),
    (IntentType.STOCKS_QUERY, "how is AAPL doing", AgentRoute.HESTIA_SOLO),

    # ── Analysis -> ARTEMIS ──────────────────────────────────────────────
    (IntentType.CHAT, "compare SQLite vs Postgres for this feature", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "help me think through the authentication architecture", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "what are the pros and cons of microservices", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "evaluate whether we should use GraphQL", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "explain why the council system uses dual-path execution", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "should I use Redis or Memcached for caching", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "investigate the performance implications of ETag caching", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "research how other AI assistants handle context windows", AgentRoute.ARTEMIS),
    (IntentType.CHAT, "deep dive into the temporal decay algorithm", AgentRoute.ARTEMIS),
    (IntentType.MEMORY_SEARCH, "what do I know about the cloud routing system", AgentRoute.ARTEMIS),

    # ── Execution -> APOLLO ──────────────────────────────────────────────
    (IntentType.CODING, "write the migration script for users table", AgentRoute.APOLLO),
    (IntentType.CODING, "fix the bug in the auth middleware", AgentRoute.APOLLO),
    (IntentType.CHAT, "write a function that validates email addresses", AgentRoute.APOLLO),
    (IntentType.CHAT, "create a new endpoint for user preferences", AgentRoute.APOLLO),
    (IntentType.CHAT, "build the WebSocket handler for real-time updates", AgentRoute.APOLLO),
    (IntentType.CHAT, "scaffold the health dashboard component", AgentRoute.APOLLO),
    (IntentType.CHAT, "refactor the memory manager to use async generators", AgentRoute.APOLLO),
    (IntentType.CHAT, "implement the ETag caching for wiki endpoints", AgentRoute.APOLLO),
    (IntentType.CALENDAR_CREATE, "schedule a meeting for tomorrow at 3pm", AgentRoute.APOLLO),
    (IntentType.REMINDER_CREATE, "remind me to deploy on Friday", AgentRoute.APOLLO),

    # ── Chain -> ARTEMIS_THEN_APOLLO ─────────────────────────────────────
    (IntentType.CHAT, "research how HealthKit handles background sync then implement it", AgentRoute.ARTEMIS_THEN_APOLLO),
    (IntentType.CHAT, "analyze the trade-offs of SSE vs WebSocket and then build the SSE implementation", AgentRoute.ARTEMIS_THEN_APOLLO),
    (IntentType.CHAT, "investigate the best caching strategy and implement it for our API", AgentRoute.ARTEMIS_THEN_APOLLO),
]


@pytest.fixture
def router():
    return AgentRouter(OrchestratorConfig())


class TestGoldenDataset:
    """Validate routing accuracy against golden dataset."""

    @pytest.mark.parametrize("intent,content,expected", GOLDEN_DATASET)
    def test_golden_routing(self, router, intent, content, expected):
        route, confidence = router.resolve(intent, content)
        assert route == expected, (
            f"Expected {expected.value} for '{content[:60]}...' "
            f"(intent={intent.value}), got {route.value}"
        )

    def test_accuracy_above_threshold(self, router):
        """Overall accuracy must be >= 75%."""
        correct = 0
        for intent, content, expected in GOLDEN_DATASET:
            route, _ = router.resolve(intent, content)
            if route == expected:
                correct += 1
        accuracy = correct / len(GOLDEN_DATASET)
        assert accuracy >= 0.75, (
            f"Routing accuracy {accuracy:.1%} below 75% threshold "
            f"({correct}/{len(GOLDEN_DATASET)} correct)"
        )
