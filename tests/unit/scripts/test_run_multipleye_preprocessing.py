"""Unit tests for run_preprocessing script."""

from pathlib import Path


def test_reading_measures_uses_sid_consistently():
    """Test that reading measures check and save use the same Sid instance.

    The Sid refactoring centralises folder path construction on `Sid`
    properties (accessed via `sess.sid`), so `sess.sid.reading_measures_dir`
    is the single source of truth for folder lookups and save destinations.
    """
    source_file = Path("preprocessing/scripts/run_preprocessing.py")
    source_code = source_file.read_text()

    lines = source_code.split("\n")

    rm_folder_line = None
    save_reading_measures_line = None

    for i, line in enumerate(lines):
        if "rm_folder = sess.sid.reading_measures_dir" in line:
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
    """Test that Sid is only instantiated once per session (via Session.sid).

    Sid should not be manually constructed with `Sid(...)` in the script.
    Instead, the single canonical Sid instance per session is provided
    by the `sess.sid` property on the Session dataclass.
    """
    source_file = Path("preprocessing/scripts/run_preprocessing.py")
    source_code = source_file.read_text()

    sid_construction_count = source_code.count("sid = Sid(")
    assert sid_construction_count == 0, (
        f"Expected 0 manual Sid constructions in run_preprocessing, "
        f"found {sid_construction_count}. Use sess.sid instead."
    )

    assert "sess.sid" in source_code, (
        "Expected sess.sid to be used in run_preprocessing"
    )
