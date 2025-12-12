"""Tests for ADF conversion utilities."""

from src.jira.adf import adf_to_text, text_to_adf


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
        assert adf_to_text(adf) == "First Second"

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
        result = adf_to_text(adf)
        assert "Line 1" in result
        assert "Line 2" in result

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
        result = adf_to_text(adf)
        assert "Item 1" in result
        assert "Item 2" in result


class TestTextToAdf:
    def test_simple_text(self):
        result = text_to_adf("Hello world")
        assert result["type"] == "doc"
        assert result["version"] == 1
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "paragraph"
        assert result["content"][0]["content"][0]["text"] == "Hello world"

    def test_empty_text(self):
        result = text_to_adf("")
        assert result["type"] == "doc"
        assert result["content"] == []

    def test_multiple_paragraphs(self):
        result = text_to_adf("Para 1\n\nPara 2")
        assert len(result["content"]) == 2
        assert result["content"][0]["content"][0]["text"] == "Para 1"
        assert result["content"][1]["content"][0]["text"] == "Para 2"

    def test_single_newlines_preserved(self):
        result = text_to_adf("Line 1\nLine 2")
        # Should be in same paragraph with hard break
        assert len(result["content"]) == 1
        para_content = result["content"][0]["content"]
        texts = [c.get("text") for c in para_content if c.get("type") == "text"]
        assert "Line 1" in texts
        assert "Line 2" in texts

    def test_roundtrip_simple(self):
        original = "Hello world"
        adf = text_to_adf(original)
        result = adf_to_text(adf)
        assert result == original

    def test_roundtrip_paragraphs(self):
        original = "Para 1\n\nPara 2"
        adf = text_to_adf(original)
        result = adf_to_text(adf)
        assert "Para 1" in result
        assert "Para 2" in result
