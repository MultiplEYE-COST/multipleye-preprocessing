"""Unit tests for run_preprocessing script."""

from pathlib import Path


def test_reading_measures_uses_sid_consistently():
    """Test that reading measures check and save use the same Sid instance.

    The Sid refactoring centralises folder path construction on `Sid`
    properties, so `sid.reading_measures_dir` is the single source of truth
    for folder lookups and save destinations.
    """
    source_file = Path("preprocessing/scripts/run_preprocessing.py")
    source_code = source_file.read_text()

    lines = source_code.split("\n")

    rm_folder_line = None
    save_reading_measures_line = None

    for i, line in enumerate(lines):
        if "rm_folder = sid.reading_measures_dir" in line:
            rm_folder_line = i
        if "preprocessing.save_reading_measures(" in line:
            save_reading_measures_line = i

    assert rm_folder_line is not None, "Could not find rm_folder assignment"
    assert save_reading_measures_line is not None, (
        "Could not find save_reading_measures call"
    )

    assert rm_folder_line < save_reading_measures_line, (
        "rm_folder should be assigned before the save call"
    )


def test_sid_is_single_instance_per_session():
    """Test that only one Sid is created per session (no repeated parsing).

    Sid should be constructed once per session loop iteration, not
    re-constructed inside each helper function call.
    """
    source_file = Path("preprocessing/scripts/run_preprocessing.py")
    source_code = source_file.read_text()

    sid_assignment_count = source_code.count("sid = Sid(")
    assert sid_assignment_count == 1, (
        f"Expected exactly 1 Sid assignment in run_preprocessing, found {sid_assignment_count}"
    )
