"""Tests for ADF conversion utilities."""

import pytest

from simple_jira_mcp.jira.adf import adf_to_text, text_to_adf


class TestAdfToText:
    def test_simple_paragraph(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                }
            ],
        }
        assert adf_to_text(adf) == "Hello world"

    def test_multiple_paragraphs(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "First"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second"}],
                },
            ],
        }
        assert adf_to_text(adf) == "First\n\nSecond"

    def test_marks_do_not_split_words(self):
        # Bold mid-word splits the text into adjacent nodes; no spaces
        # may be inserted at the seams.
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "he"},
                        {"type": "text", "text": "ll", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": "o"},
                    ],
                }
            ],
        }
        assert adf_to_text(adf) == "hello"

    def test_with_hard_break(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Line 1"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "Line 2"},
                    ],
                }
            ],
        }
        assert adf_to_text(adf) == "Line 1\nLine 2"

    def test_empty_adf(self):
        assert adf_to_text({}) == ""
        assert adf_to_text(None) == ""

    def test_empty_content(self):
        adf = {"type": "doc", "version": 1, "content": []}
        assert adf_to_text(adf) == ""

    def test_nested_content(self):
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 1"}],
                                }
                            ],
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 2"}],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        assert adf_to_text(adf) == "Item 1\n\nItem 2"


def _doc(*paragraphs):
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": list(p)} for p in paragraphs],
    }


def _text(value):
    return {"type": "text", "text": value}


BREAK = {"type": "hardBreak"}


class TestTextToAdf:
    @pytest.mark.parametrize(
        "text,adf",
        [
            ("Hello world", _doc([_text("Hello world")])),
            ("", {"type": "doc", "version": 1, "content": []}),
            ("Para 1\n\nPara 2", _doc([_text("Para 1")], [_text("Para 2")])),
            ("Line 1\nLine 2", _doc([_text("Line 1"), BREAK, _text("Line 2")])),
            (
                "First line\nSecond line\n\nAnother paragraph",
                _doc(
                    [_text("First line"), BREAK, _text("Second line")],
                    [_text("Another paragraph")],
                ),
            ),
        ],
        ids=["simple", "empty", "paragraphs", "hard-break", "break-and-paragraph"],
    )
    def test_builds_document(self, text, adf):
        assert text_to_adf(text) == adf

    @pytest.mark.parametrize(
        "original",
        ["Hello world", "Para 1\n\nPara 2", "Line 1\nLine 2"],
        ids=["simple", "paragraphs", "hard-break"],
    )
    def test_roundtrip(self, original):
        assert adf_to_text(text_to_adf(original)) == original
