"""Tests for pooled Jira clients and shared HTTP sessions."""

import json

import httpx
import pytest

from simple_jira_mcp.config import load_configs, reset_config_state
from simple_jira_mcp.jira import client as jira_client
from simple_jira_mcp.jira.client import JiraClient, close_clients, get_client
from simple_jira_mcp.utils.errors import is_error


@pytest.fixture
def configs(monkeypatch):
    monkeypatch.setenv(
        "JIRA_CONFIG_JSON",
        json.dumps(
            [
                {
                    "id": config_id,
                    "url": f"https://{config_id}.atlassian.net",
                    "email": "user@example.com",
                    "token": "test-token",
                }
                for config_id in ("default", "second")
            ]
        ),
    )
    reset_config_state()
    jira_client._clients.clear()
    yield load_configs()
    reset_config_state()
    jira_client._clients.clear()


def test_get_client_reuses_client_per_config(configs):
    default = get_client()

    assert isinstance(default, JiraClient)
    assert get_client() is default
    assert get_client("default") is default
    assert get_client("second") is not default
    assert get_client("second").config.id == "second"


def test_get_client_rebuilds_after_config_reload(configs):
    before = get_client()

    load_configs()

    assert get_client() is not before


@pytest.mark.parametrize(
    "config_id,message",
    [("unknown", "Configuration 'unknown' not found")],
)
def test_get_client_unknown_config(configs, config_id, message):
    result = get_client(config_id)

    assert is_error(result)
    assert result["error"] == {"code": "CONFIG_NOT_FOUND", "message": message}


def test_get_client_without_configs():
    reset_config_state()

    result = get_client()

    assert is_error(result)
    assert result["error"]["message"] == "No configuration available"


async def test_operations_share_one_authenticated_http_client(client, monkeypatch):
    created = []
    requests = []
    real_async_client = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"key": "ONE-1", "transitions": []})

    def factory(**kwargs):
        created.append(kwargs)
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("simple_jira_mcp.jira.base.httpx.AsyncClient", factory)

    await client.get_issue("ONE-1")
    await client.get_transitions("ONE-1")

    assert len(created) == 1
    assert len(requests) == 2
    assert all(r.headers["authorization"].startswith("Basic ") for r in requests)


async def test_close_clients_closes_and_empties_pool(configs):
    client = get_client()
    assert isinstance(client, JiraClient)
    http = client._session.client

    await close_clients()

    assert http.is_closed
    assert jira_client._clients == {}
    # Closing a session that never opened a connection is a no-op.
    await JiraClient(configs[0]).aclose()


def test_is_error_only_matches_error_payloads(configs):
    assert is_error({"isError": True, "error": {"code": "X", "message": "m"}})
    assert not is_error({"key": "ONE-1"})
    assert not is_error({"isError": False})
    assert not is_error(get_client())
