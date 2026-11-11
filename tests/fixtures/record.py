"""Record real Jira responses as replay fixtures.

Run against a sandbox project only, with the account language set to
English. The script creates three issues labelled
`mcp-fixture` in that project, runs every client operation against them, and
deletes them again. It touches no other issue.

    JIRA_CONFIG_JSON='[...]' ./venv/bin/python -m tests.fixtures.record \
        --project SBX [--config-id work]

Each scenario is written to `tests/fixtures/<scenario>.json` as the ordered
list of HTTP exchanges the client made. Review every file before committing:
scrubbing replaces the site, project key and user identities, but board,
sprint, status and priority names are kept as recorded.
"""

import argparse
import asyncio
import json
import logging
import tempfile
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import partial
from pathlib import Path

import httpx

from simple_jira_mcp.config import get_config, load_configs
from simple_jira_mcp.jira import base
from simple_jira_mcp.jira.client import (
    CreateIssueParams,
    JiraClient,
    UpdateIssueParams,
)
from simple_jira_mcp.utils.errors import is_error
from tests.fixtures.scrub import Scrubber

logger = logging.getLogger("record")

FIXTURES = Path(__file__).parent
LABEL = "mcp-fixture"
SEARCH_ATTEMPTS = 15
SEARCH_WAIT_SECONDS = 2
ALL_FIELDS = [
    "summary",
    "description",
    "reporter",
    "resolution",
    "project",
    "comment",
    "attachment",
]


class Recorder(httpx.AsyncBaseTransport):
    """Send requests to the real site and keep each exchange."""

    def __init__(self):
        self.inner = httpx.AsyncHTTPTransport()
        self.exchanges = []

    async def handle_async_request(self, request):
        # A multipart upload is a stream; read it so the body can be kept.
        await request.aread()
        response = await self.inner.handle_async_request(request)
        body = await response.aread()
        await response.aclose()
        kept = {"content-type", "location"}
        headers = {k: v for k, v in response.headers.items() if k in kept}
        self.exchanges.append(
            {
                "request": {
                    "method": request.method,
                    "url": str(request.url),
                    "body": _decode(request.content),
                },
                "response": {
                    "status": response.status_code,
                    "headers": headers,
                    "body": _decode(body),
                },
            }
        )
        return httpx.Response(
            response.status_code, headers=headers, content=body, request=request
        )


def _decode(content):
    """Return a body as parsed JSON when possible, else as text."""
    if not content:
        return None
    try:
        return json.loads(content)
    except ValueError:
        return content.decode("utf-8", errors="replace")


class Session:
    """A Jira client whose HTTP exchanges are written out per scenario."""

    def __init__(self, config, project):
        self.config = config
        self.project = project
        self.recorder = Recorder()
        self.scrubber = Scrubber(config.url, config.email, project)
        httpx_client = partial(httpx.AsyncClient, transport=self.recorder)
        # Route the client under test through the recording transport.
        base.httpx.AsyncClient = httpx_client
        self.client = JiraClient(config)

    @asynccontextmanager
    async def scenario(self, name):
        """Write the exchanges made inside the block to `<name>.json`."""
        self.recorder.exchanges = []
        yield
        path = FIXTURES / f"{name}.json"
        scrubbed = self.scrubber.scrub(self.recorder.exchanges)
        path.write_text(json.dumps(scrubbed, indent=2, sort_keys=True) + "\n")
        logger.info("wrote %s (%d exchanges)", path.name, len(scrubbed))

    async def create(self, summary, **kwargs):
        """Create a labelled issue and return its key."""
        params = CreateIssueParams(
            project_key=self.project, summary=summary, labels=[LABEL], **kwargs
        )
        result = await self.client.create_issue(params)
        if is_error(result):
            raise SystemExit(f"Cannot create issue: {result['error']}")
        return result["key"]


async def record_issue_scenarios(session, keys):
    client, project = session.client, session.project
    async with session.scenario("create_issue"):
        keys.append(
            await session.create(
                "Recorded issue", issue_type="Task", description="Line 1\nLine 2"
            )
        )
    key = keys[0]
    keys.append(await session.create("Second recorded issue"))
    keys.append(await session.create("Issue to delete"))

    for name, params in [
        ("create_invalid_priority", {"priority": "NoSuchPriority"}),
        ("create_invalid_issue_type", {"issue_type": "NoSuchType"}),
    ]:
        async with session.scenario(name):
            await client.create_issue(
                CreateIssueParams(project_key=project, summary="Rejected", **params)
            )
    # In the sandbox only Task has the priority field; Bug does not.
    async with session.scenario("create_invalid_priority_type_without_priority"):
        await client.create_issue(
            CreateIssueParams(
                project_key=project,
                summary="Rejected",
                issue_type="Bug",
                priority="NoSuchPriority",
            )
        )
    async with session.scenario("create_project_not_found"):
        await client.create_issue(
            CreateIssueParams(project_key="ZZNOPROJECT", summary="Rejected")
        )

    async with session.scenario("update_issue"):
        await client.update_issue(
            key, UpdateIssueParams(summary="Recorded issue, updated", labels=[LABEL])
        )
    async with session.scenario("update_invalid_priority"):
        await client.update_issue(key, UpdateIssueParams(priority="NoSuchPriority"))
    async with session.scenario("add_comment"):
        await client.add_comment(key, "First line\nSecond line")
    async with session.scenario("get_transitions"):
        transitions = await client.get_transitions(key)
    if is_error(transitions) or not transitions["transitions"]:
        raise SystemExit("The sandbox issue has no transitions to record")
    names = [transition["name"] for transition in transitions["transitions"]]
    async with session.scenario("transition_issue"):
        await client.transition_issue(key, names[0])
    async with session.scenario("transition_with_comment"):
        await client.transition_issue(key, names[-1], comment="Moved by recorder")
    async with session.scenario("transition_not_found"):
        await client.transition_issue(key, "No such transition")


async def record_read_scenarios(session, keys):
    client, project = session.client, session.project
    key = keys[0]
    attachment_id = await upload_attachment(session, key)
    async with session.scenario("get_issue"):
        await client.get_issue(key)
    async with session.scenario("get_issue_not_found"):
        await client.get_issue(f"{project}-99999999")
    with tempfile.TemporaryDirectory() as tmpdir:
        async with session.scenario("download_attachment"):
            await client.download_attachment(
                attachment_id, Path(tmpdir), key, "notes.txt"
            )
        async with session.scenario("download_attachment_not_found"):
            await client.download_attachment("99999999", Path(tmpdir), key, "notes.txt")

    async with session.scenario("list_sprints"):
        sprints = await client.list_sprints(
            project_key=project, board_id=None, states=["active", "future"]
        )
    if not is_error(sprints) and sprints["sprints"]:
        async with session.scenario("move_issues_to_sprint"):
            await client.move_issues_to_sprint(sprints["sprints"][0]["id"], [key])
    else:
        logger.warning("no active or future sprint: move_issues_to_sprint not recorded")
    async with session.scenario("move_issues_sprint_not_found"):
        await client.move_issues_to_sprint(99999999, [key])

    async with session.scenario("auth_failed"):
        bad = JiraClient(replace(session.config, token="invalid-token"))
        await bad.get_issue(key)
        await bad.aclose()


async def upload_attachment(session, key):
    """Attach a small text file (the server has no upload tool) and return its ID."""
    response = await session.client._session.client.post(
        f"{session.config.url}/rest/api/3/issue/{key}/attachments",
        headers={"X-Atlassian-Token": "no-check"},
        files={"file": ("notes.txt", b"recorded attachment\n", "text/plain")},
    )
    response.raise_for_status()
    return response.json()[0]["id"]


async def record_search_scenarios(session, keys):
    client = session.client
    jql = f'project = "{session.project}" AND labels = {LABEL} ORDER BY key ASC'
    # Jira indexes new issues asynchronously; wait until both are searchable.
    for _ in range(SEARCH_ATTEMPTS):
        async with session.scenario("search"):
            found = await client.search(jql)
        if not is_error(found) and len(found["issues"]) >= len(keys):
            break
        await asyncio.sleep(SEARCH_WAIT_SECONDS)
    else:
        raise SystemExit("Created issues never appeared in search")

    async with session.scenario("search_all_fields"):
        await client.search(jql, fields=ALL_FIELDS)
    async with session.scenario("search_two_pages"):
        first = await client.search(jql, max_results=1)
        await client.search(
            jql, max_results=1, next_page_token=first["next_page_token"]
        )
    async with session.scenario("search_invalid_jql"):
        await client.search(f'project = "{session.project}" AND (')


async def record(config, project):
    session = Session(config, project)
    keys = []
    try:
        await record_issue_scenarios(session, keys)
        await record_read_scenarios(session, keys)
        await record_search_scenarios(session, keys)
        async with session.scenario("delete_issue"):
            await session.client.delete_issue(keys.pop())
        async with session.scenario("delete_issue_not_found"):
            await session.client.delete_issue(f"{project}-99999999")
    finally:
        for key in keys:
            result = await session.client.delete_issue(key)
            if is_error(result):
                logger.error("could not delete %s: %s", key, result["error"])
        await session.client.aclose()
    logger.info("done; review tests/fixtures/*.json before committing")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--project", required=True, help="sandbox project key")
    parser.add_argument("--config-id", help="config to use (default: the first)")
    args = parser.parse_args()

    load_configs()
    config = get_config(args.config_id)
    if config is None:
        raise SystemExit(f"Unknown config: {args.config_id}")
    asyncio.run(record(config, args.project.upper()))


if __name__ == "__main__":
    main()
