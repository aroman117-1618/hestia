"""
Tests for Hestia Wiki module.

Architecture field guide — models, database, scanner,
manager, and generator with mocked cloud calls.

Run with: python -m pytest tests/test_wiki.py -v
"""

import asyncio
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from hestia.wiki.models import WikiArticle, ArticleType, GenerationStatus
from hestia.wiki.database import WikiDatabase
from hestia.wiki.scanner import WikiScanner
from hestia.wiki.manager import WikiManager
from hestia.wiki.generator import WikiGenerator


# ============== Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_article() -> WikiArticle:
    """Create a sample wiki article."""
    return WikiArticle.create(
        article_type=ArticleType.MODULE,
        title="Memory Layer",
        subtitle="How Hestia remembers",
        content="# Memory Layer\n\nThe memory module handles...",
        module_name="memory",
        source_hash="abc123",
        generation_status=GenerationStatus.COMPLETE,
    )


@pytest.fixture
def sample_decision_article() -> WikiArticle:
    """Create a sample decision article."""
    return WikiArticle.create(
        article_type=ArticleType.DECISION,
        title="ADR-001: Qwen 2.5 7B as Primary Model",
        subtitle="Accepted",
        content="**Date**: 2025-01-01\n\n### Context\nNeed local model...",
        module_name="adr-001",
        generation_status=GenerationStatus.STATIC,
    )


@pytest.fixture
def project_fixture(temp_dir: Path) -> Path:
    """Create a mock project structure for scanner tests."""
    # Create module directories
    memory_dir = temp_dir / "hestia" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "__init__.py").write_text('"""Memory module."""\n')
    (memory_dir / "models.py").write_text('class MemoryChunk:\n    pass\n')
    (memory_dir / "manager.py").write_text('class MemoryManager:\n    pass\n')
    (memory_dir / "database.py").write_text('class MemoryDatabase:\n    pass\n')

    security_dir = temp_dir / "hestia" / "security"
    security_dir.mkdir(parents=True)
    (security_dir / "__init__.py").write_text('"""Security module."""\n')
    (security_dir / "manager.py").write_text('class SecurityManager:\n    pass\n')

    # Create docs
    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "hestia-decision-log.md").write_text(
        "# Decision Log\n\n---\n\n## Decisions\n\n"
        "### ADR-001: Test Decision\n\n"
        "**Date**: 2025-01-01\n"
        "**Status**: Accepted\n\n"
        "#### Context\nSome context here.\n\n"
        "#### Decision\nWe decided to do X.\n\n"
        "#### Alternatives Considered\nOption A, Option B.\n\n"
        "#### Consequences\nGood: faster. Bad: more complex.\n\n"
        "---\n\n"
        "### ADR-002: Second Decision\n\n"
        "**Date**: 2025-02-01\n"
        "**Status**: Accepted\n\n"
        "#### Context\nAnother context.\n\n"
        "#### Decision\nWe chose Y.\n"
    )
    (docs_dir / "hestia-development-plan.md").write_text(
        "# Hestia Development Plan\n\n**Status**: All complete.\n\n"
        "## Completed Milestones\n\n| Phase | Status |\n|---|---|\n| 0 | COMPLETE |\n"
    )

    # Create CLAUDE.md
    (temp_dir / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\nHestia is a locally-hosted AI assistant.\n"
    )

    return temp_dir


# ============== Model Tests ==============

class TestWikiArticle:
    """Tests for WikiArticle dataclass."""

    def test_create_module_article(self) -> None:
        """Test creating a module article."""
        article = WikiArticle.create(
            article_type=ArticleType.MODULE,
            title="Memory Layer",
            subtitle="How Hestia remembers",
            content="Some content about memory.",
            module_name="memory",
        )
        assert article.id == "module-memory"
        assert article.article_type == ArticleType.MODULE
        assert article.title == "Memory Layer"
        assert article.word_count == 4
        assert article.estimated_read_time == 1

    def test_create_overview_article(self) -> None:
        """Test creating an overview article."""
        article = WikiArticle.create(
            article_type=ArticleType.OVERVIEW,
            title="Architecture Overview",
        )
        assert article.id == "overview"
        assert article.article_type == ArticleType.OVERVIEW

    def test_create_decision_article(self) -> None:
        """Test creating a decision article."""
        article = WikiArticle.create(
            article_type=ArticleType.DECISION,
            title="ADR-001: Test",
            module_name="adr-001",
        )
        assert article.id == "decision-adr-001"

    def test_create_diagram_article(self) -> None:
        """Test creating a diagram article."""
        article = WikiArticle.create(
            article_type=ArticleType.DIAGRAM,
            title="System Architecture",
            module_name="architecture",
        )
        assert article.id == "diagram-architecture"

    def test_word_count_and_read_time(self) -> None:
        """Test word count and reading time calculation."""
        # 400 words = 2 min read at 200 wpm
        content = " ".join(["word"] * 400)
        article = WikiArticle.create(
            article_type=ArticleType.OVERVIEW,
            title="Test",
            content=content,
        )
        assert article.word_count == 400
        assert article.estimated_read_time == 2

    def test_to_dict(self, sample_article: WikiArticle) -> None:
        """Test dictionary serialization."""
        d = sample_article.to_dict()
        assert d["id"] == "module-memory"
        assert d["article_type"] == "module"
        assert d["generation_status"] == "complete"
        assert d["source_hash"] == "abc123"

    def test_from_dict_roundtrip(self, sample_article: WikiArticle) -> None:
        """Test dict roundtrip."""
        d = sample_article.to_dict()
        restored = WikiArticle.from_dict(d)
        assert restored.id == sample_article.id
        assert restored.article_type == sample_article.article_type
        assert restored.title == sample_article.title
        assert restored.content == sample_article.content

    def test_sqlite_row_roundtrip(self, sample_article: WikiArticle) -> None:
        """Test SQLite row roundtrip."""
        row = sample_article.to_sqlite_row()
        assert len(row) == 12
        assert row[0] == "module-memory"

    def test_article_types(self) -> None:
        """Test all article type enum values."""
        assert ArticleType.OVERVIEW.value == "overview"
        assert ArticleType.MODULE.value == "module"
        assert ArticleType.DECISION.value == "decision"
        assert ArticleType.ROADMAP.value == "roadmap"
        assert ArticleType.DIAGRAM.value == "diagram"

    def test_generation_statuses(self) -> None:
        """Test all generation status enum values."""
        assert GenerationStatus.PENDING.value == "pending"
        assert GenerationStatus.GENERATING.value == "generating"
        assert GenerationStatus.COMPLETE.value == "complete"
        assert GenerationStatus.FAILED.value == "failed"
        assert GenerationStatus.STATIC.value == "static"


# ============== Database Tests ==============

class TestWikiDatabase:
    """Tests for WikiDatabase."""

    @pytest_asyncio.fixture
    async def db(self, temp_dir: Path):
        """Create a test database."""
        db = WikiDatabase(db_path=temp_dir / "test_wiki.db")
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_upsert_and_get(self, db: WikiDatabase, sample_article: WikiArticle) -> None:
        """Test insert and retrieve."""
        await db.upsert_article(sample_article)
        result = await db.get_article("module-memory")
        assert result is not None
        assert result.title == "Memory Layer"
        assert result.content == "# Memory Layer\n\nThe memory module handles..."

    @pytest.mark.asyncio
    async def test_upsert_update(self, db: WikiDatabase, sample_article: WikiArticle) -> None:
        """Test upsert updates existing article."""
        await db.upsert_article(sample_article)

        # Update content
        sample_article.content = "Updated content"
        sample_article.word_count = 2
        await db.upsert_article(sample_article)

        result = await db.get_article("module-memory")
        assert result is not None
        assert result.content == "Updated content"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db: WikiDatabase) -> None:
        """Test getting a nonexistent article."""
        result = await db.get_article("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, db: WikiDatabase, sample_article: WikiArticle, sample_decision_article: WikiArticle) -> None:
        """Test listing all articles."""
        await db.upsert_article(sample_article)
        await db.upsert_article(sample_decision_article)

        articles = await db.list_articles()
        assert len(articles) == 2

    @pytest.mark.asyncio
    async def test_list_by_type(self, db: WikiDatabase, sample_article: WikiArticle, sample_decision_article: WikiArticle) -> None:
        """Test listing articles filtered by type."""
        await db.upsert_article(sample_article)
        await db.upsert_article(sample_decision_article)

        modules = await db.list_articles(ArticleType.MODULE)
        assert len(modules) == 1
        assert modules[0].id == "module-memory"

        decisions = await db.list_articles(ArticleType.DECISION)
        assert len(decisions) == 1

    @pytest.mark.asyncio
    async def test_delete_article(self, db: WikiDatabase, sample_article: WikiArticle) -> None:
        """Test deleting an article."""
        await db.upsert_article(sample_article)
        deleted = await db.delete_article("module-memory")
        assert deleted is True

        result = await db.get_article("module-memory")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db: WikiDatabase) -> None:
        """Test deleting nonexistent article."""
        deleted = await db.delete_article("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_article_count(self, db: WikiDatabase, sample_article: WikiArticle) -> None:
        """Test article count."""
        assert await db.get_article_count() == 0
        await db.upsert_article(sample_article)
        assert await db.get_article_count() == 1

    @pytest.mark.asyncio
    async def test_get_stale_articles(self, db: WikiDatabase, sample_article: WikiArticle) -> None:
        """Test getting stale-checkable articles."""
        await db.upsert_article(sample_article)
        stale = await db.get_stale_articles()
        assert len(stale) == 1
        assert stale[0].id == "module-memory"

    @pytest.mark.asyncio
    async def test_static_not_in_stale(self, db: WikiDatabase, sample_decision_article: WikiArticle) -> None:
        """Test that static articles aren't flagged for staleness."""
        await db.upsert_article(sample_decision_article)
        stale = await db.get_stale_articles()
        assert len(stale) == 0


# ============== Scanner Tests ==============

class TestWikiScanner:
    """Tests for WikiScanner."""

    def test_list_modules(self, project_fixture: Path) -> None:
        """Test listing backend modules."""
        scanner = WikiScanner(project_root=project_fixture)
        modules = scanner.list_modules()
        assert "memory" in modules
        assert "security" in modules

    def test_get_module_source(self, project_fixture: Path) -> None:
        """Test reading module source files."""
        scanner = WikiScanner(project_root=project_fixture)
        source = scanner.get_module_source("memory")
        assert "models.py" in source
        assert "manager.py" in source
        assert "MemoryChunk" in source

    def test_get_module_source_nonexistent(self, project_fixture: Path) -> None:
        """Test reading nonexistent module."""
        scanner = WikiScanner(project_root=project_fixture)
        source = scanner.get_module_source("nonexistent")
        assert source == ""

    def test_get_module_hash(self, project_fixture: Path) -> None:
        """Test module hash computation."""
        scanner = WikiScanner(project_root=project_fixture)
        hash1 = scanner.get_module_hash("memory")
        assert len(hash1) == 64  # SHA256 hex

        # Hash should be deterministic
        hash2 = scanner.get_module_hash("memory")
        assert hash1 == hash2

    def test_get_module_hash_changes(self, project_fixture: Path) -> None:
        """Test that hash changes when source changes."""
        scanner = WikiScanner(project_root=project_fixture)
        hash_before = scanner.get_module_hash("memory")

        # Modify a file
        (project_fixture / "hestia" / "memory" / "models.py").write_text(
            "class MemoryChunk:\n    updated = True\n"
        )

        hash_after = scanner.get_module_hash("memory")
        assert hash_before != hash_after

    def test_get_project_overview_source(self, project_fixture: Path) -> None:
        """Test reading CLAUDE.md."""
        scanner = WikiScanner(project_root=project_fixture)
        source = scanner.get_project_overview_source()
        assert "Hestia" in source

    def test_get_overview_hash(self, project_fixture: Path) -> None:
        """Test overview hash."""
        scanner = WikiScanner(project_root=project_fixture)
        h = scanner.get_overview_hash()
        assert len(h) == 64

    def test_parse_decisions(self, project_fixture: Path) -> None:
        """Test parsing decision log into ADR entries."""
        scanner = WikiScanner(project_root=project_fixture)
        decisions = scanner.parse_decisions()
        assert len(decisions) == 2
        assert decisions[0]["number"] == "ADR-001"
        assert decisions[0]["title"] == "Test Decision"
        assert decisions[0]["date"] == "2025-01-01"
        assert decisions[0]["status"] == "Accepted"
        assert "Some context" in decisions[0]["context"]
        assert "We decided to do X" in decisions[0]["decision"]

    def test_parse_decisions_second_entry(self, project_fixture: Path) -> None:
        """Test parsing second ADR entry."""
        scanner = WikiScanner(project_root=project_fixture)
        decisions = scanner.parse_decisions()
        assert decisions[1]["number"] == "ADR-002"
        assert decisions[1]["title"] == "Second Decision"

    def test_parse_roadmap(self, project_fixture: Path) -> None:
        """Test parsing development plan."""
        scanner = WikiScanner(project_root=project_fixture)
        roadmap = scanner.parse_roadmap()
        assert "content" in roadmap
        assert "Development Plan" in roadmap["content"]

    def test_check_staleness_fresh(self, project_fixture: Path) -> None:
        """Test staleness check for fresh content."""
        scanner = WikiScanner(project_root=project_fixture)
        current_hash = scanner.get_module_hash("memory")
        assert scanner.check_staleness("module-memory", current_hash) is False

    def test_check_staleness_stale(self, project_fixture: Path) -> None:
        """Test staleness check for outdated content."""
        scanner = WikiScanner(project_root=project_fixture)
        assert scanner.check_staleness("module-memory", "old_hash") is True

    def test_check_staleness_no_hash(self, project_fixture: Path) -> None:
        """Test staleness check with no stored hash."""
        scanner = WikiScanner(project_root=project_fixture)
        assert scanner.check_staleness("module-memory", None) is True

    def test_check_staleness_static(self, project_fixture: Path) -> None:
        """Test staleness check for static content (always fresh)."""
        scanner = WikiScanner(project_root=project_fixture)
        assert scanner.check_staleness("decision-adr-001", "anything") is False

    def test_get_decision_log(self, project_fixture: Path) -> None:
        """Test reading raw decision log."""
        scanner = WikiScanner(project_root=project_fixture)
        content = scanner.get_decision_log()
        assert "ADR-001" in content

    def test_get_development_plan(self, project_fixture: Path) -> None:
        """Test reading raw development plan."""
        scanner = WikiScanner(project_root=project_fixture)
        content = scanner.get_development_plan()
        assert "Development Plan" in content


# ============== Manager Tests ==============

class TestWikiManager:
    """Tests for WikiManager."""

    @pytest_asyncio.fixture
    async def manager(self, temp_dir: Path, project_fixture: Path):
        """Create a test wiki manager."""
        db = WikiDatabase(db_path=temp_dir / "test_wiki.db")
        await db.connect()
        scanner = WikiScanner(project_root=project_fixture)
        generator = WikiGenerator(scanner=scanner)
        mgr = WikiManager(database=db, scanner=scanner, generator=generator)
        mgr._config = {
            "modules": {
                "memory": {
                    "display_name": "Memory Layer",
                    "subtitle": "How Hestia remembers",
                    "icon": "brain",
                },
                "security": {
                    "display_name": "Security Layer",
                    "subtitle": "Credentials and encryption",
                    "icon": "lock.shield",
                },
            },
            "diagrams": [
                {"type": "architecture", "title": "System Architecture"},
            ],
        }
        yield mgr
        await db.close()

    @pytest.mark.asyncio
    async def test_refresh_static(self, manager: WikiManager) -> None:
        """Test refreshing static content from disk."""
        counts = await manager.refresh_static()
        assert counts["decisions"] == 2
        assert counts["roadmap"] == 1

    @pytest.mark.asyncio
    async def test_refresh_static_creates_articles(self, manager: WikiManager) -> None:
        """Test that refresh creates browsable articles."""
        await manager.refresh_static()
        articles = await manager.list_articles("decision")
        assert len(articles) == 2
        assert articles[0].generation_status == GenerationStatus.STATIC

    @pytest.mark.asyncio
    async def test_list_articles_all(self, manager: WikiManager) -> None:
        """Test listing all articles."""
        await manager.refresh_static()
        articles = await manager.list_articles()
        assert len(articles) == 3  # 2 decisions + 1 roadmap

    @pytest.mark.asyncio
    async def test_list_articles_by_type(self, manager: WikiManager) -> None:
        """Test listing articles by type."""
        await manager.refresh_static()
        roadmap = await manager.list_articles("roadmap")
        assert len(roadmap) == 1
        assert roadmap[0].title == "Development Roadmap"

    @pytest.mark.asyncio
    async def test_list_articles_invalid_type(self, manager: WikiManager) -> None:
        """Test listing with invalid type returns empty."""
        articles = await manager.list_articles("invalid")
        assert articles == []

    @pytest.mark.asyncio
    async def test_get_article(self, manager: WikiManager) -> None:
        """Test getting a specific article."""
        await manager.refresh_static()
        article = await manager.get_article("roadmap")
        assert article is not None
        assert article.title == "Development Roadmap"

    @pytest.mark.asyncio
    async def test_get_article_nonexistent(self, manager: WikiManager) -> None:
        """Test getting nonexistent article."""
        article = await manager.get_article("nonexistent")
        assert article is None

    @pytest.mark.asyncio
    async def test_generate_module_mocked(self, manager: WikiManager) -> None:
        """Test module generation with mocked cloud."""
        mock_content = "## Memory Layer\n\nGenerated content about memory."
        with patch.object(
            manager.generator,
            "_call_cloud",
            new_callable=AsyncMock,
            return_value=mock_content,
        ):
            article = await manager.generate_article("module", "memory")
            assert article.id == "module-memory"
            assert article.generation_status == GenerationStatus.COMPLETE
            assert "Generated content" in article.content
            assert article.word_count > 0

    @pytest.mark.asyncio
    async def test_generate_overview_mocked(self, manager: WikiManager) -> None:
        """Test overview generation with mocked cloud."""
        mock_content = "# Architecture Overview\n\n" + " ".join(["word"] * 500)
        with patch.object(
            manager.generator,
            "_call_cloud",
            new_callable=AsyncMock,
            return_value=mock_content,
        ):
            article = await manager.generate_article("overview")
            assert article.id == "overview"
            assert article.generation_status == GenerationStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_generate_diagram_mocked(self, manager: WikiManager) -> None:
        """Test diagram generation with mocked cloud."""
        mock_mermaid = "graph TD\n    A[iOS] --> B[API]\n    B --> C[Orchestration]"
        with patch.object(
            manager.generator,
            "_call_cloud",
            new_callable=AsyncMock,
            return_value=mock_mermaid,
        ):
            article = await manager.generate_article("diagram", "architecture")
            assert article.id == "diagram-architecture"
            assert "graph TD" in article.content
            assert article.generation_status == GenerationStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_generate_fails_gracefully(self, manager: WikiManager) -> None:
        """Test generation failure produces FAILED article."""
        with patch.object(
            manager.generator,
            "_call_cloud",
            new_callable=AsyncMock,
            return_value=None,
        ):
            article = await manager.generate_article("module", "memory")
            assert article.generation_status == GenerationStatus.FAILED

    @pytest.mark.asyncio
    async def test_generate_module_requires_name(self, manager: WikiManager) -> None:
        """Test module generation requires module_name."""
        with pytest.raises(ValueError, match="module_name required"):
            await manager.generate_article("module")

    @pytest.mark.asyncio
    async def test_generate_decision_rejected(self, manager: WikiManager) -> None:
        """Test that decision articles can't be generated (use refresh_static)."""
        with pytest.raises(ValueError, match="Cannot generate"):
            await manager.generate_article("decision", "adr-001")

    @pytest.mark.asyncio
    async def test_check_staleness(self, manager: WikiManager) -> None:
        """Test staleness detection."""
        # Create a module article with current hash
        current_hash = manager.scanner.get_module_hash("memory")
        article = WikiArticle.create(
            article_type=ArticleType.MODULE,
            title="Memory Layer",
            module_name="memory",
            content="Content",
            source_hash=current_hash,
            generation_status=GenerationStatus.COMPLETE,
        )
        await manager.database.upsert_article(article)

        results = await manager.check_staleness()
        assert len(results) == 1
        assert results[0]["is_stale"] is False

    @pytest.mark.asyncio
    async def test_check_staleness_detects_changes(self, manager: WikiManager) -> None:
        """Test staleness detection catches source changes."""
        article = WikiArticle.create(
            article_type=ArticleType.MODULE,
            title="Memory Layer",
            module_name="memory",
            content="Content",
            source_hash="old_hash_value",
            generation_status=GenerationStatus.COMPLETE,
        )
        await manager.database.upsert_article(article)

        results = await manager.check_staleness()
        assert len(results) == 1
        assert results[0]["is_stale"] is True

    @pytest.mark.asyncio
    async def test_generate_all_mocked(self, manager: WikiManager) -> None:
        """Test full generation with mocked cloud."""
        mock_content = "Generated content for testing."
        with patch.object(
            manager.generator,
            "_call_cloud",
            new_callable=AsyncMock,
            return_value=mock_content,
        ):
            results = await manager.generate_all()
            assert results["overview"] == "complete"
            assert "memory" in results["modules"]
            assert "security" in results["modules"]
            assert "architecture" in results["diagrams"]
            assert len(results["errors"]) == 0

    @pytest.mark.asyncio
    async def test_decision_content_format(self, manager: WikiManager) -> None:
        """Test that parsed decisions have proper content format."""
        await manager.refresh_static()
        articles = await manager.list_articles("decision")
        first = articles[0]
        assert "**Date**" in first.content
        assert "**Status**" in first.content
        assert "### Context" in first.content


# ============== Generator Tests ==============

class TestWikiGenerator:
    """Tests for WikiGenerator."""

    def test_strip_mermaid_fences(self) -> None:
        """Test that Mermaid code fence stripping works."""
        # This tests the logic in generate_diagram
        content = "```mermaid\ngraph TD\n    A --> B\n```"
        content = content.strip()
        if content.startswith("```mermaid"):
            content = content[len("```mermaid"):].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        assert content == "graph TD\n    A --> B"

    def test_strip_plain_fences(self) -> None:
        """Test stripping plain code fences."""
        content = "```\ngraph TD\n    A --> B\n```"
        content = content.strip()
        if content.startswith("```mermaid"):
            content = content[len("```mermaid"):].strip()
        if content.startswith("```"):
            content = content[3:].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        assert content == "graph TD\n    A --> B"
