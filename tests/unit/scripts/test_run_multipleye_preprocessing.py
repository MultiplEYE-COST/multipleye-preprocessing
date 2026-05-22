"""Unit tests for run_multipleye_preprocessing script."""

from pathlib import Path


def test_reading_measures_check_uses_session_save_name():
    """Test that reading measures folder check uses session_save_name, not session_idf.

    This test verifies the bug fix where the check for existing reading measures
    was using `output_folder` (per-session directory with full idf) but save was using
    `session_save_name` (which differs when sessions have _restart suffixes).

    When session_idf = "001_ET_EE_1_ET1_restart_1" and session_save_name = "001_ET_EE_1_ET1",
    the check should use session_save_name to match what save uses.
    """
    source_file = Path("preprocessing/scripts/run_multipleye_preprocessing.py")
    source_code = source_file.read_text()

    lines = source_code.split("\n")

    output_folder_line = None
    save_reading_measures_line = None

    for i, line in enumerate(lines):
        if "session_save_name / settings.READING_MEASURES_FOLDER" in line:
            output_folder_line = i
        if "preprocessing.save_reading_measures(" in line:
            save_reading_measures_line = i

    assert output_folder_line is not None, "Could not find rm_folder check line"
    assert save_reading_measures_line is not None, (
        "Could not find save_reading_measures call"
    )

    context_around_check = "\n".join(lines[output_folder_line : output_folder_line + 5])

    assert "session_save_name" in context_around_check, (
        "Bug: The check for existing reading measures should use session_save_name, not output_folder. "
        f"Found:\n{context_around_check}\n\nExpected 'session_save_name' in the check."
    )
