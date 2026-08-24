from pathlib import Path

import polars as pl

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
from preprocessing.data_collection.session import Session


def _make_session():
    return Session(
        participant_id=1,
        session_identifier="001_EN_UK_1_ET1",
        is_pilot=False,
        session_folder_path=Path("/tmp"),
        session_file_path=Path("/tmp/test.log"),
        session_file_name="test.log",
    )


def _make_mdc(session):
    mdc = MultipleyeDataCollection.__new__(MultipleyeDataCollection)
    mdc.sessions = {"001_EN_UK_1_ET1": session}
    return mdc


TRIAL_COLS = ["trial", "stimulus", "page"]


def test_compute_per_trial_loss_table_both_available():
    session = _make_session()
    session._per_trial_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "page": ["page_1", "page_1"],
            "data_loss_ratio": [0.05, 0.12],
        }
    )
    session._per_trial_blink_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "page": ["page_1", "page_1"],
            "blink_loss_ratio": [0.02, 0.03],
            "blink_duration_ms": [100.0, 150.0],
            "trial_duration_ms": [5000.0, 5000.0],
        }
    )

    mdc = _make_mdc(session)
    result = mdc._compute_per_trial_loss_table("001_EN_UK_1_ET1")

    assert result is not None
    assert result.height == 2
    assert "data_loss_ratio" in result.columns
    assert "blink_loss_ratio" in result.columns
    assert result["data_loss_ratio"].to_list() == [0.05, 0.12]
    assert result["blink_loss_ratio"].to_list() == [0.02, 0.03]


def test_compute_per_trial_loss_table_data_loss_only():
    session = _make_session()
    session._per_trial_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1"],
            "stimulus": ["Enc_WikiMoon_1"],
            "page": ["page_1"],
            "data_loss_ratio": [0.05],
        }
    )
    session._per_trial_blink_loss = None

    mdc = _make_mdc(session)
    result = mdc._compute_per_trial_loss_table("001_EN_UK_1_ET1")

    assert result is not None
    assert result.height == 1
    assert "data_loss_ratio" in result.columns
    assert "blink_loss_ratio" not in result.columns


def test_compute_per_trial_loss_table_blink_loss_only():
    session = _make_session()
    session._per_trial_data_loss = None
    session._per_trial_blink_loss = pl.DataFrame(
        {
            "trial": ["trial_1"],
            "stimulus": ["Enc_WikiMoon_1"],
            "page": ["page_1"],
            "blink_loss_ratio": [0.02],
            "blink_duration_ms": [100.0],
            "trial_duration_ms": [5000.0],
        }
    )

    mdc = _make_mdc(session)
    result = mdc._compute_per_trial_loss_table("001_EN_UK_1_ET1")

    assert result is not None
    assert result.height == 1
    assert "data_loss_ratio" not in result.columns
    assert "blink_loss_ratio" in result.columns


def test_compute_per_trial_loss_table_none_available():
    session = _make_session()
    session._per_trial_data_loss = None
    session._per_trial_blink_loss = None

    mdc = _make_mdc(session)
    result = mdc._compute_per_trial_loss_table("001_EN_UK_1_ET1")

    assert result is None


def test_compute_per_trial_loss_table_handles_missing_trials():
    session = _make_session()
    session._per_trial_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "page": ["page_1", "page_2"],
            "data_loss_ratio": [0.05, 0.12],
        }
    )
    session._per_trial_blink_loss = pl.DataFrame(
        {
            "trial": ["trial_1"],
            "stimulus": ["Enc_WikiMoon_1"],
            "page": ["page_1"],
            "blink_loss_ratio": [0.02],
            "blink_duration_ms": [100.0],
            "trial_duration_ms": [5000.0],
        }
    )

    mdc = _make_mdc(session)
    result = mdc._compute_per_trial_loss_table("001_EN_UK_1_ET1")

    assert result is not None
    assert result.height == 2
    assert result["data_loss_ratio"].to_list() == [0.05, 0.12]
    # trial_2 has no blink data, should be null
    blink_ratios = result["blink_loss_ratio"].to_list()
    assert blink_ratios[0] == 0.02
    assert blink_ratios[1] is None
