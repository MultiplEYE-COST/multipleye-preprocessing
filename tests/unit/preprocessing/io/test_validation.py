import logging
from types import SimpleNamespace

import polars as pl

from preprocessing.io.validation import (
    find_low_sample_pages,
    find_message_order_conflicts,
    validate_asc_parsing,
)

TRIAL_COLUMNS = ["trial", "stimulus", "page"]


def _messages(*rows: tuple[float, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "time": [row[0] for row in rows],
            "content": [row[1] for row in rows],
        }
    )


def test_find_message_order_conflicts_detects_start_before_stop():
    messages = _messages(
        (1.0, "start_recording_trial_1_stimulus_A_page_1"),
        (2.0, "start_recording_trial_1_subject_difficulty_screen"),
        (2.0, "stop_recording_trial_1_stimulus_A_page_1"),
    )

    assert find_message_order_conflicts(messages) == [
        (
            2.0,
            [
                "start_recording_trial_1_subject_difficulty_screen",
                "stop_recording_trial_1_stimulus_A_page_1",
            ],
        )
    ]


def test_find_message_order_conflicts_accepts_stop_before_start():
    messages = _messages(
        (1.0, "start_recording_trial_1_stimulus_A_page_1"),
        (2.0, "stop_recording_trial_1_stimulus_A_page_1"),
        (2.0, "start_recording_trial_1_subject_difficulty_screen"),
    )

    assert find_message_order_conflicts(messages) == []


def test_find_low_sample_pages_reports_single_sample_group():
    samples = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_1", "trial_1"],
            "stimulus": ["A", "A", "A"],
            "page": ["page_1", "page_1", "subject_difficulty_screen"],
        }
    )

    low_sample_pages = find_low_sample_pages(samples, TRIAL_COLUMNS)

    assert low_sample_pages.to_dicts() == [
        {
            "trial": "trial_1",
            "stimulus": "A",
            "page": "subject_difficulty_screen",
            "sample_count": 1,
        }
    ]


def test_validate_asc_parsing_logs_conflicts_and_low_sample_pages(caplog):
    gaze = SimpleNamespace(
        messages=_messages(
            (2.0, "start_recording_trial_1_subject_difficulty_screen"),
            (2.0, "stop_recording_trial_1_stimulus_A_page_1"),
        ),
        samples=pl.DataFrame(
            {
                "trial": ["trial_1", "trial_1"],
                "stimulus": ["A", "A"],
                "page": ["subject_difficulty_screen", "page_1"],
            }
        ),
        trial_columns=TRIAL_COLUMNS,
    )

    with caplog.at_level(logging.WARNING, logger="preprocessing.io.validation"):
        result = validate_asc_parsing(gaze, session_id="001_TEST")

    assert result == {"message_order_conflicts": 1, "low_sample_pages": 2}
    assert "message order conflict in session 001_TEST at 2.0" in caplog.text
    assert "only 1 sample(s) in session 001_TEST" in caplog.text


def test_validate_asc_parsing_no_warnings_for_valid_data(caplog):
    gaze = SimpleNamespace(
        messages=_messages(
            (1.0, "start_recording_trial_1_stimulus_A_page_1"),
            (2.0, "stop_recording_trial_1_stimulus_A_page_1"),
            (2.0, "start_recording_trial_1_subject_difficulty_screen"),
        ),
        samples=pl.DataFrame(
            {
                "trial": ["trial_1"] * 4,
                "stimulus": ["A"] * 4,
                "page": [
                    "page_1",
                    "page_1",
                    "subject_difficulty_screen",
                    "subject_difficulty_screen",
                ],
            }
        ),
        trial_columns=TRIAL_COLUMNS,
    )

    with caplog.at_level(logging.WARNING, logger="preprocessing.io.validation"):
        result = validate_asc_parsing(gaze, session_id="001_TEST")

    assert result == {"message_order_conflicts": 0, "low_sample_pages": 0}
    assert [
        record
        for record in caplog.records
        if record.name == "preprocessing.io.validation"
    ] == []
