"""Tests for the add-comment request payload, replayed from a recording."""


async def test_add_comment_on_recorded_site(client, replay):
    jira = replay("add_comment")

    result = await client.add_comment("ONE-1", "First line\nSecond line")

    assert jira.requests[0].method == "POST"
    assert jira.requests[0].url.path == "/rest/api/3/issue/ONE-1/comment"
    assert jira.sent(0) == {
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
                }
            ],
        }
    }
    assert result == {"id": "10012", "created": "2026-11-11T12:22:10.760+0200"}
