"""Tests for Research Canvas board persistence — database CRUD and API routes."""

from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hestia.research.boards import ResearchBoard
from hestia.research.database import ResearchDatabase


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[ResearchDatabase, None]:
    """Temporary research database for unit tests."""
    database = ResearchDatabase(db_path=tmp_path / "test_boards.db")
    await database.initialize()
    try:
        yield database
    finally:
        await database.close()


@pytest_asyncio.fixture
async def client(tmp_path: Path):
    """Test HTTP client with mocked auth and a real database."""
    from fastapi import FastAPI
    from hestia.api.routes.research import router
    from hestia.api.middleware.auth import get_device_token

    database = ResearchDatabase(db_path=tmp_path / "test_boards_api.db")
    await database.initialize()

    # Build a minimal ResearchManager stub that exposes _database
    manager = MagicMock()
    manager._database = database
    manager._principle_store = None

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_device_token] = lambda: "test-token"

    with patch("hestia.api.routes.research.get_research_manager", return_value=manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    await database.close()


# =============================================================================
# ResearchBoard dataclass
# =============================================================================


class TestResearchBoard:
    def test_defaults(self) -> None:
        board = ResearchBoard()
        assert board.name == "Untitled Board"
        assert board.layout_json == "{}"
        assert board.id  # auto-generated UUID

    def test_to_dict_keys(self) -> None:
        board = ResearchBoard(name="My Board")
        d = board.to_dict()
        assert set(d.keys()) == {"id", "name", "layoutJson", "createdAt", "updatedAt"}

    def test_to_dict_name(self) -> None:
        board = ResearchBoard(name="Test")
        assert board.to_dict()["name"] == "Test"

    def test_unique_ids(self) -> None:
        b1 = ResearchBoard()
        b2 = ResearchBoard()
        assert b1.id != b2.id


# =============================================================================
# Database CRUD
# =============================================================================


class TestBoardDatabaseCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db: ResearchDatabase) -> None:
        board = ResearchBoard(name="Alpha")
        await db.create_board(board)
        fetched = await db.get_board(board.id)
        assert fetched is not None
        assert fetched.name == "Alpha"
        assert fetched.id == board.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, db: ResearchDatabase) -> None:
        result = await db.get_board("no-such-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_boards_empty(self, db: ResearchDatabase) -> None:
        boards = await db.list_boards()
        assert boards == []

    @pytest.mark.asyncio
    async def test_list_boards_ordered_by_updated(self, db: ResearchDatabase) -> None:
        b1 = ResearchBoard(name="First")
        b2 = ResearchBoard(name="Second")
        await db.create_board(b1)
        await db.create_board(b2)

        # Update b1 so it has a newer updated_at
        await db.update_board(b1.id, name="First Updated")

        boards = await db.list_boards()
        assert len(boards) == 2
        assert boards[0].name == "First Updated"

    @pytest.mark.asyncio
    async def test_update_name(self, db: ResearchDatabase) -> None:
        board = ResearchBoard(name="Original")
        await db.create_board(board)
        updated = await db.update_board(board.id, name="Renamed")
        assert updated is not None
        assert updated.name == "Renamed"

        refetched = await db.get_board(board.id)
        assert refetched is not None
        assert refetched.name == "Renamed"

    @pytest.mark.asyncio
    async def test_update_layout_json(self, db: ResearchDatabase) -> None:
        board = ResearchBoard(name="Layout Test")
        await db.create_board(board)
        layout = '{"nodes": [{"id": "n1"}]}'
        updated = await db.update_board(board.id, layout_json=layout)
        assert updated is not None
        assert updated.layout_json == layout

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, db: ResearchDatabase) -> None:
        result = await db.update_board("ghost-id", name="Nope")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_board(self, db: ResearchDatabase) -> None:
        board = ResearchBoard(name="To Delete")
        await db.create_board(board)
        deleted = await db.delete_board(board.id)
        assert deleted is True
        assert await db.get_board(board.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, db: ResearchDatabase) -> None:
        result = await db.delete_board("not-there")
        assert result is False


# =============================================================================
# API Route Tests
# =============================================================================


class TestBoardAPICreate:
    @pytest.mark.asyncio
    async def test_create_returns_201(self, client: AsyncClient) -> None:
        response = await client.post("/v1/research/boards", json={"name": "Sprint Board"})
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_response_shape(self, client: AsyncClient) -> None:
        response = await client.post("/v1/research/boards", json={"name": "Sprint Board"})
        data = response.json()
        assert "id" in data
        assert data["name"] == "Sprint Board"
        assert "layoutJson" in data
        assert "createdAt" in data
        assert "updatedAt" in data

    @pytest.mark.asyncio
    async def test_create_default_name(self, client: AsyncClient) -> None:
        response = await client.post("/v1/research/boards", json={})
        assert response.status_code == 201
        assert response.json()["name"] == "Untitled Board"


class TestBoardAPIList:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient) -> None:
        response = await client.get("/v1/research/boards")
        assert response.status_code == 200
        data = response.json()
        assert data["boards"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_after_create(self, client: AsyncClient) -> None:
        await client.post("/v1/research/boards", json={"name": "Board A"})
        await client.post("/v1/research/boards", json={"name": "Board B"})
        response = await client.get("/v1/research/boards")
        data = response.json()
        assert data["total"] == 2
        names = {b["name"] for b in data["boards"]}
        assert names == {"Board A", "Board B"}


class TestBoardAPIGet:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient) -> None:
        create = await client.post("/v1/research/boards", json={"name": "Findable"})
        board_id = create.json()["id"]
        response = await client.get(f"/v1/research/boards/{board_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Findable"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/v1/research/boards/does-not-exist")
        assert response.status_code == 404


class TestBoardAPIUpdate:
    @pytest.mark.asyncio
    async def test_update_name(self, client: AsyncClient) -> None:
        create = await client.post("/v1/research/boards", json={"name": "Old"})
        board_id = create.json()["id"]
        response = await client.put(
            f"/v1/research/boards/{board_id}", json={"name": "New"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New"

    @pytest.mark.asyncio
    async def test_update_layout(self, client: AsyncClient) -> None:
        create = await client.post("/v1/research/boards", json={"name": "Canvas"})
        board_id = create.json()["id"]
        layout = '{"nodes": [], "edges": []}'
        response = await client.put(
            f"/v1/research/boards/{board_id}", json={"layout_json": layout}
        )
        assert response.status_code == 200
        assert response.json()["layoutJson"] == layout

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self, client: AsyncClient) -> None:
        response = await client.put(
            "/v1/research/boards/ghost", json={"name": "X"}
        )
        assert response.status_code == 404


class TestBoardAPIDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self, client: AsyncClient) -> None:
        create = await client.post("/v1/research/boards", json={"name": "Temp"})
        board_id = create.json()["id"]
        response = await client.delete(f"/v1/research/boards/{board_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

        get_response = await client.get(f"/v1/research/boards/{board_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client: AsyncClient) -> None:
        response = await client.delete("/v1/research/boards/no-board")
        assert response.status_code == 404


# =============================================================================
# Distill-from-Selection Tests
# =============================================================================


class TestDistillFromSelection:
    @pytest.mark.asyncio
    async def test_distill_no_entities_returns_404(self, client: AsyncClient) -> None:
        """When entity_ids resolve to nothing, return 404."""
        response = await client.post(
            "/v1/research/principles/distill-from-selection",
            json={"entity_ids": ["nonexistent-id"], "board_id": "board-1"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_distill_creates_stub_when_inference_unavailable(
        self, tmp_path: Path
    ) -> None:
        """Distill-from-selection creates a stub principle when inference is down."""
        from datetime import datetime, timezone
        from fastapi import FastAPI
        from hestia.api.routes.research import router
        from hestia.api.middleware.auth import get_device_token
        from hestia.research.models import Entity, EntityType

        db = ResearchDatabase(db_path=tmp_path / "distill_test.db")
        await db.initialize()

        now = datetime.now(timezone.utc)
        # Insert a real entity
        entity = Entity(
            id="entity-fastapi-1",
            name="FastAPI",
            entity_type=EntityType.TOOL,
            canonical_name="fastapi",
            created_at=now,
            updated_at=now,
        )
        await db.create_entity(entity)

        manager = MagicMock()
        manager._database = db
        manager._principle_store = None

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_device_token] = lambda: "test-token"

        # Force inference to fail so stub path is exercised
        with patch("hestia.api.routes.research.get_research_manager", return_value=manager):
            with patch(
                "hestia.inference.get_inference_client",
                side_effect=RuntimeError("offline"),
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as c:
                    response = await c.post(
                        "/v1/research/principles/distill-from-selection",
                        json={"entity_ids": [entity.id], "board_id": "board-abc"},
                    )

        assert response.status_code == 200
        data = response.json()
        assert "principle" in data
        p = data["principle"]
        assert p["status"] == "pending"
        assert "FastAPI" in p["content"]

        await db.close()

    @pytest.mark.asyncio
    async def test_distill_with_mocked_inference(self, tmp_path: Path) -> None:
        """Distill-from-selection stores a principle when inference returns content."""
        from datetime import datetime, timezone
        from fastapi import FastAPI
        from hestia.api.routes.research import router
        from hestia.api.middleware.auth import get_device_token
        from hestia.inference import InferenceResponse
        from hestia.research.models import Entity, EntityType

        db = ResearchDatabase(db_path=tmp_path / "distill_mock.db")
        await db.initialize()

        now = datetime.now(timezone.utc)
        entity = Entity(
            id="entity-fastapi-2",
            name="FastAPI",
            entity_type=EntityType.TOOL,
            canonical_name="fastapi",
            created_at=now,
            updated_at=now,
        )
        await db.create_entity(entity)

        manager = MagicMock()
        manager._database = db
        manager._principle_store = None

        # Mock inference response
        mock_inference = MagicMock()
        mock_inference.chat = AsyncMock(
            return_value=InferenceResponse(
                content="[tooling] Prefer async frameworks for IO-bound APIs",
                model="test-model",
                tokens_in=10,
                tokens_out=10,
                duration_ms=50.0,
            )
        )

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_device_token] = lambda: "test-token"

        with patch("hestia.api.routes.research.get_research_manager", return_value=manager):
            with patch("hestia.inference.get_inference_client", return_value=mock_inference):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as c:
                    response = await c.post(
                        "/v1/research/principles/distill-from-selection",
                        json={"entity_ids": [entity.id], "board_id": "board-xyz"},
                    )

        assert response.status_code == 200
        data = response.json()
        principle = data["principle"]
        assert principle["status"] == "pending"

        await db.close()
