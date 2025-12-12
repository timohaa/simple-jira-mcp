"""Tests for JiraClient download_attachment operations."""

import tempfile
from pathlib import Path

import httpx
import pytest


@pytest.mark.asyncio
async def test_download_attachment_sanitizes_filename(client, patch_async_client):
    """Test download_attachment sanitizes filenames to prevent path traversal."""
    recorded: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        recorded["url"] = str(request.url)
        return httpx.Response(
            200,
            content=b"data",
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "12345",
            Path(tmpdir),
            "ONE-123",
            filename="../../etc/passwd.png",
        )

        saved_path = Path(result["path"])
        assert saved_path.name == "passwd.png"
        assert saved_path.parent.name == "ONE-123"
        assert saved_path.exists()
        assert recorded["url"].endswith("/rest/api/3/attachment/content/12345")
        assert result["success"] is True


@pytest.mark.asyncio
async def test_download_attachment_auth_failed_error(client, patch_async_client):
    """Test download_attachment returns error on authentication failure."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "12345", Path(tmpdir), "ONE-123", "file.txt"
        )

    assert result["isError"] is True
    assert result["error"]["code"] == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_download_attachment_not_found_error(client, patch_async_client):
    """Test download_attachment returns error when attachment not found."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "12345", Path(tmpdir), "ONE-123", "file.txt"
        )

    assert result["isError"] is True
    assert result["error"]["code"] == "ATTACHMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_download_attachment_rate_limited_error(client, patch_async_client):
    """Test download_attachment returns error when rate limited."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "12345", Path(tmpdir), "ONE-123", "file.txt"
        )

    assert result["isError"] is True
    assert result["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_download_attachment_other_status_error(client, patch_async_client):
    """Test download_attachment returns error for server errors."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "12345", Path(tmpdir), "ONE-123", "file.txt"
        )

    assert result["isError"] is True
    assert result["error"]["code"] == "DOWNLOAD_FAILED"
    assert "500" in result["error"]["message"]


@pytest.mark.asyncio
async def test_download_attachment_request_error(client, patch_async_client):
    """Test download_attachment handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "12345", Path(tmpdir), "ONE-123", "file.txt"
        )

    assert result["isError"] is True
    assert result["error"]["code"] == "DOWNLOAD_FAILED"
    assert "Download failed" in result["error"]["message"]
