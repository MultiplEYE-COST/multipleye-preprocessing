"""Tests for loading the metadata form from ``LabConfig.load``."""

from __future__ import annotations

from pathlib import Path

import pytest

from preprocessing.config import settings
from preprocessing.data_collection.stimulus import LabConfig

_LANG = "EN"
_COUNTRY = "UK"
_CITY = "City"
_LABNUM = 1
_YEAR = 2024

_CONFIG_PY = """\
RESOLUTION = (1920, 1080)
SCREEN_SIZE_CM = (54.2, 30.5)
DISTANCE_CM = 60.0
IMAGE_WIDTH_PX = 1310
IMAGE_HEIGHT_PX = 991
IMAGE_SIZE_CM = (37.0, 28.0)
MIN_MARGIN_LEFT_PX = 81
MIN_MARGIN_RIGHT_PX = 74
FIX_DOT_X = 55.5
FIX_DOT_Y = 110.0
"""


def _make_stimulus_dir(tmp_path: Path) -> Path:
    """Build the minimal stimulus/config layout needed by LabConfig.load."""
    stimulus_dir = tmp_path / "stimuli"
    config_dir = stimulus_dir / "config"
    config_dir.mkdir(parents=True)

    (
        config_dir
        / f"config_{_LANG.lower()}_{_COUNTRY.lower()}_city_{_LABNUM}_{_YEAR}.py"
    ).write_text(_CONFIG_PY, encoding="utf-8")
    (
        config_dir
        / f"MultiplEYE_{_LANG}_{_COUNTRY}_{_CITY}_{_LABNUM}_{_YEAR}_lab_configuration.json"
    ).write_text('{"Name_eye-tracker": "EyeLink 1000 Plus"}', encoding="utf-8")

    return stimulus_dir


def _load(stimulus_dir: Path) -> LabConfig:
    return LabConfig.load(stimulus_dir, _LANG, _COUNTRY, _LABNUM, _CITY, _YEAR)


def test_lab_config_reads_default_frequency_from_real_filename(tmp_path: Path):
    stimulus_dir = _make_stimulus_dir(tmp_path)
    doc_dir = stimulus_dir.parent / "documentation"
    doc_dir.mkdir()
    # Real upload spelling: metadataForm_ prefix and a trailing space.
    (doc_dir / "metadataForm_MultiplEYE_EN_UK_City_1_2024 .json").write_text(
        '{"Default_frequency": 500}', encoding="utf-8"
    )

    lab_config = _load(stimulus_dir)

    assert lab_config.sampling_frequency_hz == 500


def test_lab_config_reads_nested_sampling_rate(tmp_path: Path):
    """Real forms store the rate under Apparatus_lab_equipment.Sampling_rate."""
    stimulus_dir = _make_stimulus_dir(tmp_path)
    doc_dir = stimulus_dir.parent / "documentation"
    doc_dir.mkdir()
    (doc_dir / "metadataForm_MultiplEYE_EN_UK_City_1_2024.json").write_text(
        '{"Apparatus_lab_equipment": {"Sampling_rate": {"Default_frequency": 500}}}',
        encoding="utf-8",
    )

    lab_config = _load(stimulus_dir)

    assert lab_config.sampling_frequency_hz == 500


def test_lab_config_uses_expected_rate_when_frequency_key_missing(tmp_path: Path):
    """A parseable form without Default_frequency is not an error."""
    stimulus_dir = _make_stimulus_dir(tmp_path)
    doc_dir = stimulus_dir.parent / "documentation"
    doc_dir.mkdir()
    (doc_dir / "metadataform_MultiplEYE_EN_UK_City_1_2024.json").write_text(
        '{"Monitor_name": "Dell U2412M"}', encoding="utf-8"
    )

    lab_config = _load(stimulus_dir)

    assert lab_config.sampling_frequency_hz == settings.EXPECTED_SAMPLING_RATE_HZ


def test_lab_config_falls_back_when_metadata_form_missing(tmp_path: Path):
    stimulus_dir = _make_stimulus_dir(tmp_path)

    lab_config = _load(stimulus_dir)

    assert lab_config.sampling_frequency_hz == settings.EXPECTED_SAMPLING_RATE_HZ


def test_lab_config_raises_for_unparseable_metadata_form(tmp_path: Path):
    stimulus_dir = _make_stimulus_dir(tmp_path)
    doc_dir = stimulus_dir.parent / "documentation"
    doc_dir.mkdir()
    form_path = doc_dir / "metadataform_MultiplEYE_EN_UK_City_1_2024.json"
    form_path.write_text("not json at all", encoding="utf-8")

    with pytest.raises(ValueError, match="Could not parse metadata form"):
        _load(stimulus_dir)


def test_lab_config_derives_final_fix_dot_geometry(tmp_path: Path):
    stimulus_dir = _make_stimulus_dir(tmp_path)

    lab_config = _load(stimulus_dir)

    assert lab_config.final_fix_dot_x == 1236.0
    assert lab_config.final_fix_dot_y == 920.0
    assert lab_config.final_fix_dot_radius == 8.0


def test_lab_config_prefers_explicit_final_fix_dot_geometry(tmp_path: Path):
    stimulus_dir = _make_stimulus_dir(tmp_path)
    config_path = next((stimulus_dir / "config").glob("config_*.py"))
    config_path.write_text(
        _CONFIG_PY
        + "POS_BOTTOM_DOT_X_PX = 1200\n"
        + "POS_BOTTOM_DOT_Y_PX = 900\n"
        + "FIX_DOT_RADIUS = 11\n",
        encoding="utf-8",
    )

    lab_config = _load(stimulus_dir)

    assert lab_config.final_fix_dot_x == 1200.0
    assert lab_config.final_fix_dot_y == 900.0
    assert lab_config.final_fix_dot_radius == 11.0


def test_lab_config_derives_rtl_final_fix_dot_x(tmp_path: Path):
    stimulus_dir = _make_stimulus_dir(tmp_path)
    config_path = next((stimulus_dir / "config").glob("config_*.py"))
    config_path.write_text(
        _CONFIG_PY.replace("FIX_DOT_X = 55.5", "FIX_DOT_X = 1254.5"),
        encoding="utf-8",
    )

    lab_config = _load(stimulus_dir)

    assert lab_config.final_fix_dot_x == 81.0


def test_lab_config_leaves_final_fix_dot_unset_when_geometry_is_missing(
    tmp_path: Path,
):
    stimulus_dir = tmp_path / "stimuli"
    config_dir = stimulus_dir / "config"
    config_dir.mkdir(parents=True)
    missing_keys = (
        "MIN_MARGIN_LEFT_PX",
        "MIN_MARGIN_RIGHT_PX",
        "FIX_DOT_X",
    )
    (
        config_dir
        / f"config_{_LANG.lower()}_{_COUNTRY.lower()}_city_{_LABNUM}_{_YEAR}.py"
    ).write_text(
        "\n".join(
            line
            for line in _CONFIG_PY.splitlines()
            if not line.startswith(missing_keys)
        ),
        encoding="utf-8",
    )
    (
        config_dir
        / f"MultiplEYE_{_LANG}_{_COUNTRY}_{_CITY}_{_LABNUM}_{_YEAR}_lab_configuration.json"
    ).write_text('{"Name_eye-tracker": "EyeLink 1000 Plus"}', encoding="utf-8")

    lab_config = _load(stimulus_dir)

    assert lab_config.final_fix_dot_x is None
    assert lab_config.final_fix_dot_y is None
    assert lab_config.final_fix_dot_radius is None
