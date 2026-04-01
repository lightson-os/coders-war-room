import pytest
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
async def test_post_message():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/messages", json={
            "sender": "phase-1",
            "target": "all",
            "content": "Hello war room",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sender"] == "phase-1"
        assert data["target"] == "all"
        assert data["content"] == "Hello war room"
        assert data["id"] is not None
        assert data["timestamp"] is not None


@pytest.mark.asyncio
async def test_get_messages():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/messages", json={
            "sender": "phase-1", "content": "First message",
        })
        await client.post("/api/messages", json={
            "sender": "phase-2", "content": "Second message",
        })
        resp = await client.get("/api/messages?limit=10")
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) >= 2
        contents = [m["content"] for m in messages]
        assert "First message" in contents
        assert "Second message" in contents


@pytest.mark.asyncio
async def test_get_single_message():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/messages", json={
            "sender": "supervisor", "content": "A long message for retrieval",
        })
        msg_id = resp.json()["id"]
        resp = await client.get(f"/message/{msg_id}")
        assert resp.status_code == 200
        assert "A long message for retrieval" in resp.text


@pytest.mark.asyncio
async def test_get_agents():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        agents = resp.json()
        names = [a["name"] for a in agents]
        assert "supervisor" in names
        assert "phase-1" in names
        assert "git-agent" in names
        assert len(agents) == 8


@pytest.mark.asyncio
async def test_direct_message():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/messages", json={
            "sender": "supervisor",
            "target": "phase-1",
            "content": "Fix the state import",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target"] == "phase-1"


@pytest.mark.asyncio
async def test_browse_home():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        import os
        home = os.path.expanduser("~")
        resp = await client.get(f"/api/browse?path={home}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == home
        assert "parent" in data
        assert "directories" in data
        assert isinstance(data["directories"], list)
        assert len(data["directories"]) > 0
        for d in data["directories"]:
            assert "name" in d
            assert "path" in d
        names = [d["name"] for d in data["directories"]]
        assert ".Trash" not in names
        assert "Library" not in names
        assert "Applications" not in names


@pytest.mark.asyncio
async def test_browse_security_boundary():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/browse?path=/etc")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_browse_nonexistent():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/browse?path=/Users/gurvindersingh/nonexistent_dir_xyz")
        assert resp.status_code == 404
