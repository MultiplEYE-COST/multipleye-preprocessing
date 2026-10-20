"""Tests for the reading-measure engine integration."""

from types import SimpleNamespace

import polars as pl
import pymovements as pm

from preprocessing.metrics.calculate import calculate_reading_measures


def _stimulus(trial_id: str, identifier: str, words: list[str]) -> SimpleNamespace:
    aois = pl.DataFrame(
        {
            "word_idx": list(range(len(words))),
            "word": words,
            "char_idx": list(range(len(words))),
            "page": ["page_1"] * len(words),
        }
    )
    return SimpleNamespace(
        trial_id=trial_id,
        full_identifier=identifier,
        text_stimulus=SimpleNamespace(aois=aois),
    )


def test_calls_engine_with_trial_page_grouping(monkeypatch):
    captured = {}

    def fake_engine(fixations, aois, *, group_columns=None, **kwargs):
        captured["fixations"] = fixations
        captured["aois"] = aois
        captured["group_columns"] = group_columns
        return pl.DataFrame(
            {
                "trial": ["trial_1", "trial_2"],
                "page": ["page_1", "page_1"],
                "word_index": [0, 0],
                "word": ["a", "b"],
                "TFC": [1, 0],
            }
        )

    monkeypatch.setattr(pm.measure.reading, "compute_reading_measures", fake_engine)

    fixations = pl.DataFrame({"trial": ["trial_1"], "name": ["fixation"]})
    gaze = SimpleNamespace(events=SimpleNamespace(frame=fixations))
    stimuli = [
        _stimulus("trial_1", "Stim_A_1", ["a"]),
        _stimulus("trial_2", "Stim_B_2", ["b"]),
    ]

    result = calculate_reading_measures(gaze, stimuli)
    assert result is not None

    assert captured["fixations"] is fixations
    assert captured["group_columns"] == ["trial", "page"]
    assert set(captured["aois"].columns) >= {"word_idx", "word", "char_idx", "trial"}
    assert captured["aois"]["trial"].to_list() == ["trial_1", "trial_2"]


def test_renames_word_index_and_adds_stimulus(monkeypatch):
    def fake_engine(fixations, aois, *, group_columns=None, **kwargs):
        return pl.DataFrame(
            {
                "trial": ["trial_1", "trial_2", "PRACTICE_trial_1"],
                "page": ["page_1", "page_1", "page_1"],
                "word_index": [0, 1, 0],
                "word": ["a", "b", "c"],
                "TFC": [1, 2, 3],
            }
        )

    monkeypatch.setattr(pm.measure.reading, "compute_reading_measures", fake_engine)

    gaze = SimpleNamespace(events=SimpleNamespace(frame=pl.DataFrame({"trial": []})))
    stimuli = [
        _stimulus("trial_1", "Stim_A_1", ["a"]),
        _stimulus("trial_2", "Stim_B_2", ["b"]),
    ]

    result = calculate_reading_measures(gaze, stimuli)

    assert "word_idx" in result.columns
    assert "word_index" not in result.columns
    assert result["stimulus"].to_list() == ["Stim_A_1", "Stim_B_2", None]
