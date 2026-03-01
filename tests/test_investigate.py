"""
Tests for Hestia Investigate module.

URL content analysis: models, extractors, database, manager pipeline,
and API routes.

Run with: python -m pytest tests/test_investigate.py -v --timeout=30
"""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from hestia.investigate.models import (
    AnalysisDepth,
    ContentType,
    ExtractionResult,
    Investigation,
    InvestigationStatus,
    DEPTH_CONTENT_LIMITS,
    DEPTH_TOKEN_TARGETS,
)
from hestia.investigate.database import InvestigateDatabase
from hestia.investigate.manager import InvestigateManager, _extract_key_points, _validate_url
from hestia.investigate.extractors import classify_url, get_extractor
from hestia.investigate.extractors.base import BaseExtractor


# ============== Fixtures ==============


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> InvestigateDatabase:
    """Create a test database."""
    db = InvestigateDatabase(db_path=temp_dir / "test_investigate.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(database: InvestigateDatabase) -> InvestigateManager:
    """Create a manager with injected test database."""
    mgr = InvestigateManager(database=database)
    await mgr.initialize()
    return mgr


@pytest.fixture
def sample_extraction() -> ExtractionResult:
    """Create a sample successful extraction."""
    return ExtractionResult(
        content_type=ContentType.WEB_ARTICLE,
        url="https://example.com/article",
        title="Test Article",
        author="Jane Doe",
        date="2026-01-15",
        text="This is a test article about artificial intelligence. " * 50,
        metadata={"hostname": "example.com", "sitename": "Example News"},
    )


@pytest.fixture
def sample_investigation() -> Investigation:
    """Create a sample investigation."""
    return Investigation.create(
        url="https://example.com/test",
        user_id="test-user",
        content_type=ContentType.WEB_ARTICLE,
        depth=AnalysisDepth.STANDARD,
    )


# ============== Model Tests ==============


class TestContentType:
    """Tests for ContentType enum."""

    def test_all_types_have_values(self):
        """All content types have string values."""
        for ct in ContentType:
            assert isinstance(ct.value, str)
            assert len(ct.value) > 0

    def test_web_article_value(self):
        assert ContentType.WEB_ARTICLE.value == "web_article"

    def test_youtube_value(self):
        assert ContentType.YOUTUBE.value == "youtube"


class TestAnalysisDepth:
    """Tests for AnalysisDepth enum."""

    def test_all_depths_have_limits(self):
        """All depths have content limits configured."""
        for depth in AnalysisDepth:
            assert depth in DEPTH_CONTENT_LIMITS
            assert depth in DEPTH_TOKEN_TARGETS

    def test_depth_ordering(self):
        """Deeper analysis has higher limits."""
        assert DEPTH_CONTENT_LIMITS[AnalysisDepth.QUICK] < DEPTH_CONTENT_LIMITS[AnalysisDepth.STANDARD]
        assert DEPTH_CONTENT_LIMITS[AnalysisDepth.STANDARD] < DEPTH_CONTENT_LIMITS[AnalysisDepth.DEEP]


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_success_with_text(self, sample_extraction):
        """Extraction is successful when text is present."""
        assert sample_extraction.success is True

    def test_failure_with_error(self):
        """Extraction fails when error is set."""
        result = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com",
            error="Failed to download",
        )
        assert result.success is False

    def test_failure_with_empty_text(self):
        """Extraction fails when text is empty."""
        result = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com",
            text="",
        )
        assert result.success is False

    def test_word_count(self, sample_extraction):
        """Word count is calculated correctly."""
        assert sample_extraction.word_count > 0

    def test_word_count_empty(self):
        """Empty text has zero word count."""
        result = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com",
        )
        assert result.word_count == 0

    def test_truncate_for_depth(self):
        """Text is truncated for depth limits."""
        long_text = "x" * 100_000
        result = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com",
            text=long_text,
        )
        truncated = result.truncate_for_depth(AnalysisDepth.QUICK)
        assert len(truncated) <= DEPTH_CONTENT_LIMITS[AnalysisDepth.QUICK] + 50  # +50 for truncation message

    def test_no_truncation_for_short_text(self, sample_extraction):
        """Short text is not truncated."""
        truncated = sample_extraction.truncate_for_depth(AnalysisDepth.DEEP)
        assert truncated == sample_extraction.text

    def test_to_dict(self, sample_extraction):
        """Serialization to dict includes all fields."""
        d = sample_extraction.to_dict()
        assert d["content_type"] == "web_article"
        assert d["url"] == "https://example.com/article"
        assert d["title"] == "Test Article"
        assert d["author"] == "Jane Doe"
        assert d["word_count"] > 0


class TestInvestigation:
    """Tests for Investigation dataclass."""

    def test_create_factory(self):
        """Factory method creates investigation with defaults."""
        inv = Investigation.create(
            url="https://example.com/test",
            user_id="user-1",
            content_type=ContentType.YOUTUBE,
        )
        assert inv.id.startswith("inv-")
        assert inv.url == "https://example.com/test"
        assert inv.user_id == "user-1"
        assert inv.content_type == ContentType.YOUTUBE
        assert inv.depth == AnalysisDepth.STANDARD
        assert inv.status == InvestigationStatus.PENDING

    def test_to_dict(self, sample_investigation):
        """Serialization includes all expected keys."""
        d = sample_investigation.to_dict()
        assert "id" in d
        assert "url" in d
        assert "content_type" in d
        assert "depth" in d
        assert "status" in d
        assert "created_at" in d
        assert d["status"] == "pending"

    def test_from_dict_roundtrip(self, sample_investigation):
        """Dict serialization is reversible."""
        # Add required fields for from_dict
        d = sample_investigation.to_dict()
        d["extracted_text"] = ""
        d["user_id"] = sample_investigation.user_id
        d["extraction_metadata"] = {}
        restored = Investigation.from_dict(d)
        assert restored.id == sample_investigation.id
        assert restored.url == sample_investigation.url

    def test_sqlite_roundtrip(self, sample_investigation):
        """SQLite serialization is reversible."""
        row = sample_investigation.to_sqlite_row()
        assert len(row) == 18  # All columns
        # Simulate dict from sqlite Row
        columns = [
            "id", "url", "user_id", "content_type", "depth", "status",
            "title", "source_author", "source_date",
            "extracted_text", "analysis", "key_points",
            "model_used", "tokens_used", "extraction_metadata",
            "created_at", "completed_at", "error",
        ]
        row_dict = dict(zip(columns, row))
        restored = Investigation.from_sqlite_row(row_dict)
        assert restored.id == sample_investigation.id


# ============== URL Classification Tests ==============


class TestURLClassification:
    """Tests for URL classification regex patterns."""

    def test_youtube_watch(self):
        assert classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == ContentType.YOUTUBE

    def test_youtube_short_url(self):
        assert classify_url("https://youtu.be/dQw4w9WgXcQ") == ContentType.YOUTUBE

    def test_youtube_shorts(self):
        assert classify_url("https://www.youtube.com/shorts/abc123xyz45") == ContentType.YOUTUBE

    def test_youtube_embed(self):
        assert classify_url("https://www.youtube.com/embed/dQw4w9WgXcQ") == ContentType.YOUTUBE

    def test_youtube_mobile(self):
        assert classify_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ") == ContentType.YOUTUBE

    def test_tiktok_video(self):
        assert classify_url("https://www.tiktok.com/@user/video/1234567890") == ContentType.TIKTOK

    def test_tiktok_short_url(self):
        assert classify_url("https://vm.tiktok.com/abc123") == ContentType.TIKTOK

    def test_web_article_default(self):
        assert classify_url("https://www.nytimes.com/2026/01/15/article.html") == ContentType.WEB_ARTICLE

    def test_web_article_blog(self):
        assert classify_url("https://blog.example.com/some-post") == ContentType.WEB_ARTICLE

    def test_whitespace_stripped(self):
        assert classify_url("  https://youtu.be/dQw4w9WgXcQ  ") == ContentType.YOUTUBE


class TestGetExtractor:
    """Tests for extractor dispatch."""

    def test_web_article_extractor(self):
        ext = get_extractor(ContentType.WEB_ARTICLE)
        assert ext is not None
        assert ext.content_type == ContentType.WEB_ARTICLE

    def test_youtube_extractor(self):
        ext = get_extractor(ContentType.YOUTUBE)
        assert ext is not None
        assert ext.content_type == ContentType.YOUTUBE

    def test_tiktok_returns_none(self):
        """TikTok extractor not implemented yet (Phase 2)."""
        ext = get_extractor(ContentType.TIKTOK)
        assert ext is None

    def test_unknown_returns_none(self):
        ext = get_extractor(ContentType.UNKNOWN)
        assert ext is None


# ============== Extractor Tests ==============


class TestWebExtractor:
    """Tests for WebArticleExtractor with mocked trafilatura."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """Successful web extraction returns text and metadata."""
        from hestia.investigate.extractors.web import WebArticleExtractor

        mock_result = {
            "text": "Article content goes here.",
            "title": "Test Title",
            "author": "Author Name",
            "date": "2026-01-15",
            "hostname": "example.com",
            "sitename": "Example",
        }

        with patch("hestia.investigate.extractors.web._extract_sync", return_value=mock_result):
            extractor = WebArticleExtractor()
            result = await extractor.extract("https://example.com/article")

        assert result.success is True
        assert result.text == "Article content goes here."
        assert result.title == "Test Title"
        assert result.author == "Author Name"

    @pytest.mark.asyncio
    async def test_failed_extraction(self):
        """Failed web extraction returns error."""
        from hestia.investigate.extractors.web import WebArticleExtractor

        mock_result = {"error": "Failed to download: https://bad.url"}

        with patch("hestia.investigate.extractors.web._extract_sync", return_value=mock_result):
            extractor = WebArticleExtractor()
            result = await extractor.extract("https://bad.url")

        assert result.success is False
        assert "Failed to download" in result.error

    @pytest.mark.asyncio
    async def test_empty_extraction(self):
        """Empty extraction returns error."""
        from hestia.investigate.extractors.web import WebArticleExtractor

        mock_result = {"text": "", "title": None, "author": None, "date": None, "hostname": None, "sitename": None}

        with patch("hestia.investigate.extractors.web._extract_sync", return_value=mock_result):
            extractor = WebArticleExtractor()
            result = await extractor.extract("https://example.com/empty")

        assert result.success is False


class TestYouTubeExtractor:
    """Tests for YouTubeExtractor with mocked youtube-transcript-api."""

    @pytest.mark.asyncio
    async def test_successful_transcript(self):
        """Successful YouTube extraction returns transcript text."""
        from hestia.investigate.extractors.youtube import YouTubeExtractor

        mock_result = {
            "text": "Hello and welcome to this video about Python programming.",
            "language": "en (manual)",
            "entry_count": 42,
            "video_id": "dQw4w9WgXcQ",
        }

        with patch("hestia.investigate.extractors.youtube._fetch_transcript_sync", return_value=mock_result):
            extractor = YouTubeExtractor()
            result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.success is True
        assert "Python programming" in result.text
        assert result.metadata["video_id"] == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_no_transcript(self):
        """Missing transcript returns error."""
        from hestia.investigate.extractors.youtube import YouTubeExtractor

        mock_result = {"error": "No transcript available for this video"}

        with patch("hestia.investigate.extractors.youtube._fetch_transcript_sync", return_value=mock_result):
            extractor = YouTubeExtractor()
            result = await extractor.extract("https://www.youtube.com/watch?v=abcdefghijk")

        assert result.success is False
        assert "No transcript" in result.error

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        """Invalid YouTube URL returns error."""
        from hestia.investigate.extractors.youtube import YouTubeExtractor

        extractor = YouTubeExtractor()
        result = await extractor.extract("https://not-youtube.com/something")

        assert result.success is False
        assert "video ID" in result.error

    def test_video_id_extraction(self):
        """Video ID is correctly extracted from various URL formats."""
        from hestia.investigate.extractors.youtube import _extract_video_id

        assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert _extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert _extract_video_id("https://www.youtube.com/shorts/abc123xyz45") == "abc123xyz45"
        assert _extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert _extract_video_id("https://invalid.url") is None


# ============== Database Tests ==============


class TestInvestigateDatabase:
    """Tests for InvestigateDatabase CRUD operations."""

    @pytest.mark.asyncio
    async def test_store_and_get(self, database):
        """Store and retrieve an investigation."""
        inv = Investigation.create(
            url="https://example.com/test",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        inv.title = "Test Article"
        inv.analysis = "This is the analysis."
        inv.status = InvestigationStatus.COMPLETE

        await database.store(inv)
        result = await database.get(inv.id, "test-user")

        assert result is not None
        assert result.id == inv.id
        assert result.title == "Test Article"
        assert result.analysis == "This is the analysis."

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, database):
        """Getting nonexistent investigation returns None."""
        result = await database.get("inv-nonexistent", "test-user")
        assert result is None

    @pytest.mark.asyncio
    async def test_user_scoping(self, database):
        """Investigations are scoped by user_id."""
        inv = Investigation.create(
            url="https://example.com/test",
            user_id="user-a",
            content_type=ContentType.WEB_ARTICLE,
        )
        await database.store(inv)

        # Different user can't see it
        result = await database.get(inv.id, "user-b")
        assert result is None

        # Same user can see it
        result = await database.get(inv.id, "user-a")
        assert result is not None

    @pytest.mark.asyncio
    async def test_update(self, database):
        """Update an investigation's fields."""
        inv = Investigation.create(
            url="https://example.com/test",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        await database.store(inv)

        inv.status = InvestigationStatus.COMPLETE
        inv.analysis = "Updated analysis."
        inv.completed_at = datetime.now(timezone.utc)
        await database.update(inv)

        result = await database.get(inv.id, "test-user")
        assert result.status == InvestigationStatus.COMPLETE
        assert result.analysis == "Updated analysis."

    @pytest.mark.asyncio
    async def test_delete(self, database):
        """Delete an investigation."""
        inv = Investigation.create(
            url="https://example.com/test",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        await database.store(inv)

        deleted = await database.delete(inv.id, "test-user")
        assert deleted is True

        result = await database.get(inv.id, "test-user")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, database):
        """Deleting nonexistent returns False."""
        deleted = await database.delete("inv-nonexistent", "test-user")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_history(self, database):
        """List investigations with pagination."""
        for i in range(5):
            inv = Investigation.create(
                url=f"https://example.com/article-{i}",
                user_id="test-user",
                content_type=ContentType.WEB_ARTICLE,
            )
            await database.store(inv)

        results = await database.list_history("test-user", limit=3)
        assert len(results) == 3

        results = await database.list_history("test-user", limit=10)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self, database):
        """Filter investigations by content type."""
        inv_web = Investigation.create(
            url="https://example.com/article",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        inv_yt = Investigation.create(
            url="https://youtube.com/watch?v=abc",
            user_id="test-user",
            content_type=ContentType.YOUTUBE,
        )
        await database.store(inv_web)
        await database.store(inv_yt)

        results = await database.list_history("test-user", content_type="youtube")
        assert len(results) == 1
        assert results[0].content_type == ContentType.YOUTUBE

    @pytest.mark.asyncio
    async def test_count(self, database):
        """Count investigations for a user."""
        for i in range(3):
            inv = Investigation.create(
                url=f"https://example.com/{i}",
                user_id="test-user",
                content_type=ContentType.WEB_ARTICLE,
            )
            await database.store(inv)

        count = await database.count("test-user")
        assert count == 3

        count = await database.count("other-user")
        assert count == 0

    @pytest.mark.asyncio
    async def test_find_by_url(self, database):
        """Find investigation by URL."""
        inv = Investigation.create(
            url="https://example.com/specific",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        inv.status = InvestigationStatus.COMPLETE
        await database.store(inv)

        result = await database.find_by_url("https://example.com/specific", "test-user")
        assert result is not None
        assert result.url == "https://example.com/specific"

    @pytest.mark.asyncio
    async def test_find_by_url_pending_not_returned(self, database):
        """find_by_url only returns complete investigations."""
        inv = Investigation.create(
            url="https://example.com/pending",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        inv.status = InvestigationStatus.PENDING
        await database.store(inv)

        result = await database.find_by_url("https://example.com/pending", "test-user")
        assert result is None


# ============== Manager Tests ==============


class TestInvestigateManager:
    """Tests for InvestigateManager pipeline."""

    @pytest.mark.asyncio
    async def test_investigate_success(self, manager):
        """Full pipeline: extract → analyze → store."""
        mock_extraction = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com/article",
            title="Test Article",
            author="Author",
            text="Long article content here. " * 100,
        )

        mock_response = MagicMock()
        mock_response.content = "**Key Points**\n- Point one\n- Point two\n\nAnalysis text."
        mock_response.model = "qwen2.5:7b"
        mock_response.tokens_in = 500
        mock_response.tokens_out = 200

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        with patch("hestia.investigate.extractors.web.WebArticleExtractor.extract",
                   new_callable=AsyncMock, return_value=mock_extraction), \
             patch("hestia.inference.client.get_inference_client", return_value=mock_client):
            result = await manager.investigate("https://example.com/article", user_id="test-user")

        assert result["status"] == "complete"
        assert result["title"] == "Test Article"
        assert "analysis" in result
        assert result["tokens_used"] == 700

    @pytest.mark.asyncio
    async def test_investigate_extraction_failure(self, manager):
        """Pipeline handles extraction failure gracefully."""
        mock_extraction = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://bad.example.com",
            error="Failed to download",
        )

        with patch("hestia.investigate.extractors.web.WebArticleExtractor.extract",
                   new_callable=AsyncMock, return_value=mock_extraction):
            result = await manager.investigate("https://bad.example.com", user_id="test-user")

        assert result["status"] == "failed"
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_investigate_analysis_failure(self, manager):
        """Pipeline handles LLM analysis failure gracefully."""
        mock_extraction = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com/article",
            title="Test",
            text="Content here." * 50,
        )

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(side_effect=RuntimeError("Inference unavailable"))

        with patch("hestia.investigate.extractors.web.WebArticleExtractor.extract",
                   new_callable=AsyncMock, return_value=mock_extraction), \
             patch("hestia.inference.client.get_inference_client", return_value=mock_client):
            result = await manager.investigate("https://example.com/article", user_id="test-user")

        # Analysis failure is caught gracefully — investigation still completes
        assert result["status"] == "complete"
        assert "unavailable" in result["analysis"].lower()

    @pytest.mark.asyncio
    async def test_investigate_stores_in_db(self, manager, database):
        """Investigation is persisted in database."""
        mock_extraction = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com/stored",
            title="Stored Article",
            text="Content." * 50,
        )

        mock_response = MagicMock()
        mock_response.content = "Analysis text."
        mock_response.model = "test-model"
        mock_response.tokens_in = 100
        mock_response.tokens_out = 50

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        with patch("hestia.investigate.extractors.web.WebArticleExtractor.extract",
                   new_callable=AsyncMock, return_value=mock_extraction), \
             patch("hestia.inference.client.get_inference_client", return_value=mock_client):
            result = await manager.investigate("https://example.com/stored", user_id="test-user")

        # Verify stored in DB
        stored = await database.get(result["id"], "test-user")
        assert stored is not None
        assert stored.title == "Stored Article"

    @pytest.mark.asyncio
    async def test_investigate_invalid_depth(self, manager):
        """Invalid depth falls back to standard."""
        mock_extraction = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com/depth",
            title="Test",
            text="Content." * 50,
        )

        mock_response = MagicMock()
        mock_response.content = "Analysis."
        mock_response.model = "test"
        mock_response.tokens_in = 50
        mock_response.tokens_out = 25

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        with patch("hestia.investigate.extractors.web.WebArticleExtractor.extract",
                   new_callable=AsyncMock, return_value=mock_extraction), \
             patch("hestia.inference.client.get_inference_client", return_value=mock_client):
            result = await manager.investigate("https://example.com/depth", depth="invalid", user_id="test-user")

        assert result["depth"] == "standard"

    @pytest.mark.asyncio
    async def test_investigate_no_extractor(self, manager):
        """Content type with no extractor fails gracefully."""
        with patch("hestia.investigate.manager.classify_url", return_value=ContentType.UNKNOWN):
            result = await manager.investigate("https://example.com/unknown", user_id="test-user")

        assert result["status"] == "failed"
        assert "No extractor" in result["error"]

    @pytest.mark.asyncio
    async def test_get_investigation(self, manager, database):
        """Get investigation by ID."""
        inv = Investigation.create(
            url="https://example.com/get-test",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        inv.status = InvestigationStatus.COMPLETE
        inv.analysis = "Test analysis."
        await database.store(inv)

        result = await manager.get_investigation(inv.id, "test-user")
        assert result is not None
        assert result["id"] == inv.id

    @pytest.mark.asyncio
    async def test_get_investigation_not_found(self, manager):
        """Nonexistent investigation returns None."""
        result = await manager.get_investigation("inv-nonexistent", "test-user")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_investigations(self, manager, database):
        """List investigations with pagination."""
        for i in range(3):
            inv = Investigation.create(
                url=f"https://example.com/list-{i}",
                user_id="test-user",
                content_type=ContentType.WEB_ARTICLE,
            )
            await database.store(inv)

        result = await manager.list_investigations(user_id="test-user")
        assert result["count"] == 3
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_delete_investigation(self, manager, database):
        """Delete investigation."""
        inv = Investigation.create(
            url="https://example.com/delete",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        await database.store(inv)

        deleted = await manager.delete_investigation(inv.id, "test-user")
        assert deleted is True

        result = await manager.get_investigation(inv.id, "test-user")
        assert result is None

    @pytest.mark.asyncio
    async def test_compare_success(self, manager):
        """Comparison pipeline investigates each URL and synthesizes."""
        mock_extraction = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com/compare",
            title="Compare Article",
            text="Comparison content." * 50,
        )

        mock_response = MagicMock()
        mock_response.content = "**Key Points**\n- Point 1\n\nAnalysis."
        mock_response.model = "test-model"
        mock_response.tokens_in = 200
        mock_response.tokens_out = 100

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        with patch("hestia.investigate.extractors.web.WebArticleExtractor.extract",
                   new_callable=AsyncMock, return_value=mock_extraction), \
             patch("hestia.inference.client.get_inference_client", return_value=mock_client):
            result = await manager.compare(
                urls=["https://example.com/a", "https://example.com/b"],
                user_id="test-user",
            )

        assert result["urls_compared"] == 2
        assert "comparison" in result
        assert len(result["investigations"]) == 2

    @pytest.mark.asyncio
    async def test_compare_too_few_urls(self, manager):
        """Comparison rejects fewer than 2 URLs."""
        result = await manager.compare(urls=["https://example.com/only-one"], user_id="test-user")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_compare_too_many_urls(self, manager):
        """Comparison rejects more than 5 URLs."""
        urls = [f"https://example.com/{i}" for i in range(6)]
        result = await manager.compare(urls=urls, user_id="test-user")
        assert "error" in result


class TestKeyPointExtraction:
    """Tests for _extract_key_points helper."""

    def test_extracts_bullet_points(self):
        """Extracts bullet points from key points section."""
        text = (
            "**Summary**: An overview.\n\n"
            "**Key Points**\n"
            "- First key point about something\n"
            "- Second key point about something else\n"
            "- Third important finding\n\n"
            "**Assessment**: Good source."
        )
        points = _extract_key_points(text)
        assert len(points) == 3
        assert "First key point" in points[0]

    def test_fallback_to_any_bullets(self):
        """Falls back to any bullet points if no key points section."""
        text = "- Some bullet point here\n- Another one with context\n- Third point for good measure"
        points = _extract_key_points(text)
        assert len(points) >= 2

    def test_empty_text(self):
        """Empty text returns empty list."""
        points = _extract_key_points("")
        assert points == []


# ============== Route Tests ==============


class TestInvestigateRoutes:
    """Tests for investigation API endpoints."""

    def _make_app(self, mock_manager):
        """Create a test FastAPI app with auth override and mocked manager."""
        from fastapi import FastAPI
        from hestia.api.routes.investigate import router
        from hestia.api.middleware.auth import get_device_token

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_device_token] = lambda: "test-device-123"

        return app

    @pytest.fixture
    def mock_manager(self):
        """Mock investigate manager."""
        mock_mgr = AsyncMock()
        mock_mgr.investigate = AsyncMock(return_value={
            "id": "inv-test123",
            "url": "https://example.com/test",
            "content_type": "web_article",
            "depth": "standard",
            "status": "complete",
            "title": "Test Article",
            "source_author": None,
            "source_date": None,
            "analysis": "Analysis text.",
            "key_points": ["Point 1"],
            "model_used": "test-model",
            "tokens_used": 100,
            "word_count": 50,
            "created_at": "2026-01-15T00:00:00+00:00",
            "completed_at": "2026-01-15T00:01:00+00:00",
            "error": None,
        })
        mock_mgr.get_investigation = AsyncMock(return_value={
            "id": "inv-test123",
            "url": "https://example.com/test",
            "content_type": "web_article",
            "depth": "standard",
            "status": "complete",
            "title": "Test Article",
            "source_author": None,
            "source_date": None,
            "analysis": "Analysis text.",
            "key_points": [],
            "model_used": "test-model",
            "tokens_used": 100,
            "word_count": 50,
            "created_at": "2026-01-15T00:00:00+00:00",
            "completed_at": "2026-01-15T00:01:00+00:00",
            "error": None,
        })
        mock_mgr.list_investigations = AsyncMock(return_value={
            "investigations": [],
            "count": 0,
            "total": 0,
        })
        mock_mgr.delete_investigation = AsyncMock(return_value=True)
        mock_mgr.compare = AsyncMock(return_value={
            "investigations": [],
            "comparison": "Comparison text.",
            "urls_compared": 2,
            "urls_failed": 0,
            "error": None,
        })
        return mock_mgr

    @pytest.mark.asyncio
    async def test_investigate_url_endpoint(self, mock_manager):
        """POST /v1/investigate/url works."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/investigate/url",
                json={"url": "https://example.com/test", "depth": "standard"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "inv-test123"
        assert data["status"] == "complete"

    @pytest.mark.asyncio
    async def test_investigate_url_invalid_depth(self, mock_manager):
        """POST /v1/investigate/url rejects invalid depth."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/investigate/url",
                json={"url": "https://example.com/test", "depth": "invalid"},
            )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_investigation_endpoint(self, mock_manager):
        """GET /v1/investigate/{id} returns investigation."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/investigate/inv-test123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "inv-test123"

    @pytest.mark.asyncio
    async def test_get_investigation_not_found(self, mock_manager):
        """GET /v1/investigate/{id} returns 404 for missing."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)
        mock_manager.get_investigation = AsyncMock(return_value=None)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/investigate/inv-nonexistent")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_history_endpoint(self, mock_manager):
        """GET /v1/investigate/history returns list."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/investigate/history")

        assert response.status_code == 200
        data = response.json()
        assert "investigations" in data
        assert "count" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_delete_endpoint(self, mock_manager):
        """DELETE /v1/investigate/{id} deletes investigation."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.delete("/v1/investigate/inv-test123")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_manager):
        """DELETE /v1/investigate/{id} returns 404 for missing."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)
        mock_manager.delete_investigation = AsyncMock(return_value=False)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.delete("/v1/investigate/inv-nonexistent")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_compare_endpoint(self, mock_manager):
        """POST /v1/investigate/compare compares URLs."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/investigate/compare",
                json={"urls": ["https://a.com", "https://b.com"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["urls_compared"] == 2

    @pytest.mark.asyncio
    async def test_compare_too_few_urls(self, mock_manager):
        """POST /v1/investigate/compare rejects single URL."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/investigate/compare",
                json={"urls": ["https://only-one.com"]},
            )

        assert response.status_code == 422  # Pydantic min_length=2

    @pytest.mark.asyncio
    async def test_investigate_url_no_scheme(self, mock_manager):
        """POST /v1/investigate/url rejects URL without scheme."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/investigate/url",
                json={"url": "not-a-url-at-all", "depth": "standard"},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_investigate_url_ftp_scheme(self, mock_manager):
        """POST /v1/investigate/url rejects non-http(s) scheme."""
        from fastapi.testclient import TestClient
        app = self._make_app(mock_manager)

        with patch("hestia.api.routes.investigate.get_investigate_manager",
                   new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/investigate/url",
                json={"url": "ftp://files.example.com/data", "depth": "standard"},
            )

        assert response.status_code == 422


# ============== URL Validation Tests ==============


class TestURLValidation:
    """Tests for _validate_url SSRF protection."""

    def test_valid_url(self):
        assert _validate_url("https://example.com/article") is None

    def test_valid_http(self):
        assert _validate_url("http://example.com/article") is None

    def test_no_scheme(self):
        error = _validate_url("example.com/article")
        assert error is not None
        assert "scheme" in error.lower()

    def test_ftp_scheme(self):
        error = _validate_url("ftp://files.example.com")
        assert error is not None

    def test_localhost_blocked(self):
        error = _validate_url("http://localhost:8443/v1/health")
        assert error is not None
        assert "localhost" in error.lower()

    def test_127_blocked(self):
        error = _validate_url("http://127.0.0.1/secret")
        assert error is not None

    def test_private_10_blocked(self):
        error = _validate_url("http://10.0.0.1/internal")
        assert error is not None
        assert "private" in error.lower()

    def test_private_192_blocked(self):
        error = _validate_url("http://192.168.1.1/admin")
        assert error is not None

    def test_no_hostname(self):
        error = _validate_url("https://")
        assert error is not None


# ============== Additional Key Point Tests ==============


class TestKeyPointExtractionExtended:
    """Extended tests for _extract_key_points covering numbered lists."""

    def test_numbered_list(self):
        """Extracts numbered items from key points section."""
        text = (
            "**Key Points**\n"
            "1. First numbered point\n"
            "2. Second numbered point\n"
            "3. Third numbered point\n\n"
            "**Source Assessment**: Credible."
        )
        points = _extract_key_points(text)
        assert len(points) == 3
        assert "First numbered point" in points[0]

    def test_mixed_bullets_and_numbers(self):
        """Handles mix of bullet points and numbered items."""
        text = (
            "**Key Points**\n"
            "- First bullet\n"
            "1. First numbered\n"
            "- Second bullet\n\n"
            "**Assessment**: Done."
        )
        points = _extract_key_points(text)
        assert len(points) == 3

    def test_key_findings_header(self):
        """Recognizes 'Key Findings' as section header."""
        text = (
            "**Key Findings**\n"
            "- Finding A\n"
            "- Finding B\n"
        )
        points = _extract_key_points(text)
        assert len(points) == 2


# ============== Manager Advanced Tests ==============


class TestInvestigateManagerAdvanced:
    """Advanced manager tests: dedup, config, URL validation."""

    @pytest.mark.asyncio
    async def test_url_validation_rejects_localhost(self, manager):
        """Manager rejects localhost URLs."""
        result = await manager.investigate("http://localhost:8443/v1/health", user_id="test-user")
        assert result["status"] == "failed"
        assert "localhost" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_url_validation_rejects_no_scheme(self, manager):
        """Manager rejects URLs without http/https scheme."""
        result = await manager.investigate("not-a-url", user_id="test-user")
        assert result["status"] == "failed"
        assert "scheme" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_dedup_returns_cached(self, manager, database):
        """Re-investigating a recent URL returns cached result."""
        inv = Investigation.create(
            url="https://example.com/cached",
            user_id="test-user",
            content_type=ContentType.WEB_ARTICLE,
        )
        inv.status = InvestigationStatus.COMPLETE
        inv.analysis = "Cached analysis."
        await database.store(inv)

        result = await manager.investigate("https://example.com/cached", user_id="test-user")
        assert result["analysis"] == "Cached analysis."
        assert result["id"] == inv.id

    @pytest.mark.asyncio
    async def test_extractor_disabled_in_config(self, manager):
        """Disabled extractor returns error."""
        # TikTok is disabled by default in config
        with patch("hestia.investigate.manager.classify_url", return_value=ContentType.TIKTOK):
            result = await manager.investigate("https://www.tiktok.com/@user/video/123", user_id="test-user")

        assert result["status"] == "failed"
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_config_driven_content_limits(self, manager):
        """Manager uses config values for content limits."""
        limit = manager._get_content_limit(AnalysisDepth.QUICK)
        assert limit == 8000  # From investigate.yaml

    @pytest.mark.asyncio
    async def test_config_driven_token_targets(self, manager):
        """Manager uses config values for token targets."""
        target = manager._get_token_target(AnalysisDepth.DEEP)
        assert target == 4000  # From investigate.yaml

    @pytest.mark.asyncio
    async def test_stored_text_truncated(self, manager, database):
        """Stored extracted text is truncated to prevent DB bloat."""
        huge_text = "x" * 200_000
        mock_extraction = ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url="https://example.com/huge",
            title="Huge Article",
            text=huge_text,
        )

        mock_response = MagicMock()
        mock_response.content = "Analysis."
        mock_response.model = "test"
        mock_response.tokens_in = 50
        mock_response.tokens_out = 25

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)

        with patch("hestia.investigate.extractors.web.WebArticleExtractor.extract",
                   new_callable=AsyncMock, return_value=mock_extraction), \
             patch("hestia.inference.client.get_inference_client", return_value=mock_client):
            result = await manager.investigate("https://example.com/huge", user_id="test-user")

        stored = await database.get(result["id"], "test-user")
        assert len(stored.extracted_text) <= 100_001  # _MAX_STORED_TEXT_CHARS + 1


# ============== YouTube Title Tests ==============


class TestYouTubeTitleFetch:
    """Tests for YouTube title extraction."""

    @pytest.mark.asyncio
    async def test_title_fetched_on_success(self):
        """YouTube extractor fetches title when transcript succeeds."""
        from hestia.investigate.extractors.youtube import YouTubeExtractor

        mock_transcript = {
            "text": "Hello world.",
            "language": "en (manual)",
            "entry_count": 1,
            "video_id": "dQw4w9WgXcQ",
        }

        with patch("hestia.investigate.extractors.youtube._fetch_transcript_sync",
                   return_value=mock_transcript), \
             patch("hestia.investigate.extractors.youtube._fetch_video_title_sync",
                   return_value="Never Gonna Give You Up"):
            extractor = YouTubeExtractor()
            result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.success is True
        assert result.title == "Never Gonna Give You Up"

    @pytest.mark.asyncio
    async def test_title_none_on_failure(self):
        """YouTube extractor gracefully handles title fetch failure."""
        from hestia.investigate.extractors.youtube import YouTubeExtractor

        mock_transcript = {
            "text": "Hello world.",
            "language": "en (manual)",
            "entry_count": 1,
            "video_id": "dQw4w9WgXcQ",
        }

        with patch("hestia.investigate.extractors.youtube._fetch_transcript_sync",
                   return_value=mock_transcript), \
             patch("hestia.investigate.extractors.youtube._fetch_video_title_sync",
                   return_value=None):
            extractor = YouTubeExtractor()
            result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.success is True
        assert result.title is None
