"""Tests for the fixation drift correction wrapper."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pymovements as pm

from preprocessing.config import settings
from preprocessing.events.correction import correct_fixations


def _stimulus() -> SimpleNamespace:
    aois = pl.DataFrame(
        {
            "char_idx": [1, 2, 3, 4],
            "char": ["a", "b", "c", "d"],
            "word": ["ab", "ab", "cd", "cd"],
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


def _gaze() -> SimpleNamespace:
    events = pm.Events(
        pl.DataFrame(
            {
                "name": ["fixation", "fixation"],
                "onset": [0, 200],
                "duration": [100, 100],
                "location_x": [100.0, 110.0],
                "location_y": [105.0, 195.0],
                "trial": ["t1", "t1"],
                "page": ["p1", "p1"],
            }
        ),
        trial_columns=["trial", "page"],
    )
    return SimpleNamespace(events=events)


def test_correct_fixations_snaps_to_lines_and_preserves_originals() -> None:
    gaze = _gaze()

    correct_fixations(gaze, [_stimulus()], algorithm="attach")

    frame = gaze.events.frame
    assert frame["location_y"].to_list() == [100.0, 200.0]
    assert frame["location_y_original"].to_list() == [105.0, 195.0]
    assert frame["correction_algorithm"].to_list() == ["attach", "attach"]


def test_correct_fixations_uses_configured_algorithm(monkeypatch) -> None:
    monkeypatch.setattr(settings, "FIXATION_CORRECTION_ALGORITHM", "attach")
    gaze = _gaze()

    correct_fixations(gaze, [_stimulus()])

    assert gaze.events.frame["correction_algorithm"].unique().to_list() == ["attach"]
