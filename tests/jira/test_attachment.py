"""Tests for JiraClient download_attachment operations."""

from pathlib import Path

import httpx
import pytest


async def test_download_attachment_sanitizes_filename(client, replay, tmp_path):
    """Test download_attachment sanitizes filenames to prevent path traversal."""
    jira = replay("download_attachment")

    result = await client.download_attachment(
        "10007", tmp_path, "ONE-1", filename="../../etc/passwd.txt"
    )

    assert str(jira.requests[0].url).endswith("/rest/api/3/attachment/content/10007")
    assert result["success"] is True
    assert Path(result["path"]) == tmp_path / "ONE-1" / "passwd.txt"
    assert Path(result["path"]).read_bytes() == b"recorded attachment\n"


async def test_download_attachment_dot_only_filename(client, replay, tmp_path):
    """Test dot-only filenames fall back to a safe name instead of a directory."""
    replay("download_attachment")

    result = await client.download_attachment("10007", tmp_path, "ONE-1", filename="..")

    assert Path(result["path"]) == tmp_path / "ONE-1" / "attachment"
    assert Path(result["path"]).read_bytes() == b"recorded attachment\n"


async def test_download_attachment_write_failure_returns_error(
    client, replay, tmp_path
):
    """Test filesystem errors return DOWNLOAD_FAILED."""
    replay("download_attachment")
    # Occupy the issue directory's path with a file so mkdir fails
    (tmp_path / "ONE-1").write_text("in the way")

    result = await client.download_attachment("10007", tmp_path, "ONE-1", "notes.txt")

    assert result["isError"] is True
    assert result["error"]["code"] == "DOWNLOAD_FAILED"
    assert "File write failed" in result["error"]["message"]


@pytest.mark.parametrize(
    "status,code,message",
    [
        (401, "AUTH_FAILED", "Invalid credentials"),
        (429, "RATE_LIMITED", "Too many requests"),
        (500, "DOWNLOAD_FAILED", "Download failed: 500"),
    ],
    ids=["401", "429", "500"],
)
async def test_download_attachment_bare_status_errors(
    client, patch_async_client, tmp_path, status, code, message
):
    """Bare statuses a live site cannot be made to return on demand."""
    patch_async_client(httpx.MockTransport(lambda _: httpx.Response(status)))

    result = await client.download_attachment("12345", tmp_path, "ONE-123", "f.txt")

    assert result == {"isError": True, "error": {"code": code, "message": message}}
    assert list(tmp_path.iterdir()) == []


async def test_download_attachment_request_error(client, patch_async_client, tmp_path):
    """Test download_attachment handles connection errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("Connection failed")

    patch_async_client(httpx.MockTransport(handler))

    result = await client.download_attachment("12345", tmp_path, "ONE-123", "file.txt")

    assert result["isError"] is True
    assert result["error"]["code"] == "DOWNLOAD_FAILED"
    assert "Download failed" in result["error"]["message"]


async def test_same_named_attachments_do_not_overwrite(
    client, patch_async_client, tmp_path
):
    """A second attachment with a taken filename gets its ID in the name.

    The recordings hold one attachment, so two with the same name are built here.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=request.url.path.rsplit("/", 1)[-1].encode())

    patch_async_client(httpx.MockTransport(handler))

    first = await client.download_attachment("111", tmp_path, "ONE-123", "log.txt")
    second = await client.download_attachment("222", tmp_path, "ONE-123", "log.txt")
    again = await client.download_attachment("222", tmp_path, "ONE-123", "log.txt")

    assert first["filename"] == "log.txt"
    assert second["filename"] == "log-222.txt"
    assert again["path"] == second["path"]
    assert Path(first["path"]).read_bytes() == b"111"
    assert Path(second["path"]).read_bytes() == b"222"


async def test_download_streams_body_and_reports_size(
    client, patch_async_client, tmp_path
):
    """The recorded attachment is tiny, so a large body is built here."""
    payload = b"x" * 300_000

    patch_async_client(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=payload, headers={"content-type": "application/zip"}
            )
        )
    )

    result = await client.download_attachment("1", tmp_path, "ONE-123", "big.zip")

    assert Path(result["path"]).read_bytes() == payload
    assert result["size_kb"] == 292.97
    assert result["mime_type"] == "application/zip"


async def test_interrupted_download_leaves_no_partial_file(
    client, patch_async_client, tmp_path
):
    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"partial"
            raise httpx.ReadError("connection dropped")

    patch_async_client(
        httpx.MockTransport(lambda _: httpx.Response(200, stream=BrokenStream()))
    )

    result = await client.download_attachment("1", tmp_path, "ONE-123", "file.bin")

    assert result["error"]["code"] == "DOWNLOAD_FAILED"
    assert "connection dropped" in result["error"]["message"]
    assert list((tmp_path / "ONE-123").iterdir()) == []


async def test_download_follows_recorded_redirect_to_media_host(
    client, replay, tmp_path
):
    """Jira answers the content URL with a redirect to its media store."""
    jira = replay("download_attachment")

    result = await client.download_attachment("10007", tmp_path, "ONE-1", "notes.txt")

    assert [str(request.url) for request in jira.requests] == [
        "https://example.atlassian.net/rest/api/3/attachment/content/10007",
        "https://media.example.net/file",
    ]
    assert Path(result["path"]).read_bytes() == b"recorded attachment\n"
    assert result["filename"] == "notes.txt"
    assert result["size_kb"] == 0.02
    assert result["mime_type"] == "text/plain"


async def test_download_of_missing_attachment_is_not_found(client, replay, tmp_path):
    """A missing attachment returns not found and creates no directory."""
    replay("download_attachment_not_found")

    result = await client.download_attachment(
        "99999999", tmp_path, "ONE-1", "notes.txt"
    )

    assert result["error"]["code"] == "ATTACHMENT_NOT_FOUND"
    assert list(tmp_path.iterdir()) == []
