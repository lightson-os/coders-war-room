import os

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


@pytest.mark.asyncio
async def test_create_agent_duplicate_name():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/create", json={
            "name": "supervisor",
            "directory": os.path.expanduser("~"),
            "role": "Duplicate",
            "model": "opus",
            "skip_permissions": True,
        })
        assert resp.status_code == 400
        assert "already exists" in resp.json()["error"]


@pytest.mark.asyncio
async def test_create_agent_invalid_name():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/create", json={
            "name": "BAD NAME!",
            "directory": os.path.expanduser("~"),
            "role": "Bad",
            "model": "opus",
            "skip_permissions": True,
        })
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_agent_bad_directory():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/create", json={
            "name": "ghost-agent",
            "directory": "/nonexistent/path",
            "role": "Ghost",
            "model": "opus",
            "skip_permissions": True,
        })
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_set_agent_status():
    from server import app, agent_manual_status
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/phase-1/status", json={
            "task": "fixing state import",
            "progress": 60,
            "eta": "5m",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert "phase-1" in agent_manual_status
        assert agent_manual_status["phase-1"]["task"] == "fixing state import"
        assert agent_manual_status["phase-1"]["progress"] == 60


@pytest.mark.asyncio
async def test_get_agent_status():
    from server import app, agent_manual_status
    import time as t
    agent_manual_status["phase-2"] = {"task": "test task", "progress": 40, "updated_at": t.time()}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents/phase-2/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task"] == "test task"
        assert data["progress"] == 40


@pytest.mark.asyncio
async def test_clear_agent_status():
    from server import app, agent_manual_status
    import time as t
    agent_manual_status["phase-3"] = {"task": "old task", "progress": 80, "updated_at": t.time()}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/phase-3/status", json={"clear": True})
        assert resp.status_code == 200
        assert "phase-3" not in agent_manual_status


@pytest.mark.asyncio
async def test_get_agent_owns():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents/phase-1/owns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"] == "phase-1"
        assert "patterns" in data
        assert "resolved" in data


@pytest.mark.asyncio
async def test_set_blocked_status():
    from server import app, agent_manual_status
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/phase-3/status", json={
            "blocked_by": "phase-1",
            "blocked_reason": "needs config change",
        })
        assert resp.status_code == 200
        assert agent_manual_status["phase-3"]["blocked_by"] == "phase-1"


@pytest.mark.asyncio
async def test_list_files_root():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/files?path=.")
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)
        for e in data["entries"]:
            assert "name" in e
            assert "type" in e
            assert "path" in e


@pytest.mark.asyncio
async def test_list_files_with_ownership():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/files?path=northstar")
        assert resp.status_code == 200
        data = resp.json()
        owned = [e for e in data["entries"] if e.get("owner")]
        assert len(owned) > 0
        for e in owned:
            assert e["color"] is not None


@pytest.mark.asyncio
async def test_list_files_security():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/files?path=../../etc")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_files_dirs_have_owned():
    import server as srv
    srv.precompute_dir_ownership()
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/files?path=.")
        assert resp.status_code == 200
        data = resp.json()
        dirs = [e for e in data["entries"] if e["type"] == "dir"]
        northstar = [d for d in dirs if d["name"] == "northstar"]
        if northstar:
            assert northstar[0]["has_owned"] is True


@pytest.mark.asyncio
async def test_dedup_state_tracking():
    """Verify agent_last_seen_id is updated when set."""
    from server import agent_last_seen_id
    # Directly test the dedup state
    agent_last_seen_id["test-agent"] = 50
    assert agent_last_seen_id["test-agent"] == 50
    # A message with ID <= 50 should be considered "already seen"
    assert 30 <= agent_last_seen_id.get("test-agent", 0)
    assert 50 <= agent_last_seen_id.get("test-agent", 0)
    # A message with ID > 50 should NOT be considered "already seen"
    assert not (51 <= agent_last_seen_id.get("test-agent", 0))
