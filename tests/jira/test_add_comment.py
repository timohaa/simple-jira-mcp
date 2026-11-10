"""Tests for the add-comment request payload and result."""

import json

import httpx


async def test_add_comment(client, patch_async_client):
    requests = []
    created = "2026-10-01T12:34:56.000+0000"
    body = "First line\nSecond line\n\nAnother paragraph"

    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={"id": "10001", "created": created})

    patch_async_client(httpx.MockTransport(handler))
    result = await client.add_comment("ONE-123", body)

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/rest/api/3/issue/ONE-123/comment"
    assert requests[0].headers["authorization"].startswith("Basic ")
    assert json.loads(requests[0].content) == {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "First line"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "Second line"},
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Another paragraph"}],
                },
            ],
        }
    }
    assert result == {"id": "10001", "created": created}
