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
async def test_download_attachment_dot_only_filename(client, patch_async_client):
    """Test dot-only filenames fall back to a safe name instead of a directory."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "12345", Path(tmpdir), "ONE-123", filename=".."
        )

        saved_path = Path(result["path"])
        assert saved_path.name == "attachment"
        assert saved_path.parent == Path(tmpdir) / "ONE-123"
        assert saved_path.exists()


@pytest.mark.asyncio
async def test_download_attachment_write_failure_returns_error(
    client, patch_async_client
):
    """Test filesystem errors return DOWNLOAD_FAILED."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data")

    transport = httpx.MockTransport(handler)
    patch_async_client(transport)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Occupy the issue directory's path with a file so mkdir fails
        (Path(tmpdir) / "ONE-123").write_text("in the way")
        result = await client.download_attachment(
            "12345", Path(tmpdir), "ONE-123", "file.txt"
        )

    assert result["isError"] is True
    assert result["error"]["code"] == "DOWNLOAD_FAILED"
    assert "File write failed" in result["error"]["message"]


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


async def test_same_named_attachments_do_not_overwrite(client, patch_async_client):
    """A second attachment with a taken filename gets its ID in the name."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=request.url.path.rsplit("/", 1)[-1].encode())

    patch_async_client(httpx.MockTransport(handler))

    with tempfile.TemporaryDirectory() as tmpdir:
        first = await client.download_attachment(
            "111", Path(tmpdir), "ONE-123", "log.txt"
        )
        second = await client.download_attachment(
            "222", Path(tmpdir), "ONE-123", "log.txt"
        )
        again = await client.download_attachment(
            "222", Path(tmpdir), "ONE-123", "log.txt"
        )

        assert first["filename"] == "log.txt"
        assert second["filename"] == "log-222.txt"
        assert again["path"] == second["path"]
        assert Path(first["path"]).read_bytes() == b"111"
        assert Path(second["path"]).read_bytes() == b"222"


async def test_download_streams_body_and_reports_size(client, patch_async_client):
    payload = b"x" * 300_000

    patch_async_client(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=payload, headers={"content-type": "application/zip"}
            )
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "1", Path(tmpdir), "ONE-123", "big.zip"
        )

        assert Path(result["path"]).read_bytes() == payload
        assert result["size_kb"] == round(len(payload) / 1024, 2)
        assert result["mime_type"] == "application/zip"


async def test_interrupted_download_leaves_no_partial_file(client, patch_async_client):
    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"partial"
            raise httpx.ReadError("connection dropped")

    patch_async_client(
        httpx.MockTransport(lambda _: httpx.Response(200, stream=BrokenStream()))
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "1", Path(tmpdir), "ONE-123", "file.bin"
        )

        assert result["error"]["code"] == "DOWNLOAD_FAILED"
        assert "connection dropped" in result["error"]["message"]
        assert list((Path(tmpdir) / "ONE-123").iterdir()) == []


async def test_error_status_creates_no_directory(client, patch_async_client):
    patch_async_client(httpx.MockTransport(lambda _: httpx.Response(404)))

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await client.download_attachment(
            "1", Path(tmpdir), "ONE-123", "file.bin"
        )

        assert result["error"]["code"] == "ATTACHMENT_NOT_FOUND"
        assert list(Path(tmpdir).iterdir()) == []
