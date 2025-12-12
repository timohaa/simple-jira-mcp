"""Atlassian Document Format (ADF) conversion utilities."""

from typing import Any

# Type alias for ADF nodes (can be dict, list, or primitive)
AdfNode = dict[str, Any] | list[Any] | str | int | float | bool | None


def adf_to_text(adf: dict[str, Any] | None) -> str:
    """Convert Atlassian Document Format to plain text.

    Args:
        adf: The ADF document structure.

    Returns:
        Plain text extracted from the ADF.
    """
    if not adf or not isinstance(adf, dict):
        return ""

    texts: list[str] = []

    def walk(node: AdfNode) -> None:
        """Recursively walk the ADF tree and extract text."""
        if isinstance(node, dict):
            node_type = node.get("type")

            # Extract text content
            if node_type == "text":
                text = node.get("text", "")
                if text:
                    texts.append(text)

            # Handle hard breaks as newlines
            elif node_type == "hardBreak":
                texts.append("\n")

            # Recurse into content
            content = node.get("content", [])
            if isinstance(content, list):
                for child in content:
                    walk(child)

        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(adf)
    return " ".join(texts).strip()


def text_to_adf(text: str) -> dict[str, Any]:
    """Convert plain text to Atlassian Document Format.

    Args:
        text: Plain text to convert.

    Returns:
        ADF document structure.
    """
    if not text:
        return {
            "type": "doc",
            "version": 1,
            "content": [],
        }

    # Split text into paragraphs
    paragraphs = text.split("\n\n")
    content: list[dict[str, Any]] = []

    for para in paragraphs:
        if para.strip():
            # Handle single newlines within paragraphs
            lines = para.split("\n")
            para_content: list[dict[str, Any]] = []

            for i, line in enumerate(lines):
                if line:
                    para_content.append({"type": "text", "text": line})
                if i < len(lines) - 1:
                    para_content.append({"type": "hardBreak"})

            if para_content:
                content.append({"type": "paragraph", "content": para_content})

    return {
        "type": "doc",
        "version": 1,
        "content": content,
    }
