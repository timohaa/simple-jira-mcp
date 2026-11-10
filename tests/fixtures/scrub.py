"""Remove site, project and user identities from recorded Jira exchanges."""

import re
from urllib.parse import urlsplit

SITE = "https://example.atlassian.net"
PROJECT = "ONE"
EMAIL = "user@example.com"
DROPPED_KEYS = {"avatarUrls", "emailAddress"}


class Scrubber:
    """Rewrite recorded exchanges so they identify no real site or person."""

    def __init__(self, site_url, email, project_key):
        self._site = site_url.rstrip("/")
        self._host = urlsplit(self._site).netloc
        self._email = email
        self._project = re.compile(rf"\b{re.escape(project_key)}\b")
        self._accounts = {}
        self._names = {}

    def scrub(self, value):
        """Return a scrubbed copy of a JSON-like value."""
        if isinstance(value, dict):
            return self._scrub_object(value)
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        if isinstance(value, str):
            return self._scrub_text(value)
        return value

    def _scrub_object(self, obj):
        result = {}
        for key, value in obj.items():
            if key in DROPPED_KEYS:
                continue
            if key == "accountId" and isinstance(value, str):
                result[key] = self._alias(self._accounts, value, "account-")
            elif key == "displayName" and isinstance(value, str):
                result[key] = self._alias(self._names, value, "User ")
            elif key == "name" and "projectTypeKey" in obj:
                result[key] = "Project One"
            else:
                result[key] = self.scrub(value)
        return result

    @staticmethod
    def _alias(known, value, prefix):
        """Give each distinct value a stable numbered placeholder."""
        return known.setdefault(value, f"{prefix}{len(known) + 1}")

    def _scrub_text(self, text):
        text = text.replace(self._site, SITE).replace(
            self._host, "example.atlassian.net"
        )
        text = text.replace(self._email, EMAIL)
        for account, alias in self._accounts.items():
            text = text.replace(account, alias)
        if text.startswith("https://") and not text.startswith(SITE):
            # A redirect to another host: its path and query carry signed tokens.
            return "https://media.example.net/file"
        return self._project.sub(PROJECT, text)
