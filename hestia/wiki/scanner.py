"""
Source file scanner for wiki staleness detection.

Reads module source files from disk and computes content
hashes for determining when cached articles are outdated.
"""

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent


class WikiScanner:
    """
    Scans Hestia source files for wiki content generation.

    Computes SHA256 hashes of module source files to detect
    when cached wiki articles are stale.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize scanner.

        Args:
            project_root: Root of the Hestia project.
                          Defaults to ~/hestia
        """
        if project_root is None:
            project_root = Path.home() / "hestia"

        self.project_root = Path(project_root)
        self.backend_root = self.project_root / "hestia"
        self.docs_root = self.project_root / "docs"
        self.logger = get_logger()

    def get_module_source(self, module_name: str) -> str:
        """
        Read key source files from a module for generation context.

        Reads models.py, manager.py, database.py (the standard triple)
        plus __init__.py. Intelligently excerpts to stay within
        reasonable context limits (~8K tokens).

        Args:
            module_name: Module directory name (e.g., "memory").

        Returns:
            Concatenated source content with file headers.
        """
        module_path = self.backend_root / module_name
        if not module_path.is_dir():
            return ""

        # Priority order for module files
        priority_files = [
            "__init__.py",
            "models.py",
            "manager.py",
            "database.py",
        ]

        parts: List[str] = []
        total_chars = 0
        char_limit = 12000  # ~3K tokens, leaves room for prompt

        # Read priority files first
        for filename in priority_files:
            filepath = module_path / filename
            if filepath.exists() and total_chars < char_limit:
                content = self._read_file_excerpted(filepath, char_limit - total_chars)
                if content:
                    parts.append(f"### {module_name}/{filename}\n```python\n{content}\n```")
                    total_chars += len(content)

        # Then scan for other .py files not in priority list
        for filepath in sorted(module_path.glob("*.py")):
            if filepath.name not in priority_files and total_chars < char_limit:
                content = self._read_file_excerpted(filepath, char_limit - total_chars)
                if content:
                    parts.append(f"### {module_name}/{filepath.name}\n```python\n{content}\n```")
                    total_chars += len(content)

        return "\n\n".join(parts)

    def get_module_hash(self, module_name: str) -> str:
        """
        Compute SHA256 hash of a module's source files.

        Args:
            module_name: Module directory name.

        Returns:
            Hex-encoded SHA256 hash.
        """
        module_path = self.backend_root / module_name
        if not module_path.is_dir():
            return ""

        hasher = hashlib.sha256()

        for filepath in sorted(module_path.glob("*.py")):
            try:
                content = filepath.read_text(encoding="utf-8")
                hasher.update(content.encode("utf-8"))
            except (OSError, UnicodeDecodeError):
                continue

        return hasher.hexdigest()

    def get_project_overview_source(self) -> str:
        """
        Read CLAUDE.md as the source for overview generation.

        Returns:
            CLAUDE.md content.
        """
        claude_md = self.project_root / "CLAUDE.md"
        if claude_md.exists():
            try:
                return claude_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                pass
        return ""

    def get_overview_hash(self) -> str:
        """Compute hash of CLAUDE.md for staleness detection."""
        content = self.get_project_overview_source()
        if not content:
            return ""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_decision_log(self) -> str:
        """Read the decision log markdown file."""
        path = self.docs_root / "hestia-decision-log.md"
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                pass
        return ""

    def get_development_plan(self) -> str:
        """Read the development plan markdown file."""
        path = self.docs_root / "hestia-development-plan.md"
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                pass
        return ""

    def parse_decisions(self) -> List[Dict[str, Any]]:
        """
        Parse the decision log into individual ADR entries.

        Returns:
            List of dicts with keys: number, title, date, status,
            context, decision, alternatives, consequences, notes.
        """
        content = self.get_decision_log()
        if not content:
            return []

        decisions: List[Dict[str, Any]] = []

        # Split by ADR headers: ### ADR-NNN: Title
        adr_pattern = re.compile(
            r'^### (ADR-\d+):\s*(.+)$',
            re.MULTILINE,
        )

        matches = list(adr_pattern.finditer(content))

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section = content[start:end].strip()

            adr_number = match.group(1)
            title = match.group(2).strip()

            # Extract fields
            date = self._extract_field(section, r'\*\*Date\*\*:\s*(.+)')
            adr_status = self._extract_field(section, r'\*\*Status\*\*:\s*(.+)')

            # Extract sections
            context = self._extract_section(section, "Context")
            decision = self._extract_section(section, "Decision")
            alternatives = self._extract_section(section, "Alternatives Considered")
            consequences = self._extract_section(section, "Consequences")
            notes = self._extract_section(section, "Notes")

            decisions.append({
                "number": adr_number,
                "title": title,
                "date": date or "Unknown",
                "status": adr_status or "Accepted",
                "context": context,
                "decision": decision,
                "alternatives": alternatives,
                "consequences": consequences,
                "notes": notes,
            })

        return decisions

    def parse_roadmap(self) -> Dict[str, Any]:
        """
        Parse the development plan into structured roadmap data.

        Returns:
            Dict with milestones, current_state, whats_next.
        """
        content = self.get_development_plan()
        if not content:
            return {"milestones": [], "current_state": "", "whats_next": ""}

        # The development plan is already well-structured markdown
        # Return it as structured data for the API
        return {
            "content": content,
            "source": "docs/hestia-development-plan.md",
        }

    def list_modules(self) -> List[str]:
        """
        List all Hestia backend modules.

        Returns:
            Sorted list of module directory names.
        """
        modules = []
        if self.backend_root.is_dir():
            for path in sorted(self.backend_root.iterdir()):
                if (
                    path.is_dir()
                    and not path.name.startswith("_")
                    and not path.name.startswith(".")
                    and (path / "__init__.py").exists()
                ):
                    modules.append(path.name)
        return modules

    def check_staleness(
        self,
        article_id: str,
        stored_hash: Optional[str],
    ) -> bool:
        """
        Check if an article's source has changed since generation.

        Args:
            article_id: Article ID (e.g., "module-memory", "overview").
            stored_hash: Hash stored when article was generated.

        Returns:
            True if stale (source changed), False if fresh.
        """
        if not stored_hash:
            return True

        if article_id == "overview":
            current_hash = self.get_overview_hash()
        elif article_id.startswith("module-"):
            module_name = article_id.replace("module-", "")
            current_hash = self.get_module_hash(module_name)
        else:
            return False  # Static articles (decisions, roadmap) aren't hash-checked

        return current_hash != stored_hash

    def _read_file_excerpted(self, filepath: Path, max_chars: int) -> str:
        """Read a file, truncating if necessary."""
        try:
            content = filepath.read_text(encoding="utf-8")
            if len(content) > max_chars:
                content = content[:max_chars] + "\n# ... (truncated)"
            return content
        except (OSError, UnicodeDecodeError):
            return ""

    def _extract_field(self, text: str, pattern: str) -> Optional[str]:
        """Extract a single-line field from markdown text."""
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_section(self, text: str, heading: str) -> str:
        """Extract content under a #### heading until the next heading."""
        pattern = re.compile(
            rf'^####\s+{re.escape(heading)}\s*\n(.*?)(?=^####|\Z)',
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        return ""
