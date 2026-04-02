import asyncio
import sys
from pathlib import Path

import pytest

# Ensure server module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _init_db(tmp_path, monkeypatch):
    """Use a fresh temporary DB for every test."""
    import server

    test_db = tmp_path / "test_warroom.db"
    monkeypatch.setattr(server, "DB_PATH", test_db)
    monkeypatch.setattr(server, "agent_queues", {})
    monkeypatch.setattr(server, "connected_clients", [])
    monkeypatch.setattr(server, "agent_membership", {a["name"]: True for a in server.AGENTS})
    monkeypatch.setattr(server, "agent_manual_status", {})
    monkeypatch.setattr(server, "agent_last_state", {})
    monkeypatch.setattr(server, "agent_last_commit", {})
    monkeypatch.setattr(server, "agent_last_seen_id", {})
    monkeypatch.setattr(server, "dir_has_owned", {})
    loop = asyncio.new_event_loop()
    loop.run_until_complete(server.init_db())
    loop.close()
