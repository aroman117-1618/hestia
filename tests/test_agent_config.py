"""
Tests for the .md-based agent configuration system (Phase 0.1).

Tests ConfigLoader, ConfigWriter, config_models, and templates.

Run with: python -m pytest tests/test_agent_config.py -v
"""

import asyncio
import tempfile
from datetime import datetime, timezone, date
from pathlib import Path

import pytest
import pytest_asyncio

from hestia.agents.config_models import (
    AgentConfig,
    AgentConfigFile,
    AgentIdentity,
    AgentRegistry,
    DailyNote,
    AGENT_WRITABLE_FILES,
    AGENT_CONFIRM_FILES,
    USER_ONLY_FILES,
    REQUIRED_FILES,
)
from hestia.agents.config_loader import ConfigLoader
from hestia.agents.config_writer import ConfigWriter, ConfigPermissionError
from hestia.agents.templates import (
    DEFAULT_AGENT_TEMPLATES,
    NEW_AGENT_TEMPLATE,
    TIA_TEMPLATES,
    MIRA_TEMPLATES,
    OLLY_TEMPLATES,
    LEGACY_SLOT_MAP,
)


# ============== Fixtures ==============

@pytest.fixture
def temp_agents_root(tmp_path):
    """Create a temporary agents root directory."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    return agents_dir


@pytest_asyncio.fixture
async def config_loader(temp_agents_root):
    """Create a ConfigLoader with temp directory."""
    loader = ConfigLoader(agents_root=temp_agents_root)
    await loader.initialize()
    return loader


@pytest_asyncio.fixture
async def config_writer(config_loader):
    """Create a ConfigWriter backed by the test loader."""
    return ConfigWriter(config_loader)


# ============== AgentIdentity Tests ==============

class TestAgentIdentity:
    """Tests for AgentIdentity model."""

    def test_create_minimal(self):
        """Minimal identity with just a name."""
        identity = AgentIdentity(name="TestBot")
        assert identity.name == "TestBot"
        assert identity.gradient_color_1 == "808080"
        assert identity.temperature == 0.0

    def test_validate_valid(self):
        """Valid identity passes validation."""
        identity = AgentIdentity(
            name="Tia",
            gradient_color_1="E0A050",
            gradient_color_2="8B3A0F",
        )
        assert identity.validate() == []

    def test_validate_empty_name(self):
        """Empty name fails validation."""
        identity = AgentIdentity(name="")
        errors = identity.validate()
        assert any("Name" in e for e in errors)

    def test_validate_long_name(self):
        """Name over 50 chars fails validation."""
        identity = AgentIdentity(name="A" * 51)
        errors = identity.validate()
        assert any("Name" in e for e in errors)

    def test_validate_bad_hex(self):
        """Invalid hex color fails validation."""
        identity = AgentIdentity(name="Test", gradient_color_1="ZZZZZZ")
        errors = identity.validate()
        assert any("gradient_color_1" in e for e in errors)


# ============== AgentConfig Tests ==============

class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_system_prompt_assembly(self):
        """System prompt assembled from ANIMA + AGENT + USER."""
        config = AgentConfig(
            directory_name="test",
            directory_path=Path("/tmp/test"),
            identity=AgentIdentity(name="TestBot"),
            anima_md="You are TestBot, a helpful assistant.",
            agent_md="Be accurate and concise.",
            user_md="User prefers direct communication.",
        )
        prompt = config.system_prompt
        assert "TestBot" in prompt
        assert "accurate" in prompt
        assert "direct communication" in prompt

    def test_system_prompt_fallback(self):
        """Fallback prompt when no content."""
        config = AgentConfig(
            directory_name="empty",
            directory_path=Path("/tmp/empty"),
            identity=AgentIdentity(name="EmptyBot"),
        )
        assert "EmptyBot" in config.system_prompt

    def test_validate_missing_content(self):
        """Validation fails without ANIMA or AGENT content."""
        config = AgentConfig(
            directory_name="test",
            directory_path=Path("/tmp/test"),
            identity=AgentIdentity(name="Test"),
        )
        errors = config.validate()
        assert any("ANIMA" in e or "AGENT" in e for e in errors)

    def test_validate_valid(self):
        """Valid config passes validation."""
        config = AgentConfig(
            directory_name="test",
            directory_path=Path("/tmp/test"),
            identity=AgentIdentity(name="Test"),
            anima_md="You are Test, a helpful assistant.",
        )
        assert config.is_valid

    def test_to_dict(self):
        """Serialization includes all key fields."""
        config = AgentConfig(
            directory_name="test",
            directory_path=Path("/tmp/test"),
            identity=AgentIdentity(name="Test", emoji="🤖"),
            anima_md="Some personality",
            is_default=True,
        )
        d = config.to_dict()
        assert d["directory_name"] == "test"
        assert d["name"] == "Test"
        assert d["identity"]["emoji"] == "🤖"
        assert d["is_default"] is True
        assert "ANIMA.md" in d["files"]

    def test_has_bootstrap(self):
        """has_bootstrap reflects BOOTSTRAP.md content."""
        config = AgentConfig(
            directory_name="test",
            directory_path=Path("/tmp/test"),
            identity=AgentIdentity(name="Test"),
            bootstrap_md="## Onboarding\nSome questions...",
        )
        assert config.has_bootstrap is True

        config.bootstrap_md = ""
        assert config.has_bootstrap is False

    def test_get_file_content(self):
        """get_file_content returns correct content for each file."""
        config = AgentConfig(
            directory_name="test",
            directory_path=Path("/tmp/test"),
            identity=AgentIdentity(name="Test"),
            agent_md="Rules here",
            anima_md="Personality here",
        )
        assert config.get_file_content(AgentConfigFile.AGENT) == "Rules here"
        assert config.get_file_content(AgentConfigFile.ANIMA) == "Personality here"

    def test_to_legacy_profile(self):
        """Converts to legacy AgentProfile for v1 compat."""
        config = AgentConfig(
            directory_name="tia",
            directory_path=Path("/tmp/tia"),
            identity=AgentIdentity(
                name="Tia",
                gradient_color_1="E0A050",
                gradient_color_2="8B3A0F",
            ),
            anima_md="You are Tia.",
            is_default=True,
        )
        profile = config.to_legacy_profile(slot_index=0)
        assert profile.name == "Tia"
        assert profile.slot_index == 0
        assert profile.gradient_color_1 == "E0A050"
        assert profile.is_default is True


# ============== AgentRegistry Tests ==============

class TestAgentRegistry:
    """Tests for AgentRegistry model."""

    def test_default_registry(self):
        """Default registry has tia as default."""
        registry = AgentRegistry()
        assert registry.default_agent == "tia"

    def test_serialization(self):
        """Round-trip serialization."""
        registry = AgentRegistry(
            default_agent="mira",
            agents=["tia", "mira", "olly"],
        )
        d = registry.to_dict()
        restored = AgentRegistry.from_dict(d)
        assert restored.default_agent == "mira"
        assert restored.agents == ["tia", "mira", "olly"]


# ============== Template Tests ==============

class TestTemplates:
    """Tests for default agent templates."""

    def test_all_defaults_have_required_files(self):
        """All default agents have IDENTITY, ANIMA, AGENT."""
        for name, templates in DEFAULT_AGENT_TEMPLATES.items():
            for required in REQUIRED_FILES:
                assert required in templates, f"{name} missing {required.value}"
                assert templates[required].strip(), f"{name} has empty {required.value}"

    def test_tia_identity_parseable(self):
        """Tia's IDENTITY.md contains expected fields."""
        content = TIA_TEMPLATES[AgentConfigFile.IDENTITY]
        assert "# Tia" in content
        assert "Hestia" in content
        assert "E0A050" in content
        assert "8B3A0F" in content

    def test_new_agent_template_has_placeholder(self):
        """New agent template uses {name} and {slug} placeholders where applicable."""
        # At least IDENTITY and ANIMA should reference the agent name
        identity = NEW_AGENT_TEMPLATE[AgentConfigFile.IDENTITY]
        formatted = identity.format(name="TestBot", slug="testbot")
        assert "TestBot" in formatted

        anima = NEW_AGENT_TEMPLATE[AgentConfigFile.ANIMA]
        formatted = anima.format(name="TestBot", slug="testbot")
        assert "TestBot" in formatted

        # All templates should be formattable without errors
        for config_file, template in NEW_AGENT_TEMPLATE.items():
            if template:
                template.format(name="TestBot", slug="testbot")  # Should not raise

    def test_legacy_slot_map(self):
        """Legacy slot mapping is correct."""
        assert LEGACY_SLOT_MAP["tia"] == 0
        assert LEGACY_SLOT_MAP["mira"] == 1
        assert LEGACY_SLOT_MAP["olly"] == 2


# ============== ConfigLoader Tests ==============

class TestConfigLoader:
    """Tests for ConfigLoader."""

    @pytest.mark.asyncio
    async def test_initialize_creates_defaults(self, config_loader, temp_agents_root):
        """Initialization scaffolds default agents."""
        assert (temp_agents_root / "tia").is_dir()
        assert (temp_agents_root / "mira").is_dir()
        assert (temp_agents_root / "olly").is_dir()
        assert (temp_agents_root / ".archived").is_dir()

    @pytest.mark.asyncio
    async def test_initialize_creates_registry(self, config_loader, temp_agents_root):
        """Initialization creates .hestia-agents.yaml."""
        assert (temp_agents_root / ".hestia-agents.yaml").exists()

    @pytest.mark.asyncio
    async def test_list_agents(self, config_loader):
        """Lists all default agents."""
        agents = await config_loader.list_agents()
        names = [a.directory_name for a in agents]
        assert "tia" in names
        assert "mira" in names
        assert "olly" in names
        assert len(agents) == 3

    @pytest.mark.asyncio
    async def test_get_agent(self, config_loader):
        """Gets a single agent by name."""
        tia = await config_loader.get_agent("tia")
        assert tia is not None
        assert tia.identity.name == "Tia"
        assert tia.identity.gradient_color_1 == "E0A050"
        assert tia.is_default is True

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, config_loader):
        """Returns None for unknown agent."""
        result = await config_loader.get_agent("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_default_agent(self, config_loader):
        """Gets the default agent (tia)."""
        default = await config_loader.get_default_agent()
        assert default is not None
        assert default.directory_name == "tia"

    @pytest.mark.asyncio
    async def test_identity_parsing(self, config_loader):
        """IDENTITY.md fields are parsed correctly."""
        tia = await config_loader.get_agent("tia")
        assert tia.identity.full_name == "Hestia"
        assert tia.identity.emoji == "🔥"
        assert tia.identity.temperature == 0.0
        assert "tia" in tia.identity.invoke_pattern

    @pytest.mark.asyncio
    async def test_mira_identity(self, config_loader):
        """Mira's identity is parsed correctly."""
        mira = await config_loader.get_agent("mira")
        assert mira.identity.name == "Mira"
        assert mira.identity.full_name == "Artemis"
        assert mira.identity.temperature == 0.3

    @pytest.mark.asyncio
    async def test_system_prompt_has_content(self, config_loader):
        """System prompt is non-empty and contains personality."""
        tia = await config_loader.get_agent("tia")
        prompt = tia.system_prompt
        assert len(prompt) > 100
        assert "Hestia" in prompt or "Tia" in prompt

    @pytest.mark.asyncio
    async def test_create_agent(self, config_loader, temp_agents_root):
        """Creates a new agent with templates."""
        new_agent = await config_loader.create_agent("Research Bot", slug="research-bot")
        assert new_agent is not None
        assert new_agent.directory_name == "research-bot"
        assert new_agent.identity.name == "Research Bot"
        assert (temp_agents_root / "research-bot").is_dir()
        assert (temp_agents_root / "research-bot" / "ANIMA.md").exists()
        assert new_agent.has_bootstrap  # New agents have BOOTSTRAP.md

    @pytest.mark.asyncio
    async def test_create_agent_auto_slug(self, config_loader, temp_agents_root):
        """Auto-generates slug from name."""
        new_agent = await config_loader.create_agent("My Cool Bot")
        assert new_agent.directory_name == "my-cool-bot"

    @pytest.mark.asyncio
    async def test_create_agent_duplicate(self, config_loader):
        """Rejects duplicate agent names."""
        with pytest.raises(ValueError, match="already exists"):
            await config_loader.create_agent("Tia", slug="tia")

    @pytest.mark.asyncio
    async def test_archive_agent(self, config_loader, temp_agents_root):
        """Archives a non-default agent."""
        await config_loader.create_agent("Temp Bot", slug="temp-bot")
        success = await config_loader.archive_agent("temp-bot")
        assert success is True
        assert not (temp_agents_root / "temp-bot").exists()

        # Check archived directory has it
        archived = list((temp_agents_root / ".archived").iterdir())
        assert any("temp-bot" in d.name for d in archived)

    @pytest.mark.asyncio
    async def test_archive_default_agent_blocked(self, config_loader):
        """Cannot archive the default agent."""
        with pytest.raises(ValueError, match="Cannot archive"):
            await config_loader.archive_agent("tia")

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, config_loader, temp_agents_root):
        """Cache invalidation forces re-read from disk."""
        tia = await config_loader.get_agent("tia")
        assert tia.identity.name == "Tia"

        # Modify file on disk
        identity_path = temp_agents_root / "tia" / "IDENTITY.md"
        content = identity_path.read_text()
        identity_path.write_text(content.replace("# Tia", "# TiaModified"))

        # Still cached
        tia_cached = await config_loader.get_agent("tia")
        assert tia_cached.identity.name == "Tia"

        # After invalidation
        config_loader.invalidate_cache("tia")
        tia_fresh = await config_loader.get_agent("tia")
        assert tia_fresh.identity.name == "TiaModified"

    @pytest.mark.asyncio
    async def test_registry_sync(self, config_loader, temp_agents_root):
        """Registry syncs with actual directories."""
        # Create a directory directly (simulating external creation)
        (temp_agents_root / "external-bot").mkdir()
        (temp_agents_root / "external-bot" / "IDENTITY.md").write_text("# External")
        (temp_agents_root / "external-bot" / "ANIMA.md").write_text("You are External.")

        # Reload all
        await config_loader.reload_all()
        registry = await config_loader.get_registry()
        assert "external-bot" in registry.agents


# ============== ConfigWriter Tests ==============

class TestConfigWriter:
    """Tests for ConfigWriter."""

    @pytest.mark.asyncio
    async def test_write_config_file(self, config_writer, config_loader, temp_agents_root):
        """Writes a config file to disk."""
        await config_writer.write_config_file(
            agent_name="tia",
            config_file=AgentConfigFile.AGENT,
            content="## Updated Rules\n\nNew rules here.",
        )

        # Verify file on disk
        file_path = temp_agents_root / "tia" / "AGENT.md"
        assert "Updated Rules" in file_path.read_text()

        # Verify cache invalidated (next read picks up change)
        tia = await config_loader.get_agent("tia")
        assert "Updated Rules" in tia.agent_md

    @pytest.mark.asyncio
    async def test_agent_write_memory_allowed(self, config_writer):
        """Agent can write to MEMORY.md without confirmation."""
        await config_writer.write_config_file(
            agent_name="tia",
            config_file=AgentConfigFile.MEMORY,
            content="## Updated Memory\n\nNew memory.",
            source="agent",
        )

    @pytest.mark.asyncio
    async def test_agent_write_anima_needs_confirmation(self, config_writer):
        """Agent cannot write to ANIMA.md without confirmation."""
        with pytest.raises(ConfigPermissionError):
            await config_writer.write_config_file(
                agent_name="tia",
                config_file=AgentConfigFile.ANIMA,
                content="New personality",
                source="agent",
                confirmed=False,
            )

    @pytest.mark.asyncio
    async def test_agent_write_anima_with_confirmation(self, config_writer):
        """Agent can write to ANIMA.md with confirmation."""
        await config_writer.write_config_file(
            agent_name="tia",
            config_file=AgentConfigFile.ANIMA,
            content="New confirmed personality",
            source="agent",
            confirmed=True,
        )

    @pytest.mark.asyncio
    async def test_agent_write_user_only_blocked(self, config_writer):
        """Agent cannot write to user-only files."""
        with pytest.raises(ConfigPermissionError):
            await config_writer.write_config_file(
                agent_name="tia",
                config_file=AgentConfigFile.HEARTBEAT,
                content="Modified heartbeat",
                source="agent",
            )

    @pytest.mark.asyncio
    async def test_user_write_any_file(self, config_writer):
        """User can write to any file."""
        await config_writer.write_config_file(
            agent_name="tia",
            config_file=AgentConfigFile.HEARTBEAT,
            content="## Custom Heartbeat\n\n- [ ] Check stuff",
            source="user",
        )

    @pytest.mark.asyncio
    async def test_append_daily_note(self, config_writer, temp_agents_root):
        """Appends to today's daily note."""
        note = await config_writer.append_daily_note(
            agent_name="tia",
            entry="Discussed project Hestia workspace revamp.",
        )
        assert note.date == date.today()
        assert "workspace revamp" in note.content

        # Verify file exists
        expected_path = temp_agents_root / "tia" / "memory" / f"{date.today().isoformat()}.md"
        assert expected_path.exists()

    @pytest.mark.asyncio
    async def test_append_daily_note_cumulative(self, config_writer):
        """Multiple appends accumulate in the same file."""
        await config_writer.append_daily_note("tia", "First entry.")
        note = await config_writer.append_daily_note("tia", "Second entry.")
        assert "First entry" in note.content
        assert "Second entry" in note.content

    @pytest.mark.asyncio
    async def test_read_daily_note(self, config_writer):
        """Reads a daily note by date."""
        await config_writer.append_daily_note("tia", "Test note.")
        note = await config_writer.read_daily_note("tia")
        assert note is not None
        assert "Test note" in note.content

    @pytest.mark.asyncio
    async def test_read_daily_note_not_found(self, config_writer):
        """Returns None for missing daily note."""
        note = await config_writer.read_daily_note("tia", note_date=date(2020, 1, 1))
        assert note is None

    @pytest.mark.asyncio
    async def test_list_daily_notes(self, config_writer):
        """Lists daily notes."""
        await config_writer.append_daily_note("tia", "Today's note.")
        notes = await config_writer.list_daily_notes("tia")
        assert len(notes) >= 1
        assert notes[0].agent_name == "tia"

    @pytest.mark.asyncio
    async def test_append_memory(self, config_writer, config_loader):
        """Appends to MEMORY.md."""
        await config_writer.append_memory("tia", "Andrew prefers morning meetings.")

        tia = await config_loader.get_agent("tia")
        assert "morning meetings" in tia.memory_md

    @pytest.mark.asyncio
    async def test_complete_bootstrap(self, config_writer, config_loader, temp_agents_root):
        """Completing bootstrap removes BOOTSTRAP.md."""
        # Create agent with bootstrap
        await config_loader.create_agent("NewBot", slug="newbot")
        newbot = await config_loader.get_agent("newbot")
        assert newbot.has_bootstrap

        # Complete bootstrap
        await config_writer.complete_bootstrap("newbot")
        newbot = await config_loader.reload_agent("newbot")
        assert not newbot.has_bootstrap
        assert not (temp_agents_root / "newbot" / "BOOTSTRAP.md").exists()

    @pytest.mark.asyncio
    async def test_update_identity(self, config_writer, config_loader):
        """Updates IDENTITY.md from AgentIdentity object."""
        new_identity = AgentIdentity(
            name="TiaRenamed",
            full_name="Hestia Renamed",
            emoji="✨",
            gradient_color_1="FF0000",
            gradient_color_2="0000FF",
        )
        await config_writer.update_identity("tia", new_identity)

        tia = await config_loader.reload_agent("tia")
        assert tia.identity.name == "TiaRenamed"
        assert tia.identity.emoji == "✨"
        assert tia.identity.gradient_color_1 == "FF0000"


# ============== Permission Model Tests ==============

class TestPermissionModel:
    """Tests for the file permission system."""

    def test_writable_files(self):
        """MEMORY.md is agent-writable."""
        assert AgentConfigFile.MEMORY in AGENT_WRITABLE_FILES

    def test_confirm_files(self):
        """Personality/identity files require confirmation."""
        assert AgentConfigFile.ANIMA in AGENT_CONFIRM_FILES
        assert AgentConfigFile.AGENT in AGENT_CONFIRM_FILES
        assert AgentConfigFile.USER in AGENT_CONFIRM_FILES
        assert AgentConfigFile.IDENTITY in AGENT_CONFIRM_FILES

    def test_user_only_files(self):
        """Heartbeat, Boot, Tools are user-only."""
        assert AgentConfigFile.HEARTBEAT in USER_ONLY_FILES
        assert AgentConfigFile.BOOT in USER_ONLY_FILES
        assert AgentConfigFile.TOOLS in USER_ONLY_FILES

    def test_no_overlap(self):
        """Permission sets don't overlap."""
        assert AGENT_WRITABLE_FILES.isdisjoint(AGENT_CONFIRM_FILES)
        assert AGENT_WRITABLE_FILES.isdisjoint(USER_ONLY_FILES)
        assert AGENT_CONFIRM_FILES.isdisjoint(USER_ONLY_FILES)
