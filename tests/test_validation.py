"""Tests for validation utilities."""

import pytest

from simple_jira_mcp.utils.validation import (
    has_disallowed_jql_chars,
    is_bounded_query,
    sanitize_filename,
    validate_attachment_id,
    validate_issue_key,
    validate_limit,
    validate_project_key,
    validate_search_fields,
)


@pytest.mark.parametrize(
    "key,valid",
    [
        ("ONE-123", True),
        ("PROJECT123-9999", True),
        ("ABC-1", True),
        ("one-123", False),
        ("ONE123", False),
        ("ONE-", False),
        ("", False),
        ("ONE - 123", False),
        ("1ONE-123", False),
    ],
    ids=[
        "simple",
        "long-project",
        "single-digit",
        "lowercase",
        "no-dash",
        "no-number",
        "empty",
        "spaces",
        "leading-number",
    ],
)
def test_validate_issue_key(key, valid):
    assert validate_issue_key(key) is valid


@pytest.mark.parametrize(
    "key,valid",
    [
        ("ONE", True),
        ("PROJECT123", True),
        ("one", False),
        ("ONE-TWO", False),
        ("", False),
        ("1ONE", False),
        ("A", False),
    ],
    ids=[
        "simple",
        "with-numbers",
        "lowercase",
        "with-dash",
        "empty",
        "leading-number",
        "single-letter",
    ],
)
def test_validate_project_key(key, valid):
    assert validate_project_key(key) is valid


@pytest.mark.parametrize(
    "attachment_id,valid",
    [("12345", True), ("1", True), ("abc123", False), ("", False), ("-123", False)],
    ids=["numeric", "single-digit", "letters", "empty", "negative"],
)
def test_validate_attachment_id(attachment_id, valid):
    assert validate_attachment_id(attachment_id) is valid


@pytest.mark.parametrize(
    "limit,valid",
    [(1, True), (100, True), (50, True), (0, False), (-1, False), (101, False)],
    ids=["min", "max", "middle", "zero", "negative", "too-large"],
)
def test_validate_limit(limit, valid):
    assert validate_limit(limit) is valid


@pytest.mark.parametrize(
    "jql,bounded",
    [
        ("project = ONE", True),
        ("assignee = currentUser()", True),
        ('updated >= "2025-01-01"', True),
        ('status = "Done"', True),
        (
            'project = ONE AND updated >= "2025-01-01" AND assignee = currentUser()',
            True,
        ),
        ('text ~ "keyword"', False),
        ("", False),
        ("PROJECT = ONE", True),
        ('text ~ "foo" ORDER BY created', False),
        ('text ~ "project status"', False),
        ("project = ONE ORDER BY created DESC", True),
        # Reserved-word keys such as ON must be quoted for Jira's parser;
        # stripping the quoted value must not hide the project clause.
        ('project = "ON"', True),
        # A bounding clause need not scope to a project.
        ('status = "Done" AND updated >= "2025-01-01"', True),
    ],
    ids=[
        "project",
        "assignee",
        "updated",
        "status",
        "complex",
        "text-only",
        "empty",
        "case-insensitive",
        "order-by-only",
        "keyword-in-quotes",
        "with-order-by",
        "quoted-reserved-project",
        "without-project-scope",
    ],
)
def test_is_bounded_query(jql, bounded):
    assert is_bounded_query(jql) is bounded


@pytest.mark.parametrize(
    "jql,disallowed",
    [
        ("project = ONE; delete", True),
        ('project = ONE\ntext ~ "abc"', True),
        ('project = ONE AND text ~ "abc"', False),
    ],
    ids=["semicolon", "newline", "clean"],
)
def test_has_disallowed_jql_chars(jql, disallowed):
    assert has_disallowed_jql_chars(jql) is disallowed


@pytest.mark.parametrize(
    "fields,result",
    [
        (["summary", "status", "labels"], (True, None)),
        (["summary", "hack"], (False, "hack")),
        # key is always returned, so selecting it is not meaningful
        (["key"], (False, "key")),
    ],
    ids=["allowed", "unknown", "key"],
)
def test_validate_search_fields(fields, result):
    assert validate_search_fields(fields) == result


@pytest.mark.parametrize(
    "filename,sanitized",
    [
        ("document.pdf", "document.pdf"),
        ("../../../etc/passwd", "passwd"),
        ("folder/file.txt", "file.txt"),
        ("C:\\Windows\\file.txt", "file.txt"),
        ('file<>:"|?*.txt', "file_______.txt"),
        ("file\x00.txt", "file_.txt"),
        ("", "attachment"),
        ("///", "attachment"),
        (".", "attachment"),
        ("..", "attachment"),
        ("...", "attachment"),
        (".gitignore", ".gitignore"),
    ],
    ids=[
        "normal",
        "parent-traversal",
        "posix-dir",
        "windows-dir",
        "special-chars",
        "null-byte",
        "empty",
        "only-separators",
        "dot",
        "dot-dot",
        "dot-dot-dot",
        "hidden-file",
    ],
)
def test_sanitize_filename(filename, sanitized):
    assert sanitize_filename(filename) == sanitized
