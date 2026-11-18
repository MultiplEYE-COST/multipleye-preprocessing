"""Tests for AOI geometry helpers."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest

from preprocessing.config import settings
from preprocessing.mapping.aoi import build_combined_text_stimulus, enlarge_aois


def _ttb_aois() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "char_idx": [0, 1, 2, 3],
            "char": ["a", "b", "c", "d"],
            "word": ["ab", "ab", "cd", "cd"],
            "top_left_x": [1244, 1244, 1163, 1163],
            "top_left_y": [91, 119, 91, 119],
            "width": [28, 28, 28, 28],
            "height": [28, 28, 28, 28],
            "char_idx_in_line": [0, 1, 0, 1],
            "line_idx": [0, 0, 1, 1],
            "page": ["page_1"] * 4,
            "word_idx": [0, 0, 1, 1],
            "word_idx_in_line": [0, 0, 1, 1],
        }
    )


def test_enlarge_aois_ttb_uses_columns_and_covers_gaps() -> None:
    enlarged = enlarge_aois(_ttb_aois(), script_direction="ttb")

    line_0 = enlarged.filter(pl.col("line_idx") == 0)
    line_1 = enlarged.filter(pl.col("line_idx") == 1)

    # Columns are ordered right-to-left: line_idx 0 is the rightmost column.
    assert line_0["top_left_x"].unique().to_list() == [1217.5]
    assert line_0["width"].unique().to_list() == [54.5]
    assert line_1["top_left_x"].unique().to_list() == [1163.0]
    assert line_1["width"].unique().to_list() == [54.5]

    # Vertical geometry is untouched.
    assert line_0["top_left_y"].to_list() == [91, 119]
    assert line_0["height"].to_list() == [28, 28]


def test_enlarge_aois_ltr_keeps_vertical_expansion() -> None:
    aois = pl.DataFrame(
        {
            "char_idx": [0, 1],
            "char": ["a", "b"],
            "top_left_x": [100, 100],
            "top_left_y": [100, 200],
            "width": [20, 20],
            "height": [20, 20],
            "line_idx": [0, 1],
            "page": ["page_1", "page_1"],
        }
    )

    enlarged = enlarge_aois(aois, script_direction="ltr").sort("line_idx")

    assert enlarged["top_left_y"].to_list() == [100.0, 160.0]
    assert enlarged["height"].to_list() == [20.0, 100.0]


def test_enlarge_aois_rejects_bottom_to_top() -> None:
    with pytest.raises(ValueError, match="btt"):
        enlarge_aois(_ttb_aois(), script_direction="btt")


def test_build_combined_text_stimulus_transposes_ttb_geometry() -> None:
    aois = _ttb_aois()
    stimulus = SimpleNamespace(
        text_stimulus=SimpleNamespace(aois=aois),
        trial_id="trial_1",
    )

    combined = build_combined_text_stimulus([stimulus], script_direction="ttb")

    assert combined.aois["top_left_x"].to_list() == aois["top_left_y"].to_list()
    assert combined.aois["top_left_y"].to_list() == aois["top_left_x"].to_list()
    assert combined.aois["width"].to_list() == aois["height"].to_list()
    assert combined.aois["height"].to_list() == aois["width"].to_list()
    assert combined.aois[settings.TRIAL_COL].unique().to_list() == ["trial_1"]
