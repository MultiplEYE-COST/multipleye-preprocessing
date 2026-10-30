"""Tests for language node configuration and snapshot validation."""

from __future__ import annotations

import hashlib

import pytest
import yaml

from preprocessing.config import Settings
from preprocessing.metadata.language_tree import (
    LanguageTreeError,
    language_node_overview,
    resolve_language_node,
)

_SNAPSHOT = {
    "version": "2026.10",
    "nodes": [
        {"id": "root", "label": "Root"},
        {"id": "branch", "label": "Branch", "parent": "root"},
        {"id": "leaf", "label": "Leaf", "parent": "branch"},
    ],
}


@pytest.fixture
def language_snapshot(tmp_path):
    """Write a synthetic pinned tree snapshot. Not a real language tree."""
    path = tmp_path / "language_tree.yaml"
    path.write_text(yaml.safe_dump(_SNAPSHOT), encoding="utf-8")
    return path


@pytest.fixture
def settings_obj():
    return Settings()


def test_no_language_node_configured(settings_obj) -> None:
    assert language_node_overview(None) is None
    assert settings_obj.validate_language_node() is None


def test_valid_node_with_snapshot(language_snapshot) -> None:
    result = language_node_overview(
        "leaf",
        tree_path="root/branch/leaf",
        tree_version="2026.10",
        snapshot=language_snapshot,
    )

    assert result == {
        "language_node_id": "leaf",
        "language_node_path": "root/branch/leaf",
        "language_node_label": "Leaf",
        "language_tree_version": "2026.10",
        "language_tree_hash": (
            "sha256:" + hashlib.sha256(language_snapshot.read_bytes()).hexdigest()
        ),
    }


def test_configured_node_without_snapshot() -> None:
    assert language_node_overview(
        "leaf", tree_path="root/branch/leaf", tree_version="2026.10"
    ) == {
        "language_node_id": "leaf",
        "language_node_path": "root/branch/leaf",
        "language_node_label": None,
        "language_tree_version": "2026.10",
        "language_tree_hash": None,
    }


@pytest.mark.parametrize(
    ("node_id", "tree_path", "tree_version", "message"),
    [
        ("unknown", None, None, "not in the pinned language tree"),
        ("leaf", "root/other/leaf", None, "does not match the pinned snapshot path"),
        ("leaf", None, "1999.01", "does not match the pinned snapshot version"),
    ],
)
def test_invalid_node(
    language_snapshot, node_id, tree_path, tree_version, message
) -> None:
    with pytest.raises(LanguageTreeError, match=message):
        resolve_language_node(
            language_snapshot,
            node_id,
            expected_path=tree_path,
            expected_version=tree_version,
        )


def test_missing_snapshot(tmp_path) -> None:
    with pytest.raises(LanguageTreeError, match="snapshot not found"):
        resolve_language_node(tmp_path / "missing.yaml", "leaf")


def test_settings_loads_valid_language_node(tmp_path, language_snapshot) -> None:
    config = tmp_path / "settings.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "data_collection_name": "MultiplEYE_EN_UK_London_1_2026",
                "language_node_id": "leaf",
                "language_tree_path": "root/branch/leaf",
                "language_tree_version": "2026.10",
                "language_tree_snapshot": str(language_snapshot),
            }
        ),
        encoding="utf-8",
    )

    settings_obj = Settings()
    settings_obj.load(config)

    assert settings_obj.LANGUAGE_NODE_ID == "leaf"
    assert settings_obj.LANGUAGE_TREE_SNAPSHOT == str(language_snapshot)
