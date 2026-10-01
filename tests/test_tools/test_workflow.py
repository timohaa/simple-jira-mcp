"""Tests for issue workflow tool validation and config selection."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from src.config import load_configs, reset_config_state
from src.jira.adf import text_to_adf
from src.tools import workflow

TOOL_ARGUMENTS = [
    ("get_transitions", {}),
    ("transition_issue", {"transition": "Done"}),
    ("add_comment", {"body": "Comment"}),
]


@pytest.fixture(autouse=True)
def clean_config():
    reset_config_state()
    yield
    reset_config_state()


@pytest.fixture
def mock_config(monkeypatch):
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
    return load_configs()


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
@pytest.mark.parametrize("issue_key", ["", "   ", "invalid", "ONE-1/comment"])
async def test_issue_key_validation(tool_name, kwargs, issue_key):
    result = await getattr(workflow, tool_name)(issue_key, **kwargs)

    assert result["isError"] is True
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
async def test_missing_config(tool_name, kwargs):
    result = await getattr(workflow, tool_name)("ONE-123", **kwargs)

    assert result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert result["error"]["message"] == "No configuration available"


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
async def test_unknown_config(mock_config, tool_name, kwargs):
    result = await getattr(workflow, tool_name)(
        "ONE-123", config_id="unknown", **kwargs
    )

    assert result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert "unknown" in result["error"]["message"]


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
@pytest.mark.parametrize("config_id", [None, "second"])
async def test_config_and_key_normalization(
    mock_config, monkeypatch, tool_name, kwargs, config_id
):
    method = AsyncMock(return_value={"success": True})
    constructor = []
    real_client = workflow.JiraClient

    def make_client(config):
        constructor.append(config)
        client = real_client(config)
        setattr(client, tool_name, method)
        return client

    monkeypatch.setattr(workflow, "JiraClient", make_client)
    result = await getattr(workflow, tool_name)(
        " one-123 ", config_id=config_id, **kwargs
    )

    assert result == {"success": True}
    assert constructor[0].id == (config_id or "default")
    assert method.await_args.args[0] == "ONE-123"


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"transition": ""}, "Transition is required"),
        ({"transition": "   "}, "Transition is required"),
        ({"comment": ""}, "Comment must not be empty"),
        ({"comment": "  "}, "Comment must not be empty"),
        ({"resolution": ""}, "Resolution must not be empty"),
        ({"resolution": "  "}, "Resolution must not be empty"),
    ],
)
async def test_transition_input_validation(mock_config, monkeypatch, kwargs, message):
    method = AsyncMock()
    monkeypatch.setattr(workflow.JiraClient, "transition_issue", method)
    result = await workflow.transition_issue(
        "ONE-123", **{"transition": "Done", **kwargs}
    )

    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert result["error"]["message"] == message
    method.assert_not_awaited()


@pytest.mark.parametrize("body", ["", "   ", "\n\n"])
async def test_comment_body_required(mock_config, monkeypatch, body):
    method = AsyncMock()
    monkeypatch.setattr(workflow.JiraClient, "add_comment", method)
    result = await workflow.add_comment("ONE-123", body)

    assert result["error"]["code"] == "VALIDATION_ERROR"
    method.assert_not_awaited()


async def test_transition_forwards_options(mock_config, monkeypatch):
    response = {"key": "ONE-123", "status": "Done", "resolution": "Fixed"}
    method = AsyncMock(return_value=response)
    monkeypatch.setattr(workflow.JiraClient, "transition_issue", method)
    result = await workflow.transition_issue(
        "ONE-123", "Done", "Completed on 2026-09-30", "Fixed", {"customfield_1": "Done"}
    )

    assert result == response
    method.assert_awaited_once_with(
        "ONE-123",
        "Done",
        comment="Completed on 2026-09-30",
        resolution="Fixed",
        fields={"customfield_1": "Done"},
    )


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
async def test_runtime_error_forwarded(mock_config, monkeypatch, tool_name, kwargs):
    error = {
        "isError": True,
        "error": {"code": "AUTH_FAILED", "message": "Invalid credentials"},
    }
    monkeypatch.setattr(workflow.JiraClient, tool_name, AsyncMock(return_value=error))

    assert await getattr(workflow, tool_name)("ONE-123", **kwargs) == error


async def test_comment_tool_integration(mock_config, monkeypatch):
    requests = []
    real_async_client = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={"id": "123", "created": "2026-10-01"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "src.jira.workflow.httpx.AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )
    result = await workflow.add_comment(" one-123 ", "Body", config_id="second")

    assert requests[0].url.host == "second.atlassian.net"
    assert requests[0].url.path == "/rest/api/3/issue/ONE-123/comment"
    assert json.loads(requests[0].content) == {"body": text_to_adf("Body")}
    assert result == {"id": "123", "created": "2026-10-01"}
