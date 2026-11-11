"""Fixtures shared by all tests."""

import json
import os
from functools import partial
from pathlib import Path

import httpx
import pytest

from simple_jira_mcp.config import load_configs, reset_config_state

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def clean_config():
    """Reset config state before and after each test."""
    original = os.environ.get("JIRA_CONFIG_JSON")

    reset_config_state()

    yield

    if original:
        os.environ["JIRA_CONFIG_JSON"] = original
    elif "JIRA_CONFIG_JSON" in os.environ:
        del os.environ["JIRA_CONFIG_JSON"]

    reset_config_state()


@pytest.fixture
def mock_config(clean_config):
    """Load a single config with id "test"."""
    config_data = [
        {
            "id": "test",
            "url": "https://test.atlassian.net",
            "email": "test@example.com",
            "token": "test-token",
        }
    ]
    os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
    return load_configs()


@pytest.fixture
def two_configs(clean_config):
    """Load two configs: "default" (the default) and "second"."""
    config_data = [
        {
            "id": config_id,
            "url": f"https://{config_id}.atlassian.net",
            "email": "user@example.com",
            "token": "test-token",
        }
        for config_id in ("default", "second")
    ]
    os.environ["JIRA_CONFIG_JSON"] = json.dumps(config_data)
    return load_configs()


@pytest.fixture
def patch_async_client(monkeypatch):
    """Route the Jira client's HTTP requests through a mock transport."""

    def _apply(transport: httpx.MockTransport) -> None:
        async_client = partial(httpx.AsyncClient, transport=transport)
        monkeypatch.setattr("simple_jira_mcp.jira.base.httpx.AsyncClient", async_client)

    return _apply


class Replay:
    """Answer requests with the recorded exchanges of one scenario, in order.

    A request that differs from the recorded one in method, path or query
    fails the test, as does a request beyond the end of the recording.
    """

    def __init__(self, exchanges, faults):
        self._exchanges = exchanges
        self._faults = faults
        self.requests = []

    def __call__(self, request):
        index = len(self.requests)
        self.requests.append(request)
        assert index < len(self._exchanges), f"Unrecorded request: {request.url}"
        recorded = self._exchanges[index]
        expected_path = httpx.URL(recorded["request"]["url"]).raw_path
        assert request.method == recorded["request"]["method"]
        assert request.url.raw_path == expected_path
        if index in self._faults:
            return self._faults[index]
        response = recorded["response"]
        body = response["body"]
        if body is None:
            content = b""
        elif isinstance(body, str):
            content = body.encode()
        else:
            content = json.dumps(body).encode()
        return httpx.Response(
            response["status"], headers=response["headers"], content=content
        )

    def sent(self, index):
        """Return the JSON body of the request at index."""
        return json.loads(self.requests[index].content)


@pytest.fixture
def replay(patch_async_client):
    """Replay `tests/fixtures/<name>.json`, a recording of a real Jira site.

    `faults` maps a request index to a response returned in place of the
    recorded one, for failures a live site cannot be made to produce.
    """

    def _start(name, faults=None):
        exchanges = json.loads((FIXTURES / f"{name}.json").read_text())
        player = Replay(exchanges, faults or {})
        patch_async_client(httpx.MockTransport(player))
        return player

    return _start
