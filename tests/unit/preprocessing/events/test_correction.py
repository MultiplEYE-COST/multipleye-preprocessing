"""Tests for the fixation drift correction wrapper."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pymovements as pm
import pytest

from preprocessing.config import settings
from preprocessing.events.correction import correct_fixations


def _stimulus() -> SimpleNamespace:
    aois = pl.DataFrame(
        {
            "char_idx": [1, 2, 3, 4],
            "char": ["a", "b", "c", "d"],
            "unit_of_analysis": ["ab", "ab", "cd", "cd"],
            "top_left_x": [90.0, 100.0, 90.0, 100.0],
            "top_left_y": [80.0, 80.0, 180.0, 180.0],
            "width": [10.0, 10.0, 10.0, 10.0],
            "height": [40.0, 40.0, 40.0, 40.0],
            "page": ["p1", "p1", "p1", "p1"],
        }
    )
    return SimpleNamespace(
        text_stimulus=SimpleNamespace(aois=aois),
        trial_id="t1",
    )


def _lab_config() -> SimpleNamespace:
    return SimpleNamespace(
        final_fix_dot_x=1000.0,
        final_fix_dot_y=900.0,
        final_fix_dot_radius=20.0,
    )


def _gaze(*, include_dot: bool = False) -> SimpleNamespace:
    data = {
        "name": ["fixation", "fixation"],
        "onset": [0, 200],
        "duration": [100, 100],
        "location_x": [100.0, 110.0],
        "location_y": [105.0, 195.0],
        "trial": ["t1", "t1"],
        "page": ["p1", "p1"],
    }
    if include_dot:
        data["name"].append("fixation")
        data["onset"].append(400)
        data["duration"].append(100)
        data["location_x"].append(1000.0)
        data["location_y"].append(900.0)
        data["trial"].append("t1")
        data["page"].append("p1")

    events = pm.Events(
        pl.DataFrame(data),
        trial_columns=["trial", "page"],
    )
    return SimpleNamespace(events=events)


def test_correct_fixations_snaps_to_lines_and_preserves_originals() -> None:
    gaze = _gaze()

    correct_fixations(gaze, [_stimulus()], _lab_config(), algorithm="attach")

    frame = gaze.events.frame
    assert frame["location_y"].to_list() == [100.0, 200.0]
    assert frame["location_y_original"].to_list() == [105.0, 195.0]
    assert frame["correction_algorithm"].to_list() == ["attach", "attach"]


def _ttb_stimulus() -> SimpleNamespace:
    aois = pl.DataFrame(
        {
            "char_idx": [0, 1, 2, 3],
            "char": ["a", "b", "c", "d"],
            "word": ["ab", "ab", "cd", "cd"],
            "top_left_x": [200.0, 200.0, 119.0, 119.0],
            "top_left_y": [80.0, 108.0, 80.0, 108.0],
            "width": [28.0, 28.0, 28.0, 28.0],
            "height": [28.0, 28.0, 28.0, 28.0],
            "line_idx": [0, 0, 1, 1],
            "page": ["p1", "p1", "p1", "p1"],
        }
    )
    return SimpleNamespace(
        text_stimulus=SimpleNamespace(aois=aois),
        trial_id="t1",
    )


def _ttb_lab_config() -> SimpleNamespace:
    return SimpleNamespace(
        final_fix_dot_x=83.0,
        final_fix_dot_y=947.0,
        final_fix_dot_radius=8.0,
        script_direction="ttb",
    )


def _ttb_gaze(*, include_dot: bool = False) -> SimpleNamespace:
    data = {
        "name": ["fixation", "fixation"],
        "onset": [0, 200],
        "duration": [100, 100],
        "location_x": [205.0, 125.0],
        "location_y": [90.0, 100.0],
        "trial": ["t1", "t1"],
        "page": ["p1", "p1"],
    }
    if include_dot:
        data["name"].append("fixation")
        data["onset"].append(400)
        data["duration"].append(100)
        data["location_x"].append(83.0)
        data["location_y"].append(947.0)
        data["trial"].append("t1")
        data["page"].append("p1")

    events = pm.Events(
        pl.DataFrame(data),
        trial_columns=["trial", "page"],
    )
    return SimpleNamespace(events=events)


def test_correct_fixations_ttb_transposes_x_axis() -> None:
    gaze = _ttb_gaze()

    correct_fixations(
        gaze,
        [_ttb_stimulus()],
        _ttb_lab_config(),
        algorithm="attach",
    )

    frame = gaze.events.frame
    assert frame["location_x"].to_list() == [214.0, 133.0]
    assert frame["location_y"].to_list() == [90.0, 100.0]
    assert frame["location_x_original"].to_list() == [205.0, 125.0]
    assert frame["location_y_original"].to_list() == [90.0, 100.0]
    assert frame["correction_algorithm"].to_list() == ["attach", "attach"]


def test_correct_fixations_ttb_keeps_bottom_left_dot_unchanged() -> None:
    gaze = _ttb_gaze(include_dot=True)

    correct_fixations(
        gaze,
        [_ttb_stimulus()],
        _ttb_lab_config(),
        algorithm="attach",
    )

    frame = gaze.events.frame
    dot = frame.filter(pl.col("location_x") == 83.0)
    assert dot["location_y"].to_list() == [947.0]
    assert dot["correction_algorithm"].to_list() == [None]
    text = frame.filter(pl.col("location_x") != 83.0)
    assert text["location_x"].to_list() == [214.0, 133.0]


def test_correct_fixations_rejects_bottom_to_top_direction() -> None:
    lab_config = _ttb_lab_config()
    lab_config.script_direction = "btt"

    with pytest.raises(ValueError, match="btt"):
        correct_fixations(
            _ttb_gaze(),
            [_ttb_stimulus()],
            lab_config,
            algorithm="attach",
        )


def test_correct_fixations_passes_rtl_directionality() -> None:
    lab_config = _lab_config()
    lab_config.script_direction = "rtl"

    with pytest.raises(ValueError, match="right-to-left"):
        correct_fixations(
            _gaze(),
            [_stimulus()],
            lab_config,
            algorithm="compare",
        )


def test_correct_fixations_uses_configured_algorithm(monkeypatch) -> None:
    monkeypatch.setattr(settings, "FIXATION_CORRECTION_ALGORITHM", "attach")
    gaze = _gaze()

    correct_fixations(gaze, [_stimulus()], _lab_config())

    assert gaze.events.frame["correction_algorithm"].unique().to_list() == ["attach"]


def test_correct_fixations_keeps_final_dot_fixation_unchanged() -> None:
    gaze = _gaze(include_dot=True)

    correct_fixations(gaze, [_stimulus()], _lab_config(), algorithm="attach")

    frame = gaze.events.frame
    dot = frame.filter(pl.col("location_x") == 1000.0)
    assert dot["location_y"].to_list() == [900.0]
    assert dot["correction_algorithm"].to_list() == [None]
    text = frame.filter(pl.col("location_x") != 1000.0)
    assert text["location_y"].to_list() == [100.0, 200.0]


def test_offset_dot_fixation_is_excluded_from_correction() -> None:
    gaze = _gaze(include_dot=True)
    extra = pl.DataFrame(
        {
            "name": ["fixation"],
            "onset": [600],
            "duration": [100],
            "location_x": [1025.0],
            "location_y": [900.0],
            "trial": ["t1"],
            "page": ["p1"],
        }
    )
    gaze.events.frame = pl.concat([gaze.events.frame, extra], how="diagonal_relaxed")

    correct_fixations(gaze, [_stimulus()], _lab_config(), algorithm="attach")

    frame = gaze.events.frame
    dot = frame.filter(pl.col("location_x") >= 1000.0)
    assert dot["location_y"].to_list() == [900.0, 900.0]
    assert dot["correction_algorithm"].to_list() == [None, None]


def test_events_without_text_aois_are_not_corrected() -> None:
    events = pm.Events(
        pl.DataFrame(
            {
                "name": ["fixation", "fixation"],
                "onset": [0, 200],
                "duration": [100, 100],
                "location_x": [100.0, 500.0],
                "location_y": [105.0, 500.0],
                "trial": ["t1", "PRACTICE_trial_1"],
                "page": ["p1", "familiarity_rating_screen_1"],
            }
        ),
        trial_columns=["trial", "page"],
    )
    gaze = SimpleNamespace(events=events)

    correct_fixations(gaze, [_stimulus()], _lab_config(), algorithm="attach")

    frame = gaze.events.frame
    text = frame.filter(pl.col("trial") == "t1")
    practice = frame.filter(pl.col("trial") == "PRACTICE_trial_1")
    assert text["location_y"].to_list() == [100.0]
    assert practice["location_y"].to_list() == [500.0]
    assert practice["correction_algorithm"].to_list() == [None]


def test_correct_fixations_requires_final_dot_geometry() -> None:
    gaze = _gaze()

    with pytest.raises(ValueError, match="could not derive"):
        correct_fixations(
            gaze,
            [_stimulus()],
            SimpleNamespace(
                final_fix_dot_x=None,
                final_fix_dot_y=None,
                final_fix_dot_radius=None,
            ),
        )


def test_text_fixation_near_dot_inside_text_bounds_is_corrected() -> None:
    aois = pl.DataFrame(
        {
            "char_idx": [1, 2],
            "char": ["a", "b"],
            "unit_of_analysis": ["ab", "ab"],
            "top_left_x": [90.0, 100.0],
            "top_left_y": [80.0, 80.0],
            "width": [10.0, 10.0],
            "height": [10.0, 10.0],
            "page": ["p1", "p1"],
        }
    )
    stimulus = SimpleNamespace(
        text_stimulus=SimpleNamespace(aois=aois),
        trial_id="t1",
    )
    events = pm.Events(
        pl.DataFrame(
            {
                "name": ["fixation", "fixation"],
                "onset": [0, 200],
                "duration": [100, 100],
                "location_x": [110.0, 130.0],
                "location_y": [100.0, 105.0],
                "trial": ["t1", "t1"],
                "page": ["p1", "p1"],
            }
        ),
        trial_columns=["trial", "page"],
    )
    gaze = SimpleNamespace(events=events)
    lab_config = SimpleNamespace(
        final_fix_dot_x=130.0,
        final_fix_dot_y=105.0,
        final_fix_dot_radius=30.0,
    )

    correct_fixations(gaze, [stimulus], lab_config, algorithm="attach")

    frame = gaze.events.frame
    text = frame.filter(pl.col("location_x") == 110.0)
    dot = frame.filter(pl.col("location_x") == 130.0)
    assert text["location_y"].to_list() == [85.0]
    assert text["correction_algorithm"].to_list() == ["attach"]
    assert dot["location_y"].to_list() == [105.0]
    assert dot["correction_algorithm"].to_list() == [None]
