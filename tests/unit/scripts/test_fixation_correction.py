"""Tests for fixation correction cache invalidation."""

from __future__ import annotations

import polars as pl

from preprocessing.config import settings
from preprocessing.scripts.run_preprocessing import _fixation_correction_is_current


def _write_fixation(
    path,
    correction_algorithm: str | None,
    *,
    include_column: bool = True,
) -> None:
    frame = pl.DataFrame(
        {
            "onset": [0],
            "duration": [100],
            "location_x": [1.0],
            "location_y": [2.0],
            "page": ["p1"],
        }
    )
    if include_column:
        frame = frame.with_columns(
            pl.Series(
                "correction_algorithm",
                [correction_algorithm],
                dtype=pl.Utf8,
            )
        )
    frame.write_csv(path)


def test_correction_cache_missing_is_not_current(tmp_path) -> None:
    assert not _fixation_correction_is_current(tmp_path)


def test_correction_cache_without_flag_matches_disabled_setting(tmp_path) -> None:
    _write_fixation(
        tmp_path / "sess_trial_1_fixation.csv",
        None,
        include_column=False,
    )

    assert _fixation_correction_is_current(tmp_path)


def test_correction_cache_with_flag_mismatches_disabled_setting(tmp_path) -> None:
    _write_fixation(tmp_path / "sess_trial_1_fixation.csv", "attach")

    assert not _fixation_correction_is_current(tmp_path)


def test_correction_cache_without_flag_mismatches_enabled_setting(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "RUN_FIXATION_CORRECTION", True)
    _write_fixation(
        tmp_path / "sess_trial_1_fixation.csv",
        None,
        include_column=False,
    )

    assert not _fixation_correction_is_current(tmp_path)


def test_correction_cache_matches_enabled_setting(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RUN_FIXATION_CORRECTION", True)
    monkeypatch.setattr(settings, "FIXATION_CORRECTION_ALGORITHM", "attach")
    _write_fixation(tmp_path / "sess_trial_1_fixation.csv", "attach")

    assert _fixation_correction_is_current(tmp_path)


def test_correction_cache_with_null_labels_matches_enabled_setting(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "RUN_FIXATION_CORRECTION", True)
    monkeypatch.setattr(settings, "FIXATION_CORRECTION_ALGORITHM", "attach")
    _write_fixation(tmp_path / "sess_trial_1_fixation.csv", None)

    assert _fixation_correction_is_current(tmp_path)


def test_correction_cache_with_other_algorithm_mismatches(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "RUN_FIXATION_CORRECTION", True)
    monkeypatch.setattr(settings, "FIXATION_CORRECTION_ALGORITHM", "attach")
    _write_fixation(tmp_path / "sess_trial_1_fixation.csv", "stretch")

    assert not _fixation_correction_is_current(tmp_path)


def test_correction_cache_requires_all_files_to_match(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RUN_FIXATION_CORRECTION", True)
    monkeypatch.setattr(settings, "FIXATION_CORRECTION_ALGORITHM", "attach")
    _write_fixation(tmp_path / "a_fixation.csv", "attach")
    _write_fixation(tmp_path / "b_fixation.csv", "stretch")

    assert not _fixation_correction_is_current(tmp_path)
