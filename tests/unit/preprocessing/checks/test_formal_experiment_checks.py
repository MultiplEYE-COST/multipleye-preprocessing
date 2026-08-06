"""Unit tests for the formal experiment sanity check report formatting."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import polars as pl

from preprocessing.checks.formal_experiment_checks import (
    check_all_screens_logfile,
    check_messages,
    sanity_check_gaze_frame,
)
from preprocessing.data_collection.stimulus import (
    ComprehensionQuestion,
    Rating,
    Stimulus,
    StimulusPage,
)


def _empty_path() -> Path:
    return Path("")


def _make_stimulus() -> Stimulus:
    """Build a stimulus with one page/question/rating missing from any data."""
    return Stimulus(
        id=3,
        name="Lit_BrokenApril",
        type="experiment",
        pages=[
            StimulusPage(
                number=1,
                text="",
                image_path=_empty_path(),
                aoi_image_path=_empty_path(),
            ),
            StimulusPage(
                number=2,
                text="",
                image_path=_empty_path(),
                aoi_image_path=_empty_path(),
            ),
            StimulusPage(
                number=3,
                text="",
                image_path=_empty_path(),
                aoi_image_path=_empty_path(),
            ),
        ],
        text_stimulus=None,
        questions=[
            ComprehensionQuestion(
                name="q1101",
                id="1101",
                snippet_no=1,
                question="",
                target="",
                distractor_a="",
                distractor_b="",
                distractor_c="",
                image_path=_empty_path(),
                aoi_image_path=_empty_path(),
            )
        ],
        instructions=[],
        ratings=[
            Rating(
                id=15,
                name="showing_subject_difficulty_screen",
                text="",
                image_path=_empty_path(),
            )
        ],
        trial_id="trial_5",
    )


def test_check_all_screens_logfile_report_lines_have_bullet_prefix(
    tmp_path: Path,
) -> None:
    stimulus = _make_stimulus()
    logfile = pl.DataFrame(
        {
            "stimulus_number": ["3", "3", "3"],
            "trial_number": ["5", "5", "5"],
            "page_number": ["1", "2", "2"],
        }
    )
    report_file = tmp_path / "report.md"

    check_all_screens_logfile(logfile, [stimulus], report_file)

    lines = report_file.read_text(encoding="utf-8").splitlines()
    assert lines, "expected report lines to be written"
    assert all(line.startswith("- ") for line in lines), lines
    assert "- Lit_BrokenApril: Missing page 3 in Logfile" in lines
    assert "- Lit_BrokenApril: Missing question_1101 in Logfile" in lines
    assert (
        "- Lit_BrokenApril: Missing rating screen showing_subject_difficulty_screen in Logfile"
        in lines
    )


def test_sanity_check_gaze_frame_report_lines_have_bullet_prefix(
    tmp_path: Path,
) -> None:
    stimulus = _make_stimulus()
    gaze = SimpleNamespace(
        samples=pl.DataFrame(
            {
                "stimulus": ["Lit_BrokenApril_3", "Lit_BrokenApril_3"],
                "page": ["page_1", "page_2"],
            }
        )
    )
    report_file = tmp_path / "report.md"

    sanity_check_gaze_frame(gaze, [stimulus], report_file)

    lines = report_file.read_text(encoding="utf-8").splitlines()
    assert lines, "expected report lines to be written"
    assert all(line.startswith("- ") for line in lines), lines
    assert "- Lit_BrokenApril: Missing page 3 in asc file" in lines
    assert "- Missing question_q1101 in asc file or in experiment frame" in lines
    assert "- Missing rating showing_subject_difficulty_screen in asc file" in lines


def test_check_messages_report_lines_have_bullet_prefix(tmp_path: Path) -> None:
    stimulus = _make_stimulus()
    messages = [
        {
            "message": "start_recording_trial_1_stimulus_Lit_BrokenApril_3_page_1",
            "timestamp": "1000",
        },
        {
            "message": "stop_recording_trial_1_stimulus_Lit_BrokenApril_3_page_1",
            "timestamp": "2000",
        },
    ]
    report_file = tmp_path / "report.md"

    check_messages(messages, [stimulus], report_file, stimuli_order=[3])

    lines = report_file.read_text(encoding="utf-8").splitlines()
    assert lines, "expected report lines to be written"
    assert all(line.startswith("- ") for line in lines), lines
    assert (
        "- Lit_BrokenApril: Missing page_screen_image_onset Messages in ASC file"
        in lines
    )
    assert (
        "- Lit_BrokenApril: Missing stop_recording_trial_1_stimulus_Lit_BrokenApril_3_page_1 Messages in ASC file"
        in lines
    )
    assert (
        "- Lit_BrokenApril: Missing validation_before_stimulus and no recalibration screen in asc file. One should be there."
        in lines
    )
    assert "- Missing one time screen welcome_screen in asc file" in lines
    assert "- Missing rating showing_subject_difficulty_screen in asc file" in lines
