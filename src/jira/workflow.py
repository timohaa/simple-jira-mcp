"""Jira issue transitions and comment operations."""

import logging
from typing import Any

import httpx

from src.jira.adf import text_to_adf
from src.jira.base import (
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    ISSUE_PATH,
    JiraClientBase,
)
from src.utils.errors import (
    AUTH_FAILED,
    ISSUE_NOT_FOUND,
    JIRA_ERROR,
    RATE_LIMITED,
    VALIDATION_ERROR,
    ErrorResponse,
    error_response,
)

logger = logging.getLogger(__name__)


class WorkflowOperation(JiraClientBase):
    """Handle issue workflow changes and comments."""

    async def get_transitions(self, issue_key: str) -> dict[str, Any] | ErrorResponse:
        """Return available transitions and their screen field metadata."""
        data = await self._request(
            "GET",
            f"{self.base_url}{ISSUE_PATH}/{issue_key}/transitions",
            params={"expand": "transitions.fields"},
        )
        if data.get("isError"):
            return data
        return {
            "transitions": [
                {
                    "id": str(item["id"]),
                    "name": item["name"],
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
        if data.get("isError"):
            return data
        selected = self._resolve_transition(transition, data["transitions"])
        if selected.get("isError"):
            return selected
        payload = self._build_payload(selected, comment, resolution, fields)
        if payload.get("isError"):
            return payload

        url = f"{self.base_url}{ISSUE_PATH}/{issue_key}"
        result = await self._request(
            "POST",
            f"{url}/transitions",
            payload=payload,
            success_status=HTTP_NO_CONTENT,
        )
        if result.get("isError"):
            return result

        result = await self._request(
            "GET", url, params={"fields": "status,resolution,resolutiondate"}
        )
        if result.get("isError"):
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
            "resolutiondate": self._format_date(updated.get("resolutiondate")),
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
        if data.get("isError"):
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

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        success_status: int = HTTP_OK,
    ) -> dict[str, Any] | ErrorResponse:
        """Send a workflow request with the existing auth and error conventions."""
        try:
            async with self._create_client() as client:
                response = await client.request(
                    method, url, params=params, json=payload, auth=self._get_auth()
                )
        except httpx.RequestError as e:
            logger.exception("Request failed for issue workflow")
            return error_response(JIRA_ERROR, f"Request failed: {e}")

        status_errors = {
            HTTP_UNAUTHORIZED: (AUTH_FAILED, "Invalid credentials"),
            HTTP_NOT_FOUND: (ISSUE_NOT_FOUND, "Issue not found"),
            HTTP_TOO_MANY_REQUESTS: (RATE_LIMITED, "Too many requests to Jira API"),
        }
        if response.status_code in status_errors:
            code, message = status_errors[response.status_code]
            return error_response(code, message)
        if response.status_code == success_status:
            if success_status == HTTP_NO_CONTENT:
                return {}
            try:
                data = response.json()
                if isinstance(data, dict):
                    return data
            except ValueError:
                pass
            return error_response(JIRA_ERROR, "Invalid JSON response from Jira API")

        message = f"Jira API error: {response.status_code}"
        try:
            data = response.json()
            errors = data.get("errors", {})
            messages = data.get("errorMessages", [])
            if errors:
                message = ", ".join(f"{key}: {value}" for key, value in errors.items())
            elif messages:
                message = str(messages[0])
        except (ValueError, AttributeError, TypeError):
            pass
        code = (
            VALIDATION_ERROR if response.status_code == HTTP_BAD_REQUEST else JIRA_ERROR
        )
        return error_response(code, message)
