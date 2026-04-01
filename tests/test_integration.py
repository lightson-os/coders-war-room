"""
Integration smoke test for the War Room.
Tests the full flow: server + CLI + tmux dispatch.

Run with: python3 -m pytest tests/test_integration.py -v -s
Note: Requires tmux to be installed. Creates temporary tmux sessions.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import httpx

SERVER_URL = "http://localhost:5680"
PROJECT_DIR = Path(__file__).parent.parent
TEST_SESSION = "warroom-test-agent"


@pytest.fixture(scope="module", autouse=True)
def server():
    """Start the war room server for the test suite."""
    # Kill any existing server on port 5680
    subprocess.run(["pkill", "-f", "python3.*server.py"], capture_output=True)
    time.sleep(1)

    # Remove test DB if exists
    db_path = PROJECT_DIR / "warroom.db"
    if db_path.exists():
        db_path.unlink()

    proc = subprocess.Popen(
        ["python3", str(PROJECT_DIR / "server.py")],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)  # Wait for server to start
    yield proc
    proc.terminate()
    proc.wait(timeout=5)
    # Clean up DB
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(autouse=True)
def tmux_session():
    """Create and clean up a test tmux session."""
    subprocess.run(["tmux", "kill-session", "-t", TEST_SESSION],
                    capture_output=True)
    subprocess.run(["tmux", "new-session", "-d", "-s", TEST_SESSION, "-x", "200", "-y", "50"],
                    check=True)
    time.sleep(0.5)
    yield
    subprocess.run(["tmux", "kill-session", "-t", TEST_SESSION],
                    capture_output=True)


def test_post_and_retrieve_message():
    """Post a message via API and retrieve it."""
    resp = httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "phase-1",
        "target": "all",
        "content": "Integration test message",
    })
    assert resp.status_code == 200
    msg = resp.json()
    assert msg["content"] == "Integration test message"

    resp = httpx.get(f"{SERVER_URL}/api/messages?limit=5")
    assert resp.status_code == 200
    messages = resp.json()
    contents = [m["content"] for m in messages]
    assert "Integration test message" in contents


def test_cli_post():
    """Post a message via warroom.sh CLI."""
    env = {**os.environ, "WARROOM_AGENT_NAME": "phase-2"}
    result = subprocess.run(
        [str(PROJECT_DIR / "warroom.sh"), "post", "CLI test message"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert "OK" in result.stdout

    resp = httpx.get(f"{SERVER_URL}/api/messages?limit=5")
    messages = resp.json()
    found = [m for m in messages if m["content"] == "CLI test message"]
    assert len(found) == 1
    assert found[0]["sender"] == "phase-2"


def test_cli_history():
    """Retrieve message history via CLI."""
    httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "supervisor",
        "content": "History test marker",
    })

    env = {**os.environ, "WARROOM_AGENT_NAME": "test"}
    result = subprocess.run(
        [str(PROJECT_DIR / "warroom.sh"), "history", "--count", "10"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert "History test marker" in result.stdout
    assert "supervisor" in result.stdout


def test_agent_list():
    """Verify agent roster is returned correctly."""
    resp = httpx.get(f"{SERVER_URL}/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    names = [a["name"] for a in agents]
    assert "supervisor" in names
    assert "phase-1" in names
    assert "git-agent" in names
    assert len(agents) == 8


def test_message_truncation_endpoint():
    """Verify the /message/<id> endpoint returns full content."""
    long_content = "A" * 1000
    resp = httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "phase-3",
        "content": long_content,
    })
    msg_id = resp.json()["id"]

    resp = httpx.get(f"{SERVER_URL}/message/{msg_id}")
    assert resp.status_code == 200
    assert len(resp.text) == 1000


def test_direct_message():
    """Verify direct messages are stored with correct target."""
    resp = httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "supervisor",
        "target": "phase-1",
        "content": "Direct message test",
    })
    assert resp.status_code == 200
    msg = resp.json()
    assert msg["target"] == "phase-1"


def test_browse_api():
    """Test the directory browse endpoint."""
    import os
    home = os.path.expanduser("~")
    resp = httpx.get(f"{SERVER_URL}/api/browse?path={home}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] == home
    assert len(data["directories"]) > 0
    # Security: browsing outside home should fail
    resp = httpx.get(f"{SERVER_URL}/api/browse?path=/etc")
    assert resp.status_code == 403


def test_create_and_use_dynamic_agent():
    """Test creating a dynamic agent via API and verifying it joins the roster."""
    import os
    # Name must match ^[a-z0-9][a-z0-9\-]{0,18}[a-z0-9]$ (max 20 chars)
    agent_name = "int-test-agent"
    resp = httpx.post(f"{SERVER_URL}/api/agents/create", json={
        "name": agent_name,
        "directory": os.path.expanduser("~"),
        "role": "Integration test",
        "initial_prompt": "",
        "model": "opus",
        "skip_permissions": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    assert data["agent"]["name"] == agent_name

    # Verify it shows up in the agent list
    resp = httpx.get(f"{SERVER_URL}/api/agents")
    agents = resp.json()
    names = [a["name"] for a in agents]
    assert agent_name in names

    # Clean up: kill the tmux session
    subprocess.run(["tmux", "kill-session", "-t", f"warroom-{agent_name}"], capture_output=True)
