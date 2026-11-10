"""Tests for issue workflow tool validation and config selection."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from simple_jira_mcp.jira import client as jira_client
from simple_jira_mcp.jira.client import JiraClient
from simple_jira_mcp.tools import workflow

TOOL_ARGUMENTS = [
    ("get_transitions", {}),
    ("transition_issue", {"transition": "Done"}),
    ("add_comment", {"body": "Comment"}),
]


pytestmark = pytest.mark.usefixtures("clean_config")


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
async def test_unknown_config(two_configs, tool_name, kwargs):
    result = await getattr(workflow, tool_name)(
        "ONE-123", config_id="unknown", **kwargs
    )

    assert result["error"]["code"] == "CONFIG_NOT_FOUND"
    assert "unknown" in result["error"]["message"]


@pytest.mark.parametrize("tool_name,kwargs", TOOL_ARGUMENTS)
@pytest.mark.parametrize(
    "config_id,used_config", [(None, "default"), ("second", "second")]
)
async def test_config_and_key_normalization(
    two_configs, monkeypatch, tool_name, kwargs, config_id, used_config
):
    method = AsyncMock(return_value={"success": True})
    constructor = []
    real_client = JiraClient

    def make_client(config):
        constructor.append(config)
        client = real_client(config)
        setattr(client, tool_name, method)
        return client

    monkeypatch.setattr(jira_client, "JiraClient", make_client)
    result = await getattr(workflow, tool_name)(
        " one-123 ", config_id=config_id, **kwargs
    )

    assert result == {"success": True}
    assert [config.id for config in constructor] == [used_config]
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
async def test_transition_input_validation(two_configs, monkeypatch, kwargs, message):
    method = AsyncMock()
    monkeypatch.setattr(JiraClient, "transition_issue", method)
    result = await workflow.transition_issue(
        "ONE-123", **{"transition": "Done", **kwargs}
    )

    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert result["error"]["message"] == message
    method.assert_not_awaited()


@pytest.mark.parametrize("body", ["", "   ", "\n\n"])
async def test_comment_body_required(two_configs, monkeypatch, body):
    method = AsyncMock()
    monkeypatch.setattr(JiraClient, "add_comment", method)
    result = await workflow.add_comment("ONE-123", body)

    assert result["error"]["code"] == "VALIDATION_ERROR"
    method.assert_not_awaited()


async def test_transition_forwards_options(two_configs, monkeypatch):
    response = {"key": "ONE-123", "status": "Done", "resolution": "Fixed"}
    method = AsyncMock(return_value=response)
    monkeypatch.setattr(JiraClient, "transition_issue", method)
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
async def test_runtime_error_forwarded(two_configs, monkeypatch, tool_name, kwargs):
    error = {
        "isError": True,
        "error": {"code": "AUTH_FAILED", "message": "Invalid credentials"},
    }
    monkeypatch.setattr(JiraClient, tool_name, AsyncMock(return_value=error))

    assert await getattr(workflow, tool_name)("ONE-123", **kwargs) == error


async def test_comment_tool_integration(two_configs, patch_async_client):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={"id": "123", "created": "2026-10-01"})

    patch_async_client(httpx.MockTransport(handler))
    result = await workflow.add_comment(" one-123 ", "Body", config_id="second")

    assert requests[0].url.host == "second.atlassian.net"
    assert requests[0].url.path == "/rest/api/3/issue/ONE-123/comment"
    assert json.loads(requests[0].content) == {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Body"}]}
            ],
        }
    }
    assert result == {"id": "123", "created": "2026-10-01"}
