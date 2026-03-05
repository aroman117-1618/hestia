"""
Tests for tool trust tiers — model, handler integration, and API.

Covers:
- ToolTrustTiers model logic (should_auto_approve, get_tier_for_tool)
- Serialization/deserialization (to_dict, from_dict)
- UserSettings integration (get/set tool_trust_tiers)
- Trust tier wiring in API schema

Run with: python -m pytest tests/test_trust_tiers.py -v
"""

import pytest
from typing import Any, Dict

from hestia.user.models import ToolTrustTiers, UserSettings


# ============== Model Tests ==============


class TestToolTrustTiers:
    """Tests for the ToolTrustTiers dataclass."""

    def test_defaults(self):
        """Default tiers: read=auto, rest=prompt."""
        tiers = ToolTrustTiers()
        assert tiers.read == "auto"
        assert tiers.write == "prompt"
        assert tiers.execute == "prompt"
        assert tiers.external == "prompt"

    def test_should_auto_approve_read_tier(self):
        """Read-tier tools auto-approve by default."""
        tiers = ToolTrustTiers()
        # health and general categories map to read tier
        assert tiers.should_auto_approve("health", True) is True
        assert tiers.should_auto_approve("general", True) is True

    def test_should_not_auto_approve_write_tier(self):
        """Write-tier tools require prompt by default."""
        tiers = ToolTrustTiers()
        assert tiers.should_auto_approve("calendar", True) is False
        assert tiers.should_auto_approve("reminders", True) is False
        assert tiers.should_auto_approve("notes", True) is False
        assert tiers.should_auto_approve("file", True) is False

    def test_should_not_auto_approve_execute_tier(self):
        """Execute-tier tools require prompt by default."""
        tiers = ToolTrustTiers()
        assert tiers.should_auto_approve("shell", True) is False

    def test_should_not_auto_approve_external_tier(self):
        """External-tier tools require prompt by default."""
        tiers = ToolTrustTiers()
        assert tiers.should_auto_approve("mail", True) is False

    def test_non_approval_tools_always_read(self):
        """Tools that don't require approval are always read tier."""
        tiers = ToolTrustTiers()
        # Even categories that map to "execute" tier return "read" when
        # requires_approval is False
        assert tiers.get_tier_for_tool("shell", False) == "read"
        assert tiers.should_auto_approve("shell", False) is True

    def test_custom_tiers_all_auto(self):
        """All tiers set to auto: everything auto-approves."""
        tiers = ToolTrustTiers(
            read="auto", write="auto", execute="auto", external="auto"
        )
        assert tiers.should_auto_approve("calendar", True) is True
        assert tiers.should_auto_approve("shell", True) is True
        assert tiers.should_auto_approve("mail", True) is True

    def test_custom_tiers_all_prompt(self):
        """All tiers set to prompt: nothing auto-approves."""
        tiers = ToolTrustTiers(
            read="prompt", write="prompt", execute="prompt", external="prompt"
        )
        assert tiers.should_auto_approve("health", True) is False
        assert tiers.should_auto_approve("general", True) is False

    def test_unknown_category_defaults_to_write(self):
        """Unknown categories fall back to write tier."""
        tiers = ToolTrustTiers()
        assert tiers.get_tier_for_tool("unknown_category", True) == "write"
        assert tiers.should_auto_approve("unknown_category", True) is False

    def test_to_dict(self):
        """to_dict excludes CATEGORY_TO_TIER (static mapping)."""
        tiers = ToolTrustTiers()
        d = tiers.to_dict()
        assert d == {
            "read": "auto",
            "write": "prompt",
            "execute": "prompt",
            "external": "prompt",
        }
        assert "CATEGORY_TO_TIER" not in d

    def test_from_dict(self):
        """from_dict reconstructs ToolTrustTiers."""
        data = {
            "read": "prompt",
            "write": "auto",
            "execute": "auto",
            "external": "prompt",
        }
        tiers = ToolTrustTiers.from_dict(data)
        assert tiers.read == "prompt"
        assert tiers.write == "auto"
        assert tiers.execute == "auto"
        assert tiers.external == "prompt"

    def test_from_dict_defaults(self):
        """from_dict with empty dict uses defaults."""
        tiers = ToolTrustTiers.from_dict({})
        assert tiers.read == "auto"
        assert tiers.write == "prompt"

    def test_roundtrip(self):
        """to_dict → from_dict roundtrip preserves values."""
        original = ToolTrustTiers(read="prompt", write="auto", execute="prompt", external="auto")
        restored = ToolTrustTiers.from_dict(original.to_dict())
        assert restored.read == original.read
        assert restored.write == original.write
        assert restored.execute == original.execute
        assert restored.external == original.external


# ============== UserSettings Integration ==============


class TestUserSettingsTrustTiers:
    """Tests for trust tiers stored in UserSettings."""

    def test_default_no_trust_tiers(self):
        """New UserSettings has no trust tiers by default."""
        settings = UserSettings()
        assert settings.tool_trust_tiers is None

    def test_get_default_tiers(self):
        """get_tool_trust_tiers returns defaults when not stored."""
        settings = UserSettings()
        tiers = settings.get_tool_trust_tiers()
        assert tiers.read == "auto"
        assert tiers.write == "prompt"

    def test_set_and_get_tiers(self):
        """set_tool_trust_tiers stores and get retrieves."""
        settings = UserSettings()
        custom = ToolTrustTiers(read="prompt", write="auto", execute="auto", external="prompt")
        settings.set_tool_trust_tiers(custom)

        # Stored as dict
        assert isinstance(settings.tool_trust_tiers, dict)

        # Retrieved as ToolTrustTiers
        retrieved = settings.get_tool_trust_tiers()
        assert retrieved.read == "prompt"
        assert retrieved.write == "auto"
        assert retrieved.execute == "auto"
        assert retrieved.external == "prompt"

    def test_serialization_roundtrip(self):
        """UserSettings to_dict/from_dict preserves trust tiers."""
        settings = UserSettings()
        settings.set_tool_trust_tiers(
            ToolTrustTiers(read="auto", write="auto", execute="prompt", external="prompt")
        )

        data = settings.to_dict()
        assert "tool_trust_tiers" in data

        restored = UserSettings.from_dict(data)
        tiers = restored.get_tool_trust_tiers()
        assert tiers.read == "auto"
        assert tiers.write == "auto"
        assert tiers.execute == "prompt"

    def test_settings_without_tiers_key(self):
        """from_dict without tool_trust_tiers key works."""
        data = {"default_mode": "tia"}
        settings = UserSettings.from_dict(data)
        assert settings.tool_trust_tiers is None
        tiers = settings.get_tool_trust_tiers()
        assert tiers.read == "auto"  # defaults


# ============== Category Mapping Tests ==============


class TestCategoryMapping:
    """Tests for the category → tier mapping."""

    def test_all_builtin_categories_mapped(self):
        """All expected categories have a mapping."""
        tiers = ToolTrustTiers()
        expected_categories = [
            "calendar", "reminders", "notes", "mail",
            "file", "shell", "health", "general",
        ]
        for cat in expected_categories:
            tier = tiers.get_tier_for_tool(cat, True)
            assert tier in ("read", "write", "execute", "external"), f"Category {cat} mapped to unexpected tier: {tier}"

    def test_calendar_is_write(self):
        tiers = ToolTrustTiers()
        assert tiers.get_tier_for_tool("calendar", True) == "write"

    def test_mail_is_external(self):
        tiers = ToolTrustTiers()
        assert tiers.get_tier_for_tool("mail", True) == "external"

    def test_shell_is_execute(self):
        tiers = ToolTrustTiers()
        assert tiers.get_tier_for_tool("shell", True) == "execute"

    def test_health_is_read(self):
        tiers = ToolTrustTiers()
        assert tiers.get_tier_for_tool("health", True) == "read"


# ============== API Schema Tests ==============


class TestTrustTierSchema:
    """Tests for the Pydantic schema validation."""

    def test_valid_values(self):
        from hestia.api.schemas.user import ToolTrustTiersSchema
        schema = ToolTrustTiersSchema(read="auto", write="prompt")
        assert schema.read == "auto"
        assert schema.write == "prompt"

    def test_partial_update(self):
        """Only some fields provided — rest are None."""
        from hestia.api.schemas.user import ToolTrustTiersSchema
        schema = ToolTrustTiersSchema(execute="auto")
        assert schema.read is None
        assert schema.execute == "auto"

    def test_invalid_value_rejected(self):
        """Invalid tier values are rejected by pattern."""
        from hestia.api.schemas.user import ToolTrustTiersSchema
        with pytest.raises(Exception):  # ValidationError
            ToolTrustTiersSchema(read="invalid")
