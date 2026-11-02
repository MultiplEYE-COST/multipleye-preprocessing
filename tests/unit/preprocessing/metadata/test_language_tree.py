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


def test_configured_node_without_snapshot_uses_configured_label_and_hash() -> None:
    assert language_node_overview(
        "leaf",
        tree_path="root/branch/leaf",
        tree_version="2026.10",
        tree_label="Leaf",
        tree_hash="sha256:configured",
    ) == {
        "language_node_id": "leaf",
        "language_node_path": "root/branch/leaf",
        "language_node_label": "Leaf",
        "language_tree_version": "2026.10",
        "language_tree_hash": "sha256:configured",
    }


def test_snapshot_fills_missing_path_label_and_hash(language_snapshot) -> None:
    assert language_node_overview("leaf", snapshot=language_snapshot) == {
        "language_node_id": "leaf",
        "language_node_path": "root/branch/leaf",
        "language_node_label": "Leaf",
        "language_tree_version": "2026.10",
        "language_tree_hash": (
            "sha256:" + hashlib.sha256(language_snapshot.read_bytes()).hexdigest()
        ),
    }


def test_snapshot_keeps_configured_label_and_hash(language_snapshot) -> None:
    result = language_node_overview(
        "leaf",
        snapshot=language_snapshot,
        tree_label="Configured Leaf",
        tree_hash="sha256:configured",
    )

    assert result["language_node_label"] == "Configured Leaf"
    assert result["language_tree_hash"] == "sha256:configured"


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


def test_snapshot_allows_single_spaces_in_ids_labels_and_paths(tmp_path) -> None:
    path = tmp_path / "language_tree_spaces.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": "2026.10",
                "nodes": [
                    {"id": "Indo European", "label": "Indo European"},
                    {
                        "id": "Germanic branch",
                        "label": "Germanic branch",
                        "parent": "Indo European",
                    },
                    {
                        "id": "High German",
                        "label": "High German",
                        "parent": "Germanic branch",
                        "path": "Indo European/Germanic branch/High German",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = language_node_overview("High German", snapshot=path)

    assert result["language_node_id"] == "High German"
    assert result["language_node_label"] == "High German"
    assert result["language_node_path"] == "Indo European/Germanic branch/High German"


@pytest.mark.parametrize(
    ("node", "message"),
    [
        ({"id": "bad  id", "label": "Bad"}, "extra spaces"),
        ({"id": "bad", "label": "Bad  label"}, "extra spaces"),
        (
            {"id": "bad", "label": "Bad", "path": "root//bad"},
            "empty segments",
        ),
        (
            {"id": "bad", "label": "Bad", "path": "root / bad"},
            "leading or trailing spaces",
        ),
    ],
)
def test_snapshot_rejects_extra_spaces_and_empty_path_segments(
    tmp_path, node, message
) -> None:
    path = tmp_path / "language_tree_invalid.yaml"
    path.write_text(
        yaml.safe_dump({"version": "2026.10", "nodes": [node]}),
        encoding="utf-8",
    )

    with pytest.raises(LanguageTreeError, match=message):
        language_node_overview(node["id"], snapshot=path)


def test_configured_path_with_extra_spaces_is_rejected(language_snapshot) -> None:
    with pytest.raises(LanguageTreeError, match="leading or trailing spaces"):
        language_node_overview(
            "leaf",
            tree_path="root /branch/leaf",
            snapshot=language_snapshot,
        )


def test_missing_snapshot_warns_when_node_is_configured(caplog) -> None:
    settings_obj = Settings()
    settings_obj.LANGUAGE_NODE_ID = "leaf"
    settings_obj.LANGUAGE_TREE_SNAPSHOT = None

    caplog.set_level("WARNING")
    settings_obj.validate_language_node()

    assert "No language tree snapshot configured" in caplog.text


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


def test_settings_loads_nested_language_tree(tmp_path, language_snapshot) -> None:
    config = tmp_path / "settings.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "data_collection_name": "MultiplEYE_EN_UK_London_1_2026",
                "language_tree": {
                    "node_id": "leaf",
                    "node_path": "root/branch/leaf",
                    "node_label": "Leaf",
                    "version": "2026.10",
                    "hash": "sha256:configured",
                    "snapshot": str(language_snapshot),
                },
            }
        ),
        encoding="utf-8",
    )

    settings_obj = Settings()
    settings_obj.load(config)

    assert settings_obj.LANGUAGE_NODE_ID == "leaf"
    assert settings_obj.LANGUAGE_TREE_PATH == "root/branch/leaf"
    assert settings_obj.LANGUAGE_NODE_LABEL == "Leaf"
    assert settings_obj.LANGUAGE_TREE_VERSION == "2026.10"
    assert settings_obj.LANGUAGE_TREE_HASH == "sha256:configured"
    assert settings_obj.LANGUAGE_TREE_SNAPSHOT == str(language_snapshot)


def test_settings_reject_missing_snapshot(tmp_path) -> None:
    config = tmp_path / "settings.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "data_collection_name": "MultiplEYE_EN_UK_London_1_2026",
                "language_tree": {
                    "node_id": "leaf",
                    "snapshot": str(tmp_path / "missing.yaml"),
                },
            }
        ),
        encoding="utf-8",
    )

    settings_obj = Settings()
    with pytest.raises(LanguageTreeError, match="snapshot not found"):
        settings_obj.load(config)


def test_settings_reject_invalid_nested_node(tmp_path, language_snapshot) -> None:
    config = tmp_path / "settings.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "data_collection_name": "MultiplEYE_EN_UK_London_1_2026",
                "language_tree": {
                    "node_id": "unknown",
                    "snapshot": str(language_snapshot),
                },
            }
        ),
        encoding="utf-8",
    )

    settings_obj = Settings()
    with pytest.raises(LanguageTreeError, match="not in the pinned"):
        settings_obj.load(config)


def test_settings_without_nested_language_tree() -> None:
    settings_obj = Settings()

    assert settings_obj.validate_language_node() is None
