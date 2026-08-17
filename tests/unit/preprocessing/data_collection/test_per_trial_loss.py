from pathlib import Path

import polars as pl
import pytest

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
from preprocessing.data_collection.session import Session

SESSION_NAME = "001_EN_UK_1_ET1"

TRIAL_COLS = ["trial", "stimulus"]
PAGE_COLS = ["trial", "stimulus", "page"]


def _make_session():
    return Session(
        participant_id=1,
        session_identifier=SESSION_NAME,
        is_pilot=False,
        session_folder_path=Path("/tmp"),
        session_file_path=Path("/tmp/test.log"),
        session_file_name="test.log",
    )


def _make_mdc(session):
    mdc = MultipleyeDataCollection.__new__(MultipleyeDataCollection)
    mdc.sessions = {SESSION_NAME: session}
    return mdc


def _data_loss_df(cols):
    return pl.DataFrame(
        {
            **{col: ["trial_1"] for col in cols},
            "data_loss_ratio": [0.05],
        }
    )


def _blink_loss_df(cols):
    return pl.DataFrame(
        {
            **{col: ["trial_1"] for col in cols},
            "blink_loss_ratio": [0.02],
            "blink_duration_ms": [100.0],
        }
    )


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ("page_1", "reading"),
        ("page_12", "reading"),
        ("question_Enc_WikiMoon_1", "question"),
        ("familiarity_rating_screen_1", "rating"),
        ("familiarity_rating_screen_2", "rating"),
        ("subject_difficulty_screen", "rating"),
        ("unknown_page", "other"),
    ],
)
def test_page_type(page, expected):
    mdc = _make_mdc(_make_session())
    assert mdc._page_type(page) == expected


def test_compute_per_trial_loss_table_both_available():
    session = _make_session()
    session._per_trial_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "data_loss_ratio": [0.05, 0.12],
        }
    )
    session._per_trial_blink_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "blink_loss_ratio": [0.02, 0.03],
            "blink_duration_ms": [100.0, 150.0],
            "trial_duration_ms": [5000.0, 7000.0],
        }
    )

    mdc = _make_mdc(session)
    result = mdc._compute_per_trial_loss_table(SESSION_NAME)

    assert result is not None
    assert result.height == 2
    assert "data_loss_ratio" in result.columns
    assert "blink_loss_ratio" in result.columns
    assert result["data_loss_ratio"].to_list() == [0.05, 0.12]
    assert result["blink_loss_ratio"].to_list() == [0.02, 0.03]
    assert result["trial_duration_ms"].to_list() == [5000.0, 7000.0]


def test_compute_per_trial_loss_table_handles_missing_trials():
    session = _make_session()
    session._per_trial_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "data_loss_ratio": [0.05, 0.12],
        }
    )
    session._per_trial_blink_loss = pl.DataFrame(
        {
            "trial": ["trial_1"],
            "stimulus": ["Enc_WikiMoon_1"],
            "blink_loss_ratio": [0.02],
            "blink_duration_ms": [100.0],
            "trial_duration_ms": [5000.0],
        }
    )

    mdc = _make_mdc(session)
    result = mdc._compute_per_trial_loss_table(SESSION_NAME)

    assert result is not None
    assert result.height == 2
    assert result["data_loss_ratio"].to_list() == [0.05, 0.12]
    # trial_2 has no blink data, should be null
    blink_ratios = result["blink_loss_ratio"].to_list()
    assert blink_ratios[0] == 0.02
    assert blink_ratios[1] is None


def test_compute_per_page_loss_table_both_available():
    session = _make_session()
    session._per_page_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "page": ["page_1", "question_Enc_WikiMoon_1", "subject_difficulty_screen"],
            "data_loss_ratio": [0.05, 0.10, 0.12],
        }
    )
    session._per_page_blink_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_1", "trial_2"],
            "stimulus": ["Enc_WikiMoon_1", "Enc_WikiMoon_1", "Lit_MagicMountain_6"],
            "page": ["page_1", "question_Enc_WikiMoon_1", "subject_difficulty_screen"],
            "blink_loss_ratio": [0.02, 0.03, 0.04],
            "blink_duration_ms": [100.0, 200.0, 300.0],
            "page_duration_ms": [5000.0, 6000.0, 7000.0],
        }
    )

    mdc = _make_mdc(session)
    result = mdc._compute_per_page_loss_table(SESSION_NAME)

    assert result is not None
    assert result.height == 3
    assert "page_type" in result.columns
    assert "page_duration_ms" in result.columns
    assert result["data_loss_ratio"].to_list() == [0.05, 0.10, 0.12]
    assert result["blink_loss_ratio"].to_list() == [0.02, 0.03, 0.04]
    assert result["page_type"].to_list() == ["reading", "question", "rating"]
    assert result["page_duration_ms"].to_list() == [5000.0, 6000.0, 7000.0]


@pytest.mark.parametrize(
    ("table_name", "cols", "include_data", "include_blink"),
    [
        ("_compute_per_trial_loss_table", TRIAL_COLS, True, False),
        ("_compute_per_trial_loss_table", TRIAL_COLS, False, True),
        ("_compute_per_trial_loss_table", TRIAL_COLS, False, False),
        ("_compute_per_page_loss_table", PAGE_COLS, True, False),
        ("_compute_per_page_loss_table", PAGE_COLS, False, False),
    ],
)
def test_compute_loss_table_presence(table_name, cols, include_data, include_blink):
    prefix = "per_page" if cols is PAGE_COLS else "per_trial"
    session = _make_session()
    setattr(
        session, f"_{prefix}_data_loss", _data_loss_df(cols) if include_data else None
    )
    setattr(
        session,
        f"_{prefix}_blink_loss",
        _blink_loss_df(cols) if include_blink else None,
    )

    mdc = _make_mdc(session)
    result = getattr(mdc, table_name)(SESSION_NAME)

    if result is None:
        assert not include_data and not include_blink
        return
    assert result.height == 1
    assert ("data_loss_ratio" in result.columns) == include_data
    assert ("blink_loss_ratio" in result.columns) == include_blink
    if prefix == "per_page":
        assert "page_type" in result.columns


def test_data_loss_by_page_type():
    session = _make_session()
    session._per_page_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_1", "trial_1", "trial_2"],
            "stimulus": [
                "Enc_WikiMoon_1",
                "Enc_WikiMoon_1",
                "Enc_WikiMoon_1",
                "Lit_MagicMountain_6",
            ],
            "page": [
                "page_1",
                "page_2",
                "familiarity_rating_screen_1",
                "subject_difficulty_screen",
            ],
            "data_loss_ratio": [0.10, 0.20, 0.30, 0.40],
        }
    )
    session._per_page_blink_loss = None

    mdc = _make_mdc(session)
    result = mdc._data_loss_by_page_type(SESSION_NAME)

    assert result is not None
    rows = {row["page_type"]: row for row in result.iter_rows(named=True)}
    assert rows["reading"]["mean_data_loss"] == pytest.approx(0.15)
    assert rows["reading"]["num_pages"] == 2
    assert rows["rating"]["mean_data_loss"] == pytest.approx(0.35)
    assert rows["rating"]["num_pages"] == 2


def test_data_loss_by_page_type_none_available():
    session = _make_session()
    session._per_page_data_loss = None
    session._per_page_blink_loss = None

    mdc = _make_mdc(session)
    assert mdc._data_loss_by_page_type(SESSION_NAME) is None
