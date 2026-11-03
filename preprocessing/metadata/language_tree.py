"""Format the configured language node metadata.

The selected node is a Glottolog Glottocode. Validation against the pinned
Glottolog table happens in :mod:`preprocessing.metadata.glottolog` when the
settings are loaded. This module only checks the text shape and builds the
overview block. The EyeStore language tree is external and is not vendored by
the pipeline.
"""

from __future__ import annotations

__all__ = ["LanguageTreeError", "language_node_overview"]


class LanguageTreeError(ValueError):
    """Raised when configured language node metadata is invalid."""


def _clean_text(value: object, field: str, source: str) -> str:
    """Validate one node ID, label or path segment and return it as text."""
    text = str(value)
    if text != text.strip():
        raise LanguageTreeError(
            f"{source} {field} {text!r} must not have leading or trailing spaces."
        )
    if "  " in text or "\t" in text or "\n" in text:
        raise LanguageTreeError(
            f"{source} {field} {text!r} must not contain extra spaces."
        )
    return text


def _clean_path(value: object, field: str, source: str) -> str:
    """Validate a slash separated path with optional single spaces."""
    text = _clean_text(value, field, source)
    if not text:
        raise LanguageTreeError(f"{source} {field} must not be empty.")
    if text.startswith("/") or text.endswith("/"):
        raise LanguageTreeError(
            f"{source} {field} {text!r} must not start or end with a slash."
        )
    for segment in text.split("/"):
        _clean_text(segment, field, source)
        if not segment:
            raise LanguageTreeError(
                f"{source} {field} {text!r} must not contain empty segments."
            )
    return text


def language_node_overview(
    node_id: str | None,
    tree_path: str | None = None,
    tree_version: str | None = None,
    node_label: str | None = None,
    tree_hash: str | None = None,
) -> dict[str, str | None] | None:
    """Return the dataset overview block for the configured language node.

    Parameters
    ----------
    node_id : str, optional
        Glottocode of the selected language node.
    tree_path : str, optional
        Display path from the EyeStore tree root to the node. It is not derived
        from Glottolog because the EyeStore tree may prune intermediate levels.
    tree_version : str, optional
        Version of the EyeStore language tree.
    node_label : str, optional
        Human readable node label. The settings loader fills this from the
        Glottolog name when it is not configured.
    tree_hash : str, optional
        Hash of the EyeStore language tree.

    Returns
    -------
    dict or None
        Overview fields for the node, or ``None`` when no node is configured.

    Raises
    ------
    LanguageTreeError
        If the node ID, path or label has leading, trailing or repeated spaces,
        or the path has empty segments.
    """
    if not node_id:
        return None

    selected = _clean_text(node_id, "node id", "configured")
    if "/" in selected:
        raise LanguageTreeError(
            f"Configured language node id {selected!r} must not contain a slash."
        )
    path = _clean_path(tree_path, "path", "configured") if tree_path else None
    label = _clean_text(node_label, "label", "configured") if node_label else None

    return {
        "language_node_id": selected,
        "language_node_path": path,
        "language_node_label": label,
        "language_tree_version": tree_version or None,
        "language_tree_hash": tree_hash or None,
    }
