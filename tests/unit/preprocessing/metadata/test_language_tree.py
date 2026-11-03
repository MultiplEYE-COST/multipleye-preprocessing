"""Tests for language node metadata and Glottolog validation."""

from __future__ import annotations

import pytest
import yaml

from preprocessing.config import Settings
from preprocessing.metadata.glottolog import (
    GlottologError,
    GlottologLanguoid,
    GlottologTable,
)
from preprocessing.metadata.language_tree import (
    LanguageTreeError,
    language_node_overview,
)


@pytest.fixture
def glottolog_table(monkeypatch):
    """Patch the Glottolog loader with a tiny in-memory table."""
    rows = {
        "indo1319": GlottologLanguoid(
            "indo1319", "Indo-European", "family", None, None
        ),
        "stan1295": GlottologLanguoid(
            "stan1295", "German", "language", "indo1319", "deu"
        ),
        "swis1247": GlottologLanguoid(
            "swis1247", "Central Alemannic", "language", "indo1319", "gsw"
        ),
        "zuri1239": GlottologLanguoid(
            "zuri1239", "Zürich German", "dialect", "swis1247", None
        ),
    }
    table = GlottologTable(rows)

    def fake_loader(*args, **kwargs):
        return table

    monkeypatch.setattr(
        "preprocessing.metadata.glottolog.load_glottolog_table", fake_loader
    )
    return table


def _config(tmp_path, language_tree: dict) -> Settings:
    path = tmp_path / "settings.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "data_collection_name": "MultiplEYE_EN_UK_London_1_2026",
                "language_tree": language_tree,
            }
        ),
        encoding="utf-8",
    )
    settings = Settings()
    settings.load(path)
    return settings


def test_no_language_node_configured() -> None:
    assert language_node_overview(None) is None
    assert Settings().validate_language_node() is None


def test_configured_node_without_label() -> None:
    assert language_node_overview(
        "stan1295", tree_path="Indo-European/Germanic/German"
    ) == {
        "language_node_id": "stan1295",
        "language_node_path": "Indo-European/Germanic/German",
        "language_node_label": None,
        "language_tree_version": None,
        "language_tree_hash": None,
    }


def test_configured_node_keeps_label_and_hash() -> None:
    assert language_node_overview(
        "stan1295",
        tree_path="Indo-European/Germanic/German",
        tree_version="2026.10",
        node_label="German",
        tree_hash="sha256:configured",
    ) == {
        "language_node_id": "stan1295",
        "language_node_path": "Indo-European/Germanic/German",
        "language_node_label": "German",
        "language_tree_version": "2026.10",
        "language_tree_hash": "sha256:configured",
    }


@pytest.mark.parametrize(
    ("node_id", "node_path", "message"),
    [
        ("stan1295", "root//node", "empty segments"),
        ("stan  1295", None, "extra spaces"),
        (" stan1295", None, "leading or trailing spaces"),
        ("stan1295", "root / node", "leading or trailing spaces"),
        ("stan/1295", None, "must not contain a slash"),
    ],
)
def test_invalid_node_metadata(node_id, node_path, message) -> None:
    with pytest.raises(LanguageTreeError, match=message):
        language_node_overview(node_id, tree_path=node_path)


def test_settings_fills_label_from_glottolog(tmp_path, glottolog_table) -> None:
    settings = _config(
        tmp_path,
        {
            "node_id": "stan1295",
            "node_path": "Indo-European/Germanic/German",
        },
    )

    assert settings.LANGUAGE_NODE_ID == "stan1295"
    assert settings.LANGUAGE_NODE_LABEL == "German"


def test_settings_keeps_configured_label(tmp_path, glottolog_table) -> None:
    settings = _config(
        tmp_path,
        {
            "node_id": "stan1295",
            "node_label": "German (display)",
        },
    )

    assert settings.LANGUAGE_NODE_LABEL == "German (display)"


def test_settings_accepts_dialect_node(tmp_path, glottolog_table) -> None:
    settings = _config(tmp_path, {"node_id": "zuri1239"})

    assert settings.LANGUAGE_NODE_LABEL == "Zürich German"


def test_settings_rejects_family_node(tmp_path, glottolog_table) -> None:
    with pytest.raises(GlottologError, match="family"):
        _config(tmp_path, {"node_id": "indo1319"})


def test_settings_rejects_unknown_node(tmp_path, glottolog_table) -> None:
    with pytest.raises(GlottologError, match="not a Glottolog"):
        _config(tmp_path, {"node_id": "xxxx1234"})


def test_settings_can_disable_glottolog_check(tmp_path) -> None:
    settings = _config(
        tmp_path,
        {"node_id": "leaf", "glottolog_check": False},
    )

    assert settings.LANGUAGE_NODE_ID == "leaf"
    assert settings.LANGUAGE_NODE_LABEL is None


def test_settings_rejects_removed_snapshot_key(tmp_path) -> None:
    with pytest.raises(TypeError, match="snapshot was removed"):
        _config(tmp_path, {"node_id": "stan1295", "snapshot": "tree.yaml"})


def test_settings_without_nested_language_tree() -> None:
    settings = Settings()

    assert settings.validate_language_node() is None
