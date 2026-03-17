"""
Tests for the anti-hallucination verification pipeline (Sprint 18).

Covers:
- HallucinationRisk enum and VerificationResult dataclass
- ToolComplianceChecker Layer 1 detection
- build_context_with_score() memory manager addition
"""
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class TestVerificationModels:
    def test_hallucination_risk_enum_values(self):
        from hestia.verification.models import HallucinationRisk
        assert HallucinationRisk.NONE.value == "none"
        assert HallucinationRisk.TOOL_BYPASS.value == "tool_bypass"
        assert HallucinationRisk.LOW_RETRIEVAL.value == "low_retrieval"
        assert HallucinationRisk.SLM_FLAG.value == "slm_flag"
        assert HallucinationRisk.UNKNOWN.value == "unknown"

    def test_verification_result_clean(self):
        from hestia.verification.models import VerificationResult, HallucinationRisk
        result = VerificationResult.clean()
        assert result.risk == HallucinationRisk.NONE
        assert not result.has_risk
        assert result.disclaimer is None
        assert result.flags == []

    def test_verification_result_has_risk(self):
        from hestia.verification.models import VerificationResult, HallucinationRisk
        result = VerificationResult(risk=HallucinationRisk.TOOL_BYPASS)
        assert result.has_risk

    def test_verification_result_with_disclaimer(self):
        from hestia.verification.models import VerificationResult, HallucinationRisk
        result = VerificationResult(
            risk=HallucinationRisk.TOOL_BYPASS,
            disclaimer="Please verify.",
            flags=["calendar_claim_without_tool"],
        )
        assert result.has_risk
        assert result.disclaimer == "Please verify."
        assert len(result.flags) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tool Compliance Checker (Layer 1)
# ─────────────────────────────────────────────────────────────────────────────

class TestToolComplianceChecker:
    def setup_method(self):
        from hestia.verification.tool_compliance import ToolComplianceChecker
        self.checker = ToolComplianceChecker()

    def test_clean_response_no_disclaimer(self):
        """Conversational response with no domain claims returns None."""
        response = "The weather looks nice today. How can I help you?"
        result = self.checker.check(response, had_tool_calls=False)
        assert result is None

    def test_grounded_response_with_tool_calls(self):
        """Response grounded by tool calls returns None regardless of content."""
        response = "Your next meeting is at 3pm with the design team."
        result = self.checker.check(response, had_tool_calls=True)
        assert result is None

    def test_calendar_claim_without_tool_returns_disclaimer(self):
        """Calendar data claim without tool call triggers disclaimer."""
        response = "Your next meeting is the team standup at 9am."
        result = self.checker.check(response, had_tool_calls=False)
        assert result is not None
        assert "verify" in result.lower() or "confirm" in result.lower()

    def test_health_claim_without_tool_returns_disclaimer(self):
        """Health data claim without tool call triggers disclaimer."""
        response = "Your heart rate today was 72 bpm, which is excellent."
        result = self.checker.check(response, had_tool_calls=False)
        assert result is not None

    def test_notes_claim_without_tool_returns_disclaimer(self):
        """Notes data claim without tool call triggers disclaimer."""
        response = "In your notes, you wrote down the project deadline as March 30."
        result = self.checker.check(response, had_tool_calls=False)
        assert result is not None

    def test_reminder_claim_without_tool(self):
        """Reminder data claim without tool call triggers disclaimer."""
        response = "You have a reminder to call the dentist tomorrow at noon."
        result = self.checker.check(response, had_tool_calls=False)
        assert result is not None

    def test_empty_response_returns_none(self):
        """Empty response is never flagged."""
        result = self.checker.check("", had_tool_calls=False)
        assert result is None

    def test_generic_project_question_no_false_positive(self):
        """Questions about roadmap/status should not trigger false positives."""
        response = (
            "We're at Sprint 17 with the agent orchestration complete. "
            "Next candidates include the outcome-to-principle pipeline."
        )
        result = self.checker.check(response, had_tool_calls=False)
        assert result is None

    def test_checker_does_not_raise_on_internal_error(self, monkeypatch):
        """Internal errors return None — never raise to caller (fail-open)."""
        import hestia.verification.tool_compliance as tc_module
        # Clear cached patterns to force reload
        monkeypatch.setattr(tc_module, "_COMPILED_PATTERNS", None)

        original_load = tc_module._load_patterns

        def bad_load():
            raise RuntimeError("config unavailable")

        monkeypatch.setattr(tc_module, "_load_patterns", bad_load)
        # Should not raise — fail-open; hardcoded fallback kicks in
        try:
            result = self.checker.check("Your heart rate is 72 bpm.", had_tool_calls=False)
            # Either None or a disclaimer string — both acceptable
            assert result is None or isinstance(result, str)
        finally:
            monkeypatch.setattr(tc_module, "_load_patterns", original_load)
            monkeypatch.setattr(tc_module, "_COMPILED_PATTERNS", None)
