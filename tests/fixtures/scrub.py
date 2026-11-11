"""Remove site, project and user identities from recorded Jira exchanges."""

import re
from urllib.parse import quote, urlsplit

SITE = "https://example.atlassian.net"
PROJECT = "ONE"
EMAIL = "user@example.com"
DROPPED_KEYS = {"avatarUrls", "emailAddress", "timeZone"}
PROJECT_NAME_KEYS = {"projectName"}


class Scrubber:
    """Rewrite recorded exchanges so they identify no real site or person.

    One instance serves a whole recording run, so an account, a display name
    or an issue key gets the same placeholder in every fixture.
    """

    def __init__(self, site_url, email, project_key):
        self._site = site_url.rstrip("/")
        self._host = urlsplit(self._site).netloc
        self._email = email
        self._project = re.compile(rf"\b{re.escape(project_key)}\b")
        self._issue_key = re.compile(rf"\b{re.escape(project_key)}-(\d+)\b")
        self._accounts = {}
        self._names = {}
        self._issues = {}

    def scrub(self, value):
        """Return a scrubbed copy of a JSON-like value."""
        self._collect_accounts(value)
        return self._scrub(value)

    def _collect_accounts(self, value):
        """Register every account ID first; URLs may mention one before its object."""
        if isinstance(value, dict):
            account = value.get("accountId")
            if isinstance(account, str):
                self._alias(self._accounts, account, "account-")
            for item in value.values():
                self._collect_accounts(item)
        elif isinstance(value, list):
            for item in value:
                self._collect_accounts(item)

    def _scrub(self, value):
        if isinstance(value, dict):
            return self._scrub_object(value)
        if isinstance(value, list):
            return [self._scrub(item) for item in value]
        if isinstance(value, str):
            return self._scrub_text(value)
        return value

    def _scrub_object(self, obj):
        result = {}
        for key, value in obj.items():
            if key in DROPPED_KEYS:
                continue
            if key == "displayName" and isinstance(value, str):
                result[key] = self._alias(self._names, value, "User ")
            elif key in PROJECT_NAME_KEYS or (
                key == "name" and "projectTypeKey" in obj
            ):
                result[key] = "Project One"
            else:
                result[key] = self._scrub(value)
        return result

    @staticmethod
    def _alias(known, value, prefix):
        """Give each distinct value a stable numbered placeholder."""
        return known.setdefault(value, f"{prefix}{len(known) + 1}")

    def _issue_alias(self, match):
        """Number issues in order of first appearance; keep made-up large numbers."""
        number = match.group(1)
        if len(number) > 6:
            return f"{PROJECT}-{number}"
        return self._alias(self._issues, number, f"{PROJECT}-")

    def _scrub_text(self, text):
        text = text.replace(self._site, SITE).replace(
            self._host, "example.atlassian.net"
        )
        text = text.replace(self._email, EMAIL)
        for account, alias in self._accounts.items():
            text = text.replace(account, alias).replace(quote(account, safe=""), alias)
        if text.startswith("https://") and not text.startswith(SITE):
            # A redirect to another host: its path and query carry signed tokens.
            return "https://media.example.net/file"
        return self._project.sub(PROJECT, self._issue_key.sub(self._issue_alias, text))
