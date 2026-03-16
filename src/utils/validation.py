"""Input validation utilities for Jira MCP Server."""

import re

ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+$")
ATTACHMENT_ID_PATTERN = re.compile(r"^\d+$")

MAX_LIMIT = 100
MIN_LIMIT = 1
DISALLOWED_JQL_PATTERN = re.compile(r"[;\r\n]")

ALLOWED_SEARCH_FIELDS = frozenset(
    [
        "summary",
        "status",
        "assignee",
        "priority",
        "updated",
        "created",
        "labels",
        "issuetype",
        "reporter",
        "resolution",
        "description",
        "comment",
        "attachment",
        "project",
        "key",
    ]
)

BOUNDING_KEYWORDS = frozenset(
    [
        "project",
        "assignee",
        "reporter",
        "created",
        "updated",
        "resolved",
        "status",
        "type",
        "issuetype",
        "priority",
        "key",
        "id",
    ]
)


def validate_issue_key(key: str) -> bool:
    """Validate a Jira issue key format.

    Args:
        key: The issue key to validate (e.g., "ONE-123").

    Returns:
        True if valid, False otherwise.
    """
    return bool(ISSUE_KEY_PATTERN.match(key))


def validate_project_key(key: str) -> bool:
    """Validate a Jira project key format.

    Args:
        key: The project key to validate (e.g., "ONE").

    Returns:
        True if valid, False otherwise.
    """
    return bool(PROJECT_KEY_PATTERN.match(key))


def validate_attachment_id(attachment_id: str) -> bool:
    """Validate an attachment ID format.

    Args:
        attachment_id: The attachment ID to validate.

    Returns:
        True if valid (numeric string), False otherwise.
    """
    return bool(ATTACHMENT_ID_PATTERN.match(attachment_id))


def validate_limit(limit: int) -> bool:
    """Validate a pagination limit.

    Args:
        limit: The limit value to validate.

    Returns:
        True if valid (1-100), False otherwise.
    """
    return MIN_LIMIT <= limit <= MAX_LIMIT


def validate_start_at(start_at: int) -> bool:
    """Validate a pagination start_at value.

    Args:
        start_at: The start_at value to validate.

    Returns:
        True if valid (>= 0), False otherwise.
    """
    return start_at >= 0


def is_bounded_query(jql: str) -> bool:
    """Check if a JQL query has at least one bounding filter.

    Jira Cloud API v3 requires bounded queries. This function checks
    if the JQL contains at least one keyword that limits the result set.

    Args:
        jql: The JQL query string.

    Returns:
        True if the query is bounded, False otherwise.
    """
    jql_lower = jql.lower()
    # Match whole words only using word boundaries
    return any(re.search(rf"\b{keyword}\b", jql_lower) for keyword in BOUNDING_KEYWORDS)


def has_disallowed_jql_chars(jql: str) -> bool:
    """Detect disallowed characters in JQL to guard against injection.

    Args:
        jql: The JQL query string.

    Returns:
        True if the query contains disallowed characters, False otherwise.
    """
    return bool(DISALLOWED_JQL_PATTERN.search(jql))


def validate_search_fields(fields: list[str]) -> tuple[bool, str | None]:
    """Validate requested search fields against an allowlist.

    Args:
        fields: List of requested field names.

    Returns:
        Tuple of (is_valid, first_invalid_field).
    """
    for field in fields:
        if not field or field not in ALLOWED_SEARCH_FIELDS:
            return False, field
    return True, None


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent directory traversal attacks.

    Args:
        filename: The original filename.

    Returns:
        A safe filename with dangerous characters removed.
    """
    # Accept both forward and backslash separators before splitting, so
    # paths like "C:\Users\...\file.txt" are handled the same as POSIX paths.
    safe = filename.replace("\\", "/").split("/")[-1]
    safe = re.sub(r'[:\x00<>"|?*]', "_", safe)
    return safe.strip() or "attachment"
