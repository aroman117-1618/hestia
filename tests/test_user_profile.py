"""
Tests for the markdown-based user profile configuration system.

Tests cover:
- UserConfigFile enum and permission sets
- UserConfig model (context_block, cloud_safe_context, topic_context)
- UserCommand expansion
- UserConfigLoader (initialization, loading, parsing, commands, notes)
- UserConfigWriter (file writes, permissions, daily notes, commands)
- API route serialization
"""

import asyncio
import pytest
import tempfile
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from hestia.user.config_models import (
    AGENT_WRITABLE_FILES,
    ALWAYS_LOAD_FILES,
    LOCAL_ONLY_FILES,
    TOPIC_KEYWORDS,
    TOPIC_LOAD_FILES,
    USER_ONLY_FILES,
    DailyNote,
    UserCommand,
    UserConfig,
    UserConfigFile,
    UserIdentity,
)
from hestia.user.config_loader import UserConfigLoader
from hestia.user.config_writer import UserConfigWriter


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_user_dir(tmp_path):
    """Create a temporary user profile directory with default structure."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "memory").mkdir()
    (user_dir / "commands").mkdir()
    return user_dir


@pytest.fixture
def populated_user_dir(tmp_user_dir):
    """User directory with sample content in all files."""
    # USER-IDENTITY.md
    (tmp_user_dir / "USER-IDENTITY.md").write_text(
        "# Andrew Lonati\n\n"
        "**Timezone:** America/Los_Angeles\n"
        "**Job:** Software Engineer\n"
        "**Avatar:** (not set)\n\n"
        "## Top Contacts\n"
        "- Alice\n"
        "- Bob\n",
        encoding="utf-8"
    )

    # MIND.md
    (tmp_user_dir / "MIND.md").write_text(
        "# Mind\n\nRigorous investigation. Security obsessed.\n",
        encoding="utf-8"
    )

    # TOOLS.md
    (tmp_user_dir / "TOOLS.md").write_text(
        "# Tools\n\nMac Mini M1, 16GB.\n",
        encoding="utf-8"
    )

    # MEMORY.md
    (tmp_user_dir / "MEMORY.md").write_text(
        "# Memory\n\nPrefers dark mode.\n",
        encoding="utf-8"
    )

    # BODY.md
    (tmp_user_dir / "BODY.md").write_text(
        "# Body\n\nVitamin D, magnesium.\n",
        encoding="utf-8"
    )

    # SPIRIT.md
    (tmp_user_dir / "SPIRIT.md").write_text(
        "# Spirit\n\nStoicism. Growth mindset.\n",
        encoding="utf-8"
    )

    # VITALS.md
    (tmp_user_dir / "VITALS.md").write_text(
        "# Vitals\n\n- [ ] Hydrate\n- [ ] Move\n",
        encoding="utf-8"
    )

    # SETUP.md (empty = no pending setup)
    (tmp_user_dir / "SETUP.md").write_text("", encoding="utf-8")

    # A command
    (tmp_user_dir / "commands" / "research.md").write_text(
        "Deep research on a topic.\n\n"
        "## System Instructions\n"
        "Investigate $ARGUMENTS thoroughly.\n\n"
        "## Resources\n"
        "web, memory\n",
        encoding="utf-8"
    )

    # A daily note
    (tmp_user_dir / "memory" / "2026-02-28.md").write_text(
        "# Daily Notes — 2026-02-28\n\nWorked on user profile system.\n",
        encoding="utf-8"
    )

    return tmp_user_dir


@pytest.fixture
def sample_identity():
    return UserIdentity(
        name="Andrew Lonati",
        timezone="America/Los_Angeles",
        job="Software Engineer",
        contacts=["Alice", "Bob"],
    )


@pytest.fixture
def sample_config(tmp_user_dir, sample_identity):
    return UserConfig(
        directory_path=tmp_user_dir,
        identity=sample_identity,
        identity_md="# Andrew Lonati\n\n**Timezone:** America/Los_Angeles\n",
        mind_md="# Mind\n\nRigorous investigation.\n",
        tools_md="# Tools\n\nMac Mini M1.\n",
        memory_md="# Memory\n\nPrefers dark mode.\n",
        body_md="# Body\n\nVitamin D.\n",
        spirit_md="# Spirit\n\nStoicism.\n",
        vitals_md="# Vitals\n\n- [ ] Hydrate\n",
        setup_md="",
    )


# =============================================================================
# UserConfigFile & Permission Tests
# =============================================================================


class TestConfigFileEnums:
    """Test enum values and permission sets."""

    def test_all_files_in_enum(self):
        assert len(UserConfigFile) == 8

    def test_always_load_files(self):
        assert UserConfigFile.IDENTITY in ALWAYS_LOAD_FILES
        assert UserConfigFile.MIND in ALWAYS_LOAD_FILES
        assert UserConfigFile.TOOLS in ALWAYS_LOAD_FILES
        assert len(ALWAYS_LOAD_FILES) == 3

    def test_topic_load_files(self):
        assert UserConfigFile.BODY in TOPIC_LOAD_FILES
        assert UserConfigFile.SPIRIT in TOPIC_LOAD_FILES
        assert UserConfigFile.VITALS in TOPIC_LOAD_FILES
        assert len(TOPIC_LOAD_FILES) == 3

    def test_agent_writable_only_memory(self):
        assert AGENT_WRITABLE_FILES == {UserConfigFile.MEMORY}

    def test_user_only_files(self):
        assert UserConfigFile.IDENTITY in USER_ONLY_FILES
        assert UserConfigFile.MEMORY not in USER_ONLY_FILES

    def test_local_only_files(self):
        assert UserConfigFile.IDENTITY in LOCAL_ONLY_FILES
        assert UserConfigFile.BODY in LOCAL_ONLY_FILES
        assert UserConfigFile.MIND not in LOCAL_ONLY_FILES

    def test_topic_keywords_populated(self):
        assert len(TOPIC_KEYWORDS[UserConfigFile.BODY]) > 5
        assert "health" in TOPIC_KEYWORDS[UserConfigFile.BODY]
        assert "philosophy" in TOPIC_KEYWORDS[UserConfigFile.SPIRIT]
        assert "checklist" in TOPIC_KEYWORDS[UserConfigFile.VITALS]


# =============================================================================
# UserIdentity Tests
# =============================================================================


class TestUserIdentity:

    def test_basic_identity(self, sample_identity):
        assert sample_identity.name == "Andrew Lonati"
        assert sample_identity.timezone == "America/Los_Angeles"
        assert len(sample_identity.contacts) == 2

    def test_validation_valid(self, sample_identity):
        errors = sample_identity.validate()
        assert errors == []

    def test_validation_empty_name(self):
        identity = UserIdentity(name="")
        errors = identity.validate()
        assert len(errors) == 1
        assert "Name" in errors[0]

    def test_validation_long_name(self):
        identity = UserIdentity(name="x" * 101)
        errors = identity.validate()
        assert len(errors) == 1


# =============================================================================
# UserConfig Tests
# =============================================================================


class TestUserConfig:

    def test_name_property(self, sample_config):
        assert sample_config.name == "Andrew Lonati"

    def test_name_fallback(self, tmp_user_dir):
        config = UserConfig(
            directory_path=tmp_user_dir,
            identity=UserIdentity(name=""),
        )
        assert config.name == "User"

    def test_has_setup_false_when_empty(self, sample_config):
        assert sample_config.has_setup is False

    def test_has_setup_true_when_populated(self, sample_config):
        sample_config.setup_md = "# Setup\nInterview questions here."
        assert sample_config.has_setup is True

    def test_context_block_includes_always_files(self, sample_config):
        block = sample_config.context_block
        assert "Andrew Lonati" in block
        assert "Rigorous investigation" in block
        assert "Mac Mini M1" in block
        # Should NOT include BODY, SPIRIT, VITALS
        assert "Vitamin D" not in block
        assert "Stoicism" not in block

    def test_cloud_safe_context_excludes_pii(self, sample_config):
        safe = sample_config.get_cloud_safe_context()
        # Should include MIND and TOOLS
        assert "Rigorous investigation" in safe
        assert "Mac Mini M1" in safe
        # Should NOT include IDENTITY or BODY
        assert "Andrew Lonati" not in safe
        assert "Vitamin D" not in safe

    def test_topic_context(self, sample_config):
        context = sample_config.get_topic_context([UserConfigFile.BODY])
        assert "Vitamin D" in context

    def test_topic_context_empty(self, sample_config):
        sample_config.spirit_md = ""
        context = sample_config.get_topic_context([UserConfigFile.SPIRIT])
        assert context == ""

    def test_get_file_content(self, sample_config):
        assert "Rigorous" in sample_config.get_file_content(UserConfigFile.MIND)
        assert sample_config.get_file_content(UserConfigFile.SETUP) == ""

    def test_to_dict(self, sample_config):
        d = sample_config.to_dict()
        assert d["name"] == "Andrew Lonati"
        assert d["identity"]["timezone"] == "America/Los_Angeles"
        assert d["has_setup"] is False
        assert d["config_version"] == "1.0"
        assert "files" in d
        assert d["files"]["MIND.md"] is True
        assert d["files"]["SETUP.md"] is False

    def test_validate_valid(self, sample_config):
        assert sample_config.is_valid

    def test_validate_empty_identity(self, tmp_user_dir):
        config = UserConfig(
            directory_path=tmp_user_dir,
            identity=UserIdentity(name="Test"),
            identity_md="",
        )
        errors = config.validate()
        assert any("USER-IDENTITY.md" in e for e in errors)


# =============================================================================
# UserCommand Tests
# =============================================================================


class TestUserCommand:

    def test_expand_with_arguments(self, tmp_user_dir):
        cmd = UserCommand(
            name="research",
            file_path=tmp_user_dir / "commands" / "research.md",
            raw_content="Research $ARGUMENTS in depth.",
        )
        result = cmd.expand("quantum computing")
        assert result == "Research quantum computing in depth."

    def test_expand_no_arguments(self, tmp_user_dir):
        cmd = UserCommand(
            name="test",
            file_path=tmp_user_dir / "commands" / "test.md",
            raw_content="Run $ARGUMENTS",
        )
        result = cmd.expand()
        assert result == "Run "

    def test_to_dict(self, tmp_user_dir):
        cmd = UserCommand(
            name="research",
            file_path=tmp_user_dir / "commands" / "research.md",
            system_instructions="Be thorough",
            resources=["web", "memory"],
            description="Deep research",
        )
        d = cmd.to_dict()
        assert d["name"] == "research"
        assert d["description"] == "Deep research"
        assert d["resources"] == ["web", "memory"]
        assert d["has_system_instructions"] is True


# =============================================================================
# DailyNote Tests
# =============================================================================


class TestDailyNote:

    def test_filename(self):
        note = DailyNote(date=date(2026, 2, 28), content="Hello")
        assert note.filename == "2026-02-28.md"

    def test_relative_path(self):
        note = DailyNote(date=date(2026, 2, 28), content="Hello")
        assert note.relative_path == "memory/2026-02-28.md"


# =============================================================================
# UserConfigLoader Tests
# =============================================================================


class TestUserConfigLoader:

    @pytest.mark.asyncio
    async def test_initialize_creates_directories(self, tmp_user_dir):
        # Remove created dirs to test scaffolding
        shutil.rmtree(str(tmp_user_dir))

        loader = UserConfigLoader(user_root=tmp_user_dir)
        await loader.initialize()

        assert tmp_user_dir.exists()
        assert (tmp_user_dir / "memory").exists()
        assert (tmp_user_dir / "commands").exists()

    @pytest.mark.asyncio
    async def test_initialize_scaffolds_default_files(self, tmp_user_dir):
        # Empty dir — should scaffold defaults
        loader = UserConfigLoader(user_root=tmp_user_dir)
        await loader.initialize()

        assert (tmp_user_dir / "USER-IDENTITY.md").exists()
        assert (tmp_user_dir / "MIND.md").exists()
        assert (tmp_user_dir / "TOOLS.md").exists()

    @pytest.mark.asyncio
    async def test_initialize_scaffolds_default_commands(self, tmp_user_dir):
        loader = UserConfigLoader(user_root=tmp_user_dir)
        await loader.initialize()

        commands_dir = tmp_user_dir / "commands"
        command_files = list(commands_dir.glob("*.md"))
        assert len(command_files) > 0

    @pytest.mark.asyncio
    async def test_initialize_creates_metadata(self, tmp_user_dir):
        loader = UserConfigLoader(user_root=tmp_user_dir)
        await loader.initialize()

        meta_path = tmp_user_dir / ".user-meta.yaml"
        assert meta_path.exists()

    @pytest.mark.asyncio
    async def test_load_returns_user_config(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()
        config = await loader.load()

        assert isinstance(config, UserConfig)
        assert config.identity.name == "Andrew Lonati"
        assert config.identity.timezone == "America/Los_Angeles"
        assert config.identity.job == "Software Engineer"
        assert "Alice" in config.identity.contacts
        assert "Bob" in config.identity.contacts

    @pytest.mark.asyncio
    async def test_load_caches(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        config1 = await loader.load()
        config2 = await loader.load()
        assert config1 is config2  # Same object (cached)

    @pytest.mark.asyncio
    async def test_load_force_reload(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        config1 = await loader.load()
        config2 = await loader.load(force_reload=True)
        assert config1 is not config2  # New object

    @pytest.mark.asyncio
    async def test_parse_identity_minimal(self, tmp_user_dir):
        (tmp_user_dir / "USER-IDENTITY.md").write_text("# Jane", encoding="utf-8")

        loader = UserConfigLoader(user_root=tmp_user_dir)
        await loader.initialize()
        config = await loader.load(force_reload=True)

        assert config.identity.name == "Jane"

    @pytest.mark.asyncio
    async def test_parse_identity_empty(self, tmp_user_dir):
        (tmp_user_dir / "USER-IDENTITY.md").write_text("", encoding="utf-8")

        loader = UserConfigLoader(user_root=tmp_user_dir)
        await loader.initialize()
        config = await loader.load(force_reload=True)

        assert config.identity.name == "User"

    @pytest.mark.asyncio
    async def test_load_commands(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        commands = await loader.load_commands()
        assert "research" in commands
        assert commands["research"].system_instructions == "Investigate $ARGUMENTS thoroughly."
        assert "web" in commands["research"].resources
        assert "memory" in commands["research"].resources

    @pytest.mark.asyncio
    async def test_get_command(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        cmd = await loader.get_command("research")
        assert cmd is not None
        assert cmd.name == "research"

    @pytest.mark.asyncio
    async def test_get_command_not_found(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        cmd = await loader.get_command("nonexistent")
        assert cmd is None

    @pytest.mark.asyncio
    async def test_list_daily_notes(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        notes = await loader.list_daily_notes()
        assert len(notes) == 1
        assert notes[0].date == date(2026, 2, 28)
        assert "user profile system" in notes[0].content

    @pytest.mark.asyncio
    async def test_get_daily_note(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        note = await loader.get_daily_note(date(2026, 2, 28))
        assert note is not None
        assert "user profile system" in note.content

    @pytest.mark.asyncio
    async def test_get_daily_note_not_found(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        note = await loader.get_daily_note(date(2025, 1, 1))
        assert note is None

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        config1 = await loader.load()
        loader.invalidate_cache()
        config2 = await loader.load()
        assert config1 is not config2


# =============================================================================
# UserConfigWriter Tests
# =============================================================================


class TestUserConfigWriter:

    @pytest.fixture
    def writer_and_loader(self, populated_user_dir):
        """Create a writer with a manually set loader."""
        import hestia.user.config_loader as loader_mod

        # Reset the singleton
        old_instance = loader_mod._loader_instance
        loader_mod._loader_instance = None

        async def setup():
            loader = UserConfigLoader(user_root=populated_user_dir)
            await loader.initialize()
            loader_mod._loader_instance = loader

            writer = UserConfigWriter()
            writer._loader = loader
            return writer, loader

        result = asyncio.get_event_loop().run_until_complete(setup())

        yield result

        # Restore
        loader_mod._loader_instance = old_instance

    @pytest.mark.asyncio
    async def test_write_config_file_user(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        new_content = "# Updated Mind\n\nNew values here."
        await writer.write_config_file(UserConfigFile.MIND, new_content, source="user")

        # Verify file was written
        mind_path = populated_user_dir / "MIND.md"
        assert mind_path.read_text(encoding="utf-8") == new_content

    @pytest.mark.asyncio
    async def test_write_config_file_agent_writable(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        # Agent can write MEMORY.md
        await writer.write_config_file(
            UserConfigFile.MEMORY, "Agent memory update", source="agent"
        )
        memory_path = populated_user_dir / "MEMORY.md"
        assert memory_path.read_text(encoding="utf-8") == "Agent memory update"

    @pytest.mark.asyncio
    async def test_write_config_file_agent_denied_user_only(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        with pytest.raises(PermissionError, match="user-only"):
            await writer.write_config_file(
                UserConfigFile.IDENTITY, "Hacked!", source="agent"
            )

    @pytest.mark.asyncio
    async def test_write_config_file_agent_denied_not_writable(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        with pytest.raises(PermissionError):
            await writer.write_config_file(
                UserConfigFile.MIND, "Hacked!", source="agent"
            )

    @pytest.mark.asyncio
    async def test_write_invalidates_cache(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        # Load once to populate cache
        config1 = await loader.load()

        writer = UserConfigWriter()
        writer._loader = loader

        await writer.write_config_file(
            UserConfigFile.MIND, "# New Mind", source="user"
        )

        # Cache should be invalidated, next load returns new data
        config2 = await loader.load()
        assert config2 is not config1
        assert "New Mind" in config2.mind_md

    @pytest.mark.asyncio
    async def test_append_memory(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        await writer.append_memory("User prefers terminal tools.")

        memory_path = populated_user_dir / "MEMORY.md"
        content = memory_path.read_text(encoding="utf-8")
        assert "User prefers terminal tools." in content
        assert "Prefers dark mode" in content  # Original still there

    @pytest.mark.asyncio
    async def test_write_daily_note(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        note = await writer.write_daily_note(
            "Test note content", note_date=date(2026, 3, 1)
        )

        assert note.date == date(2026, 3, 1)
        note_path = populated_user_dir / "memory" / "2026-03-01.md"
        assert note_path.exists()
        assert note_path.read_text(encoding="utf-8") == "Test note content"

    @pytest.mark.asyncio
    async def test_append_daily_note(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        note = await writer.append_daily_note(
            "New entry", note_date=date(2026, 2, 28)
        )

        content = note.content
        assert "Daily Notes — 2026-02-28" in content
        assert "New entry" in content

    @pytest.mark.asyncio
    async def test_append_daily_note_new_date(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        note = await writer.append_daily_note(
            "First entry", note_date=date(2026, 4, 1)
        )

        assert "Daily Notes — 2026-04-01" in note.content
        assert "First entry" in note.content

    @pytest.mark.asyncio
    async def test_write_command(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        await writer.write_command("test-cmd", "# Test Command\n\nDo things.")

        cmd_path = populated_user_dir / "commands" / "test-cmd.md"
        assert cmd_path.exists()
        assert "Do things" in cmd_path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_delete_command(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        result = await writer.delete_command("research")
        assert result is True
        assert not (populated_user_dir / "commands" / "research.md").exists()

    @pytest.mark.asyncio
    async def test_delete_command_not_found(self, populated_user_dir):
        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        result = await writer.delete_command("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_complete_setup(self, populated_user_dir):
        # Write a SETUP.md with content
        (populated_user_dir / "SETUP.md").write_text(
            "# Setup\nOnboarding questions", encoding="utf-8"
        )

        loader = UserConfigLoader(user_root=populated_user_dir)
        await loader.initialize()

        writer = UserConfigWriter()
        writer._loader = loader

        await writer.complete_setup()

        assert not (populated_user_dir / "SETUP.md").exists()
        assert (populated_user_dir / ".archived-SETUP.md").exists()
