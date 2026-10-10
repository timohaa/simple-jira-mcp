"""Atlassian Document Format (ADF) conversion utilities."""

from typing import Any

AdfNode = dict[str, Any] | list[Any] | str | int | float | bool | None

# Block nodes whose content is purely inline; each yields one text block.
LEAF_BLOCK_TYPES = frozenset({"paragraph", "heading", "codeBlock"})


def _inline_text(node: AdfNode) -> str:
    """Extract inline text from an ADF node.

    Adjacent text nodes are concatenated without separators so that
    formatting marks (bold, links, ...) splitting a word do not corrupt it.

    Args:
        node: An ADF node (dict, list, or scalar).

    Returns:
        The concatenated inline text.
    """
    if isinstance(node, list):
        return "".join(_inline_text(item) for item in node)

    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")

    if node_type == "text":
        text = node.get("text", "")
        return text if isinstance(text, str) else ""

    if node_type == "hardBreak":
        return "\n"

    content = node.get("content", [])
    return _inline_text(content) if isinstance(content, list) else ""


def _collect_blocks(node: AdfNode) -> list[str]:
    """Recursively collect text blocks from an ADF node.

    Args:
        node: An ADF node (dict, list, or scalar).

    Returns:
        List of non-empty text blocks in document order.
    """
    if isinstance(node, list):
        blocks: list[str] = []
        for item in node:
            blocks.extend(_collect_blocks(item))
        return blocks

    if not isinstance(node, dict):
        return []

    node_type = node.get("type")

    if node_type in LEAF_BLOCK_TYPES or node_type == "text":
        text = _inline_text(node)
        return [text] if text.strip() else []

    content = node.get("content", [])
    if not isinstance(content, list):
        return []

    blocks = []
    for child in content:
        blocks.extend(_collect_blocks(child))
    return blocks


def adf_to_text(adf: dict[str, Any] | None) -> str:
    """Convert Atlassian Document Format to plain text.

    Inline fragments are joined without separators; block-level nodes
    (paragraphs, headings, list items, ...) are separated by blank lines,
    matching the paragraph convention used by text_to_adf.

    Args:
        adf: The ADF document structure.

    Returns:
        Plain text extracted from the ADF.
    """
    if not adf or not isinstance(adf, dict):
        return ""

    return "\n\n".join(_collect_blocks(adf)).strip()


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
