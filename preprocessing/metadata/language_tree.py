"""Resolve selected language nodes against a pinned language tree snapshot.

EyeStore owns the canonical language tree. This module does not ship a tree.
It only reads a caller supplied snapshot, validates the selected node and
derives the metadata written to the dataset overview.

Snapshot format
---------------
A snapshot is a YAML or JSON mapping with the keys ``version`` and ``nodes``.
Every node is a mapping with a stable ``id`` and a ``label``. A node may have
a ``parent`` id. An explicit ``path`` is used when present, otherwise the path
is built by joining the node ids from the root to the selected node with
slashes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "LanguageNode",
    "LanguageTreeError",
    "language_node_overview",
    "resolve_language_node",
]


class LanguageTreeError(ValueError):
    """Raised when a language tree snapshot or selected node is invalid."""


@dataclass(frozen=True, slots=True)
class LanguageNode:
    """One resolved node from a pinned language tree snapshot."""

    node_id: str
    path: str
    label: str
    tree_version: str | None
    tree_hash: str

    def to_overview(self) -> dict[str, str | None]:
        """Return the dataset overview representation of this node."""
        return {
            "language_node_id": self.node_id,
            "language_node_path": self.path or None,
            "language_node_label": self.label or None,
            "language_tree_version": self.tree_version,
            "language_tree_hash": self.tree_hash,
        }


def _snapshot_hash(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _parse_snapshot(payload: Any, source: Path) -> tuple[dict[str, dict], str | None]:
    if isinstance(payload, list):
        raw_nodes = payload
        version = None
    elif isinstance(payload, dict):
        raw_nodes = payload.get("nodes")
        version = payload.get("version", payload.get("tree_version"))
    else:
        raise LanguageTreeError(
            f"Language tree snapshot {source} must contain a node list or mapping."
        )

    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise LanguageTreeError(
            f"Language tree snapshot {source} has no non-empty 'nodes' list."
        )

    nodes: dict[str, dict] = {}
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            raise LanguageTreeError(
                f"Language tree snapshot {source} node {index} is not a mapping."
            )
        node_id = str(raw_node.get("id", "")).strip()
        label = str(raw_node.get("label", "")).strip()
        if not node_id:
            raise LanguageTreeError(
                f"Language tree snapshot {source} node {index} has no id."
            )
        if not label:
            raise LanguageTreeError(
                f"Language tree snapshot {source} node {node_id!r} has no label."
            )
        if node_id in nodes:
            raise LanguageTreeError(
                f"Language tree snapshot {source} has duplicate node id {node_id!r}."
            )
        parent = raw_node.get("parent")
        nodes[node_id] = {
            "label": label,
            "parent": str(parent).strip() if parent else None,
            "path": str(raw_node.get("path", "")).strip() or None,
        }

    for node_id, node in nodes.items():
        parent = node["parent"]
        if parent is not None and parent not in nodes:
            raise LanguageTreeError(
                f"Language tree snapshot {source} node {node_id!r} has unknown "
                f"parent {parent!r}."
            )

    return nodes, str(version) if version is not None else None


def _load_snapshot(snapshot: Path | str) -> tuple[dict[str, dict], str | None, str]:
    path = Path(snapshot)
    if not path.is_file():
        raise LanguageTreeError(f"Language tree snapshot not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise LanguageTreeError(
            f"Could not read language tree snapshot {path}: {exc}"
        ) from exc
    nodes, version = _parse_snapshot(payload, path)
    return nodes, version, _snapshot_hash(path)


def _node_path(node_id: str, nodes: dict[str, dict]) -> str:
    explicit = nodes[node_id]["path"]
    if explicit:
        return explicit

    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = node_id
    while current is not None:
        if current in seen:
            raise LanguageTreeError(
                f"Language tree snapshot has a parent cycle at node {current!r}."
            )
        seen.add(current)
        chain.append(current)
        current = nodes[current]["parent"]
    return "/".join(reversed(chain))


def resolve_language_node(
    snapshot: Path | str,
    node_id: str,
    expected_path: str | None = None,
    expected_version: str | None = None,
) -> LanguageNode:
    """Validate and resolve one node from a pinned language tree snapshot.

    Parameters
    ----------
    snapshot : Path or str
        Path to the pinned YAML or JSON snapshot.
    node_id : str
        Stable id of the selected node.
    expected_path : str, optional
        Full path configured for the node. When set it must match the snapshot.
    expected_version : str, optional
        Tree version configured for the node. When the snapshot records a
        version, both values must match.

    Returns
    -------
    LanguageNode
        Selected node with its path, label, tree version and snapshot hash.

    Raises
    ------
    LanguageTreeError
        If the snapshot is missing or malformed, the node is unknown, or the
        configured path or version does not match the snapshot.
    """
    loaded_nodes, loaded_version, tree_hash = _load_snapshot(snapshot)
    selected = str(node_id).strip()
    if selected not in loaded_nodes:
        available = ", ".join(sorted(loaded_nodes))
        raise LanguageTreeError(
            f"Language node {selected!r} is not in the pinned language tree "
            f"snapshot {Path(snapshot)}. Known node ids: {available}."
        )

    if expected_version and loaded_version and expected_version != loaded_version:
        raise LanguageTreeError(
            f"Language tree version {expected_version!r} does not match the "
            f"pinned snapshot version {loaded_version!r}."
        )

    path = _node_path(selected, loaded_nodes)
    if expected_path and expected_path.strip("/") != path.strip("/"):
        raise LanguageTreeError(
            f"Language node path {expected_path!r} does not match the pinned "
            f"snapshot path {path!r} for node {selected!r}."
        )

    return LanguageNode(
        node_id=selected,
        path=path,
        label=loaded_nodes[selected]["label"],
        tree_version=loaded_version or expected_version,
        tree_hash=tree_hash,
    )


def language_node_overview(
    node_id: str | None,
    tree_path: str | None = None,
    tree_version: str | None = None,
    snapshot: Path | str | None = None,
) -> dict[str, str | None] | None:
    """Return the dataset overview block for the configured language node.

    Returns ``None`` when no node is configured. Validation only runs when a
    snapshot path is provided, because the pipeline does not ship a tree.

    Parameters
    ----------
    node_id : str, optional
        Selected language node id.
    tree_path : str, optional
        Configured full path, checked against the snapshot when available.
    tree_version : str, optional
        Configured tree version, checked against the snapshot when available.
    snapshot : Path or str, optional
        Path to a pinned language tree snapshot.

    Returns
    -------
    dict or None
        Overview fields for the node, or ``None`` when no node is configured.

    Raises
    ------
    LanguageTreeError
        If a snapshot is provided and validation fails.
    """
    if not node_id:
        return None

    if not snapshot:
        return {
            "language_node_id": str(node_id),
            "language_node_path": tree_path or None,
            "language_node_label": None,
            "language_tree_version": tree_version or None,
            "language_tree_hash": None,
        }

    return resolve_language_node(
        snapshot,
        node_id,
        expected_path=tree_path,
        expected_version=tree_version,
    ).to_overview()
