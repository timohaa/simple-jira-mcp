"""Jira issue transitions and comment operations."""

from typing import Any

from simple_jira_mcp.jira.adf import text_to_adf
from simple_jira_mcp.jira.base import (
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    ISSUE_PATH,
    JiraClientBase,
)
from simple_jira_mcp.utils.errors import (
    VALIDATION_ERROR,
    ErrorResponse,
    error_response,
    is_error,
)


class WorkflowOperation(JiraClientBase):
    """Handle issue workflow changes and comments."""

    async def get_transitions(self, issue_key: str) -> dict[str, Any] | ErrorResponse:
        """Return available transitions and their screen field metadata."""
        data = await self._request(
            "GET",
            f"{self.base_url}{ISSUE_PATH}/{issue_key}/transitions",
            params={"expand": "transitions.fields"},
        )
        if is_error(data):
            return data
        return {
            "transitions": [
                {
                    "id": str(item.get("id", "")),
                    "name": item.get("name") or "",
                    "status": self._extract_name(item.get("to")),
                    "fields": item.get("fields", {}),
                }
                for item in data.get("transitions", [])
            ]
        }

    async def transition_issue(
        self,
        issue_key: str,
        transition: str,
        *,
        comment: str | None = None,
        resolution: str | None = None,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any] | ErrorResponse:
        """Transition an issue and read its resulting status and resolution."""
        data = await self.get_transitions(issue_key)
        if is_error(data):
            return data
        selected = self._resolve_transition(transition, data["transitions"])
        if is_error(selected):
            return selected
        # Jira silently drops update.comment when the transition screen has no
        # comment field, so such a comment is posted separately afterwards.
        inline = "comment" in selected["fields"]
        payload = self._build_payload(
            selected, comment if inline else None, resolution, fields
        )
        if is_error(payload):
            return payload

        result = await self._request(
            "POST",
            f"{self.base_url}{ISSUE_PATH}/{issue_key}/transitions",
            payload=payload,
            success_status=HTTP_NO_CONTENT,
        )
        if is_error(result):
            return result

        return await self._after_transition(issue_key, None if inline else comment)

    async def _after_transition(
        self, issue_key: str, comment: str | None
    ) -> dict[str, Any] | ErrorResponse:
        """Post a comment the transition could not carry, then read the issue."""
        if comment is not None:
            posted = await self.add_comment(issue_key, comment)
            if is_error(posted):
                posted["error"]["message"] = (
                    "Transition succeeded, but adding the comment failed: "
                    + posted["error"]["message"]
                )
                return posted

        result = await self._request(
            "GET",
            f"{self.base_url}{ISSUE_PATH}/{issue_key}",
            params={"fields": "status,resolution,resolutiondate"},
        )
        if is_error(result):
            result["error"]["message"] = (
                "Transition succeeded, but reading the updated issue failed: "
                + result["error"]["message"]
            )
            return result
        updated = result.get("fields", {})
        return {
            "key": issue_key,
            "status": self._extract_name(updated.get("status")),
            "resolution": self._extract_name(updated.get("resolution")),
            "resolutiondate": updated.get("resolutiondate"),
        }

    async def add_comment(
        self, issue_key: str, body: str
    ) -> dict[str, Any] | ErrorResponse:
        """Post a plain-text comment as ADF."""
        data = await self._request(
            "POST",
            f"{self.base_url}{ISSUE_PATH}/{issue_key}/comment",
            payload={"body": text_to_adf(body)},
            success_status=HTTP_CREATED,
        )
        if is_error(data):
            return data
        return {"id": data.get("id"), "created": data.get("created")}

    @staticmethod
    def _resolve_transition(
        transition: str, transitions: list[dict[str, Any]]
    ) -> dict[str, Any] | ErrorResponse:
        """Select an exact ID or a unique case-insensitive name/status match."""
        transition = transition.strip()
        for item in transitions:
            if item["id"] == transition:
                return item
        matches = [
            item
            for item in transitions
            if transition.casefold()
            in (item["name"].casefold(), (item["status"] or "").casefold())
        ]
        if len(matches) == 1:
            return matches[0]
        options = "; ".join(
            f"{item['id']}: {item['name']} -> {item['status']}" for item in transitions
        )
        reason = "is ambiguous" if matches else "was not found"
        return error_response(
            VALIDATION_ERROR,
            f"Transition '{transition}' {reason}. "
            f"Valid options: {options or 'none'}. Use a transition ID to disambiguate.",
        )

    @staticmethod
    def _build_payload(
        selected: dict[str, Any],
        comment: str | None,
        resolution: str | None,
        fields: dict[str, Any] | None,
    ) -> dict[str, Any] | ErrorResponse:
        """Validate screen fields before building a transition payload."""
        values = dict(fields or {})
        if "resolutiondate" in values:
            return error_response(
                VALIDATION_ERROR,
                "Jira sets resolutiondate automatically; it cannot be edited via API. "
                "Record the actual completion date in the comment.",
            )
        if resolution is not None:
            if "resolution" in values:
                return error_response(
                    VALIDATION_ERROR, "Specify resolution either directly or in fields"
                )
            values["resolution"] = {"name": resolution.strip()}
        screen_fields = selected["fields"]
        settable = {
            key
            for key, metadata in screen_fields.items()
            if "set" in metadata.get("operations", ["set"])
        }
        unsupported = [key for key in values if key not in settable]
        if unsupported:
            return error_response(
                VALIDATION_ERROR,
                f"Transition '{selected['name']}' does not accept fields: "
                f"{', '.join(unsupported)}. "
                f"Settable fields: {', '.join(sorted(settable)) or 'none'}",
            )
        payload: dict[str, Any] = {"transition": {"id": selected["id"]}}
        if values:
            payload["fields"] = values
        if comment is not None:
            payload["update"] = {"comment": [{"add": {"body": text_to_adf(comment)}}]}
        return payload
