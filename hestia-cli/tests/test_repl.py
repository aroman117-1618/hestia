"""Tests for REPL tab completion."""

from prompt_toolkit.document import Document

from hestia_cli.repl import SlashCommandCompleter


class TestSlashCommandCompleter:
    """Tests for slash command and @mode tab completion."""

    def _get_completions(self, text: str) -> list:
        """Helper: get completion texts for a given input."""
        completer = SlashCommandCompleter()
        doc = Document(text, cursor_position=len(text))
        return [c.text for c in completer.get_completions(doc, None)]

    def test_slash_prefix_shows_commands(self):
        """Typing / shows all slash commands."""
        completions = self._get_completions("/")
        assert "/help" in completions
        assert "/exit" in completions
        assert "/tools" in completions

    def test_partial_slash_filters(self):
        """Typing /he filters to /help."""
        completions = self._get_completions("/he")
        assert "/help" in completions
        assert "/exit" not in completions

    def test_full_command_matches_exact(self):
        """Typing full command still shows it as completion."""
        completions = self._get_completions("/help")
        assert "/help" in completions

    def test_no_completions_after_space(self):
        """No completions after a space (subcommand args)."""
        completions = self._get_completions("/trust ")
        assert completions == []

    def test_at_mode_completion(self):
        """Typing @ shows mode completions."""
        completions = self._get_completions("@")
        assert any("@tia" in c for c in completions)
        assert any("@mira" in c for c in completions)
        assert any("@olly" in c for c in completions)

    def test_partial_at_mode(self):
        """Typing @m filters to @mira."""
        completions = self._get_completions("@m")
        assert any("@mira" in c for c in completions)
        assert not any("@tia" in c for c in completions)

    def test_regular_text_no_completions(self):
        """Regular text does not trigger completions."""
        completions = self._get_completions("hello")
        assert completions == []

    def test_completions_have_descriptions(self):
        """Completions include display_meta descriptions."""
        completer = SlashCommandCompleter()
        doc = Document("/he", cursor_position=3)
        completions = list(completer.get_completions(doc, None))
        assert len(completions) > 0
        assert completions[0].display_meta is not None
