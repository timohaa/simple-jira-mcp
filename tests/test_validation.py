"""Tests for validation utilities."""

from src.utils.validation import (
    has_disallowed_jql_chars,
    is_bounded_query,
    sanitize_filename,
    validate_attachment_id,
    validate_issue_key,
    validate_limit,
    validate_project_key,
    validate_search_fields,
    validate_start_at,
)


class TestValidateIssueKey:
    def test_valid_simple(self):
        assert validate_issue_key("ONE-123") is True

    def test_valid_long_project(self):
        assert validate_issue_key("PROJECT123-9999") is True

    def test_valid_single_digit(self):
        assert validate_issue_key("ABC-1") is True

    def test_invalid_lowercase(self):
        assert validate_issue_key("one-123") is False

    def test_invalid_no_dash(self):
        assert validate_issue_key("ONE123") is False

    def test_invalid_no_number(self):
        assert validate_issue_key("ONE-") is False

    def test_invalid_empty(self):
        assert validate_issue_key("") is False

    def test_invalid_spaces(self):
        assert validate_issue_key("ONE - 123") is False

    def test_invalid_leading_number(self):
        assert validate_issue_key("1ONE-123") is False


class TestValidateProjectKey:
    def test_valid_simple(self):
        assert validate_project_key("ONE") is True

    def test_valid_with_numbers(self):
        assert validate_project_key("PROJECT123") is True

    def test_invalid_lowercase(self):
        assert validate_project_key("one") is False

    def test_invalid_with_dash(self):
        assert validate_project_key("ONE-TWO") is False

    def test_invalid_empty(self):
        assert validate_project_key("") is False

    def test_invalid_leading_number(self):
        assert validate_project_key("1ONE") is False

    def test_invalid_single_letter(self):
        assert validate_project_key("A") is False


class TestValidateAttachmentId:
    def test_valid_numeric(self):
        assert validate_attachment_id("12345") is True

    def test_valid_single_digit(self):
        assert validate_attachment_id("1") is True

    def test_invalid_with_letters(self):
        assert validate_attachment_id("abc123") is False

    def test_invalid_empty(self):
        assert validate_attachment_id("") is False

    def test_invalid_negative(self):
        assert validate_attachment_id("-123") is False


class TestValidateLimit:
    def test_valid_min(self):
        assert validate_limit(1) is True

    def test_valid_max(self):
        assert validate_limit(100) is True

    def test_valid_middle(self):
        assert validate_limit(50) is True

    def test_invalid_zero(self):
        assert validate_limit(0) is False

    def test_invalid_negative(self):
        assert validate_limit(-1) is False

    def test_invalid_too_large(self):
        assert validate_limit(101) is False


class TestValidateStartAt:
    def test_valid_zero(self):
        assert validate_start_at(0) is True

    def test_valid_positive(self):
        assert validate_start_at(100) is True

    def test_invalid_negative(self):
        assert validate_start_at(-1) is False


class TestIsBoundedQuery:
    def test_bounded_with_project(self):
        assert is_bounded_query("project = ONE") is True

    def test_bounded_with_assignee(self):
        assert is_bounded_query("assignee = currentUser()") is True

    def test_bounded_with_updated(self):
        assert is_bounded_query('updated >= "2025-01-01"') is True

    def test_bounded_with_status(self):
        assert is_bounded_query('status = "Done"') is True

    def test_bounded_complex(self):
        jql = 'project = ONE AND updated >= "2025-01-01" AND assignee = currentUser()'
        assert is_bounded_query(jql) is True

    def test_unbounded_text_only(self):
        assert is_bounded_query('text ~ "keyword"') is False

    def test_unbounded_empty(self):
        assert is_bounded_query("") is False

    def test_case_insensitive(self):
        assert is_bounded_query("PROJECT = ONE") is True


class TestJqlSafety:
    def test_disallows_semicolon(self):
        assert has_disallowed_jql_chars("project = ONE; delete") is True

    def test_disallows_newline(self):
        assert has_disallowed_jql_chars('project = ONE\ntext ~ "abc"') is True

    def test_allows_clean_query(self):
        assert has_disallowed_jql_chars('project = ONE AND text ~ "abc"') is False


class TestValidateSearchFields:
    def test_allows_allowed_fields(self):
        valid, invalid = validate_search_fields(["summary", "status", "labels"])
        assert valid is True
        assert invalid is None

    def test_rejects_unknown_field(self):
        valid, invalid = validate_search_fields(["summary", "hack"])
        assert valid is False
        assert invalid == "hack"


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_removes_path_separators(self):
        assert sanitize_filename("../../../etc/passwd") == "passwd"
        assert sanitize_filename("folder/file.txt") == "file.txt"
        assert sanitize_filename("C:\\Windows\\file.txt") == "file.txt"

    def test_removes_special_chars(self):
        assert sanitize_filename('file<>:"|?*.txt') == "file_______.txt"

    def test_handles_null_bytes(self):
        assert sanitize_filename("file\x00.txt") == "file_.txt"

    def test_empty_returns_attachment(self):
        assert sanitize_filename("") == "attachment"

    def test_only_special_chars(self):
        assert sanitize_filename("///") == "attachment"
