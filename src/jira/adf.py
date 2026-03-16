"""Atlassian Document Format (ADF) conversion utilities."""

from typing import Any

AdfNode = dict[str, Any] | list[Any] | str | int | float | bool | None


def _collect_text(node: AdfNode) -> list[str]:
    """Recursively collect text fragments from an ADF node.

    Args:
        node: An ADF node (dict, list, or scalar).

    Returns:
        List of text fragments in document order.
    """
    if isinstance(node, list):
        fragments: list[str] = []
        for item in node:
            fragments.extend(_collect_text(item))
        return fragments

    if not isinstance(node, dict):
        return []

    node_type = node.get("type")

    if node_type == "text":
        text = node.get("text", "")
        return [text] if text else []

    if node_type == "hardBreak":
        return ["\n"]

    content = node.get("content", [])
    if not isinstance(content, list):
        return []

    fragments = []
    for child in content:
        fragments.extend(_collect_text(child))
    return fragments


def adf_to_text(adf: dict[str, Any] | None) -> str:
    """Convert Atlassian Document Format to plain text.

    Args:
        adf: The ADF document structure.

    Returns:
        Plain text extracted from the ADF.
    """
    if not adf or not isinstance(adf, dict):
        return ""

    return " ".join(_collect_text(adf)).strip()


def _build_paragraph_content(para: str) -> list[dict[str, Any]]:
    """Build ADF paragraph content nodes from a single paragraph string.

    Args:
        para: A paragraph of plain text (may contain single newlines).

    Returns:
        List of ADF text and hardBreak nodes.
    """
    lines = para.split("\n")
    para_content: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        if line:
            para_content.append({"type": "text", "text": line})
        if i < len(lines) - 1:
            para_content.append({"type": "hardBreak"})
    return para_content


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

    content: list[dict[str, Any]] = []
    for para in text.split("\n\n"):
        if not para.strip():
            continue
        para_content = _build_paragraph_content(para)
        if para_content:
            content.append({"type": "paragraph", "content": para_content})

    return {
        "type": "doc",
        "version": 1,
        "content": content,
    }
