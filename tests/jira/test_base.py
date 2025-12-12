"""Tests for JiraClientBase helper methods."""

from src.jira.base import JiraClientBase


def test_extract_name_with_none():
    """Test _extract_name returns None for None input."""
    assert JiraClientBase._extract_name(None) is None


def test_extract_name_with_non_dict():
    """Test _extract_name returns None for non-dict input."""
    assert JiraClientBase._extract_name("string") is None  # type: ignore[arg-type]


def test_extract_name_with_dict():
    """Test _extract_name extracts name from dict."""
    assert JiraClientBase._extract_name({"name": "Test"}) == "Test"


def test_extract_display_name_with_none():
    """Test _extract_display_name returns None for None input."""
    assert JiraClientBase._extract_display_name(None) is None


def test_extract_display_name_with_non_dict():
    """Test _extract_display_name returns None for non-dict input."""
    assert JiraClientBase._extract_display_name("string") is None  # type: ignore[arg-type]


def test_extract_display_name_with_dict():
    """Test _extract_display_name extracts displayName from dict."""
    assert JiraClientBase._extract_display_name({"displayName": "User"}) == "User"


def test_format_date_with_none():
    """Test _format_date returns None for None input."""
    assert JiraClientBase._format_date(None) is None


def test_format_date_with_value():
    """Test _format_date passes through date values."""
    assert JiraClientBase._format_date("2025-01-01") == "2025-01-01"
