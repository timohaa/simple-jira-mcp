"""Jira Agile (board and sprint) operations."""

from typing import Any

from simple_jira_mcp.jira.base import (
    AGILE_BASE,
    HTTP_NO_CONTENT,
    JiraClientBase,
)
from simple_jira_mcp.utils.errors import (
    BOARD_NOT_FOUND,
    SPRINT_NOT_FOUND,
    VALIDATION_ERROR,
    ErrorResponse,
    is_error,
)

BOARD_PATH = f"{AGILE_BASE}/board"
SPRINT_PATH = f"{AGILE_BASE}/sprint"
PAGE_SIZE = 50
# Jira rejects a sprint move request with more issues than this.
MAX_ISSUES_PER_MOVE = 50


class AgileOperation(JiraClientBase):
    """Handle board lookups, sprint listing, and moving issues into sprints."""

    async def list_sprints(
        self,
        *,
        project_key: str | None,
        board_id: int | None,
        states: list[str],
    ) -> dict[str, Any] | ErrorResponse:
        """List sprints of one board or of every board in a project."""
        if board_id is not None:
            boards = [{"id": board_id, "name": None}]
        else:
            found = await self._paged(
                f"{self.base_url}{BOARD_PATH}",
                {"projectKeyOrId": str(project_key)},
                BOARD_NOT_FOUND,
            )
            if is_error(found):
                return found
            boards = found["values"]

        sprints: list[dict[str, Any]] = []
        for board in boards:
            board_sprints = await self._board_sprints(board, states)
            if is_error(board_sprints):
                # Boards without sprint support (kanban) are skipped when they
                # were discovered through the project.
                if board_id is None and board_sprints["error"]["code"] == (
                    VALIDATION_ERROR
                ):
                    continue
                return board_sprints
            sprints.extend(board_sprints["values"])
        return {"sprints": sprints}

    async def _board_sprints(
        self, board: dict[str, Any], states: list[str]
    ) -> dict[str, Any] | ErrorResponse:
        """Fetch all sprints of a board in compact form."""
        data = await self._paged(
            f"{self.base_url}{BOARD_PATH}/{board['id']}/sprint",
            {"state": ",".join(states)},
            BOARD_NOT_FOUND,
        )
        if is_error(data):
            return data
        return {
            "values": [
                {
                    "id": sprint.get("id"),
                    "name": sprint.get("name"),
                    "state": sprint.get("state"),
                    "startDate": sprint.get("startDate"),
                    "endDate": sprint.get("endDate"),
                    "boardId": board["id"],
                    "boardName": board.get("name"),
                }
                for sprint in data["values"]
            ]
        }

    async def _paged(
        self, url: str, params: dict[str, str], not_found: str
    ) -> dict[str, Any] | ErrorResponse:
        """Collect the values of every page of an Agile list endpoint."""
        values: list[dict[str, Any]] = []
        start_at = 0
        while True:
            page = await self._request(
                "GET",
                url,
                params={
                    **params,
                    "startAt": str(start_at),
                    "maxResults": str(PAGE_SIZE),
                },
                not_found=(not_found, "Board not found"),
            )
            if is_error(page):
                return page
            batch = page.get("values", [])
            values.extend(batch)
            if page.get("isLast", True) or not batch:
                return {"values": values}
            start_at += len(batch)

    async def move_issues_to_sprint(
        self, sprint_id: int, issue_keys: list[str]
    ) -> dict[str, Any] | ErrorResponse:
        """Move issues into a sprint, sending at most 50 per request."""
        moved: list[str] = []
        for start in range(0, len(issue_keys), MAX_ISSUES_PER_MOVE):
            batch = issue_keys[start : start + MAX_ISSUES_PER_MOVE]
            result = await self._request(
                "POST",
                f"{self.base_url}{SPRINT_PATH}/{sprint_id}/issue",
                payload={"issues": batch},
                success_status=HTTP_NO_CONTENT,
                not_found=(SPRINT_NOT_FOUND, f"Sprint {sprint_id} not found"),
            )
            if is_error(result):
                if moved:
                    result["error"]["message"] += (
                        f" Already moved before the failure: {', '.join(moved)}."
                    )
                return result
            moved.extend(batch)
        return {"sprint_id": sprint_id, "moved": moved}
