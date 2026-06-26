"""Unit tests for the preflight input file check."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from preprocessing.checks.preflight import (
    PreflightError,
    run_preflight_check,
)


@dataclass
class FakeSession:
    session_identifier: str
    session_file_path: Path
    session_folder_path: Path


@dataclass
class FakeDataCollection:
    stimulus_dir: Path
    language: str
    country: str
    lab_number: int
    city: str = "City"
    year: int = 2024
    sessions: dict[str, FakeSession] = field(default_factory=dict)


def _write_csv(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    """Write a tiny CSV with the given columns and rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ",".join(columns)
    lines = [header] + [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def preflight_env(tmp_path: Path):
    """Build a data-collection-like environment with one session.

    Returns a ``(data_collection, session_id)`` tuple.  The caller can remove / corrupt files
    **after** receiving the environment and **before** calling ``run_preflight_check``.
    """
    session_id = "001_EN_UK_1_ET1"

    # --- data-collection-level files -----------------------------------
    stim_dir = tmp_path / "stimuli"
    stim_dir.mkdir()
    lang = "EN"
    lang_lower = lang.lower()
    country = "UK"
    country_lower = country.lower()
    labnum = 1
    city = "city"
    year = 2024

    # Stimulus definition files (dummy — just a file, not a real xlsx/csv)
    (stim_dir / "multipleye_stimuli_experiment_EN.xlsx").write_text(
        "dummy", encoding="utf-8"
    )
    (stim_dir / "multipleye_comprehension_questions_EN.xlsx").write_text(
        "dummy", encoding="utf-8"
    )
    (
        stim_dir
        / f"multipleye_participant_instructions_{lang_lower}_with_img_paths.csv"
    ).write_text("dummy", encoding="utf-8")

    # Config folder
    config_dir = stim_dir / "config"
    config_dir.mkdir()
    (
        config_dir / f"config_{lang_lower}_{country_lower}_city_{labnum}_{year}.py"
    ).write_text("dummy", encoding="utf-8")
    (
        config_dir
        / f"MultiplEYE_{lang}_{country}_{city}_{labnum}_{year}_lab_configuration.json"
    ).write_text("{}", encoding="utf-8")
    (config_dir / f"stimulus_order_versions_{lang}_{country}_{labnum}.csv").write_text(
        "participant_id,version_number\n001,1\n", encoding="utf-8"
    )

    # Image/AOI folders
    for folder_name in [
        f"stimuli_images_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_stimuli_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_stimuli_images_{lang_lower}_{country_lower}_{labnum}",
        f"question_images_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_question_images_{lang_lower}_{country_lower}_{labnum}",
        f"participant_instructions_images_{lang_lower}_{country_lower}_{labnum}",
    ]:
        (stim_dir / folder_name).mkdir()

    # Documentation folder
    doc_dir = stim_dir.parent / "documentation"
    doc_dir.mkdir()
    (
        doc_dir
        / f"MultiplEYE_{lang}_{country}_{city}_{labnum}_{year}_metadata_form.json"
    ).write_text("{}", encoding="utf-8")

    # --- session folder ------------------------------------------------
    sess_folder = tmp_path / "sessions" / session_id
    sess_folder.mkdir(parents=True)

    edf_path = sess_folder / "data.edf"
    edf_path.write_text("edf data", encoding="utf-8")

    logfiles = sess_folder / "logfiles"
    logfiles.mkdir()

    (logfiles / "EXPERIMENT_LOGFILE_001.txt").write_text(
        "experiment data", encoding="utf-8"
    )
    (logfiles / "GENERAL_LOGFILE_001.txt").write_text("general data", encoding="utf-8")

    _write_csv(
        logfiles / "completed_stimuli.csv",
        ["stimulus_id", "stimulus_name", "trial_id", "completed"],
        [["1", "Arg_PISACowsMilk", "1", "1"]],
    )
    _write_csv(
        logfiles / "question_order_versions.csv",
        [
            "question_order_version",
            "local_question_1",
            "local_question_2",
            "bridging_question_1",
            "bridging_question_2",
            "global_question_1",
            "global_question_2",
        ],
        [["1", "101", "102", "201", "202", "301", "302"]],
    )

    session = FakeSession(
        session_identifier=session_id,
        session_file_path=edf_path,
        session_folder_path=sess_folder,
    )

    dc = FakeDataCollection(
        stimulus_dir=stim_dir,
        language="EN",
        country="UK",
        lab_number=1,
        sessions={session_id: session},
    )

    return dc, session_id


# ---------------------------------------------------------------------------
# Parametrized scenarios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario, modify_env, expected_errors",
    [
        # ---- pass ----------------------------------------------------------
        (
            "all_files_exist",
            lambda env: None,
            0,
        ),
        # ---- EDF -----------------------------------------------------------
        (
            "edf_missing",
            lambda env: env[0].sessions[env[1]].session_file_path.unlink(),
            1,
        ),
        # ---- logfiles folder -----------------------------------------------
        (
            "logfiles_folder_missing",
            lambda env: _rmtree(
                env[0].sessions[env[1]].session_folder_path / "logfiles"
            ),
            1,
        ),
        # ---- EXPERIMENT_*.txt ----------------------------------------------
        (
            "experiment_log_missing",
            lambda env: _remove_glob(
                env[0].sessions[env[1]].session_folder_path / "logfiles",
                "EXPERIMENT_*.txt",
            ),
            1,
        ),
        # ---- GENERAL_LOGFILE_*.txt -----------------------------------------
        (
            "general_log_missing",
            lambda env: _remove_glob(
                env[0].sessions[env[1]].session_folder_path / "logfiles",
                "GENERAL_LOGFILE_*.txt",
            ),
            1,
        ),
        # ---- completed_stimuli.csv -----------------------------------------
        (
            "completed_stimuli_missing",
            lambda env: (
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "completed_stimuli.csv"
            ).unlink(),
            1,
        ),
        (
            "completed_stimuli_unparseable",
            lambda env: (
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "completed_stimuli.csv"
            ).write_text("not,a,csv\n"),
            1,
        ),
        (
            "completed_stimuli_wrong_columns",
            lambda env: _write_csv(
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "completed_stimuli.csv",
                ["foo", "bar"],
                [["1", "2"]],
            ),
            1,
        ),
        # ---- question_order_versions.csv ------------------------------------
        (
            "question_order_missing",
            lambda env: (
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "question_order_versions.csv"
            ).unlink(),
            1,
        ),
        (
            "question_order_unparseable",
            lambda env: (
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "question_order_versions.csv"
            ).write_text("broken"),
            1,
        ),
        (
            "question_order_wrong_columns",
            lambda env: _write_csv(
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "question_order_versions.csv",
                ["a", "b"],
                [["1", "2"]],
            ),
            1,
        ),
        # ---- stimulus xlsx --------------------------------------------------
        (
            "stimulus_xlsx_missing",
            lambda env: (
                env[0].stimulus_dir / "multipleye_stimuli_experiment_EN.xlsx"
            ).unlink(),
            1,
        ),
        (
            "questions_xlsx_missing",
            lambda env: (
                env[0].stimulus_dir / "multipleye_comprehension_questions_EN.xlsx"
            ).unlink(),
            1,
        ),
        # ---- participant instructions CSV ------------------------------------
        (
            "participant_instructions_csv_missing",
            lambda env: (
                env[0].stimulus_dir
                / "multipleye_participant_instructions_en_with_img_paths.csv"
            ).unlink(),
            1,
        ),
        # ---- config python file (glob) --------------------------------------
        (
            "config_py_missing",
            lambda env: _remove_glob(env[0].stimulus_dir / "config", "config_*.py"),
            1,
        ),
        # ---- lab configuration JSON -----------------------------------------
        (
            "lab_config_json_missing",
            lambda env: (
                env[0].stimulus_dir
                / "config"
                / "MultiplEYE_EN_UK_city_1_2024_lab_configuration.json"
            ).unlink(),
            1,
        ),
        # ---- stimulus order versions CSV ------------------------------------
        (
            "stimulus_order_versions_csv_missing",
            lambda env: (
                env[0].stimulus_dir / "config" / "stimulus_order_versions_EN_UK_1.csv"
            ).unlink(),
            1,
        ),
        # ---- image folders ---------------------------------------------------
        (
            "stimuli_images_folder_missing",
            lambda env: _rmtree(env[0].stimulus_dir / "stimuli_images_en_uk_1"),
            1,
        ),
        (
            "aoi_stimuli_folder_missing",
            lambda env: _rmtree(env[0].stimulus_dir / "aoi_stimuli_en_uk_1"),
            1,
        ),
        # ---- documentation metadata form (warning, not error) ---------------
        (
            "metadata_form_json_missing",
            lambda env: _rmtree(env[0].stimulus_dir.parent / "documentation"),
            0,
        ),
        # ---- multiple failures ----------------------------------------------
        (
            "multiple_failures",
            lambda env: (
                (
                    env[0].stimulus_dir / "multipleye_stimuli_experiment_EN.xlsx"
                ).unlink(),
                env[0].sessions[env[1]].session_file_path.unlink(),
                (
                    env[0].sessions[env[1]].session_folder_path
                    / "logfiles"
                    / "completed_stimuli.csv"
                ).unlink(),
            ),
            3,
        ),
    ],
)
def test_preflight_scenarios(preflight_env, scenario, modify_env, expected_errors):
    """Verify that the preflight check reports the correct number of errors."""
    modify_env(preflight_env)
    dc = preflight_env[0]

    if expected_errors == 0:
        # Should not raise
        run_preflight_check(dc)
    else:
        with pytest.raises(PreflightError) as exc_info:
            run_preflight_check(dc)
        assert exc_info.value.num_errors == expected_errors, (
            f"Scenario {scenario!r}: expected {expected_errors} error(s), "
            f"got {exc_info.value.num_errors}: {exc_info.value}"
        )


# ---------------------------------------------------------------------------
# Multi-session test
# ---------------------------------------------------------------------------


def test_preflight_multiple_sessions(tmp_path: Path):
    """Three sessions with different failures — all reported in one error."""
    stim_dir = tmp_path / "stimuli"
    stim_dir.mkdir()
    lang = "EN"
    lang_lower = lang.lower()
    country = "UK"
    country_lower = country.lower()
    labnum = 1
    city = "city"
    year = 2024

    (stim_dir / "multipleye_stimuli_experiment_EN.xlsx").write_text(
        "dummy", encoding="utf-8"
    )
    (stim_dir / "multipleye_comprehension_questions_EN.xlsx").write_text(
        "dummy", encoding="utf-8"
    )
    (
        stim_dir
        / f"multipleye_participant_instructions_{lang_lower}_with_img_paths.csv"
    ).write_text("dummy", encoding="utf-8")

    config_dir = stim_dir / "config"
    config_dir.mkdir()
    (
        config_dir / f"config_{lang_lower}_{country_lower}_{city}_{labnum}_{year}.py"
    ).write_text("dummy", encoding="utf-8")
    (
        config_dir
        / f"MultiplEYE_{lang}_{country}_{city}_{labnum}_{year}_lab_configuration.json"
    ).write_text("{}", encoding="utf-8")
    (config_dir / f"stimulus_order_versions_{lang}_{country}_{labnum}.csv").write_text(
        "participant_id,version_number\n001,1\n", encoding="utf-8"
    )

    for folder_name in [
        f"stimuli_images_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_stimuli_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_stimuli_images_{lang_lower}_{country_lower}_{labnum}",
        f"question_images_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_question_images_{lang_lower}_{country_lower}_{labnum}",
        f"participant_instructions_images_{lang_lower}_{country_lower}_{labnum}",
    ]:
        (stim_dir / folder_name).mkdir()

    doc_dir = stim_dir.parent / "documentation"
    doc_dir.mkdir()
    (
        doc_dir
        / f"MultiplEYE_{lang}_{country}_{city}_{labnum}_{year}_metadata_form.json"
    ).write_text("{}", encoding="utf-8")

    sessions: dict[str, FakeSession] = {}
    for idx, missing in enumerate(["edf", "experiment_log", "question_order"]):
        sid = f"{idx:03d}_EN_UK_1_ET1"
        sess_dir = tmp_path / "sessions" / sid
        sess_dir.mkdir(parents=True)

        edf = sess_dir / "data.edf"
        if missing != "edf":
            edf.write_text("data", encoding="utf-8")

        logfiles = sess_dir / "logfiles"
        logfiles.mkdir()

        if missing != "experiment_log":
            (logfiles / "EXPERIMENT_LOGFILE_001.txt").write_text(
                "data", encoding="utf-8"
            )
        (logfiles / "GENERAL_LOGFILE_001.txt").write_text("data", encoding="utf-8")
        _write_csv(
            logfiles / "completed_stimuli.csv",
            ["stimulus_id", "stimulus_name", "trial_id", "completed"],
            [["1", "Arg_PISACowsMilk", "1", "1"]],
        )

        if missing != "question_order":
            _write_csv(
                logfiles / "question_order_versions.csv",
                [
                    "question_order_version",
                    "local_question_1",
                    "local_question_2",
                    "bridging_question_1",
                    "bridging_question_2",
                    "global_question_1",
                    "global_question_2",
                ],
                [["1", "101", "102", "201", "202", "301", "302"]],
            )

        sessions[sid] = FakeSession(
            session_identifier=sid,
            session_file_path=edf,
            session_folder_path=sess_dir,
        )

    dc = FakeDataCollection(
        stimulus_dir=stim_dir,
        language="EN",
        country="UK",
        lab_number=1,
        city=city,
        year=year,
        sessions=sessions,
    )

    with pytest.raises(PreflightError) as exc_info:
        run_preflight_check(dc)
    # Expect 3 errors: 1 × edf, 1 × experiment_log, 1 × question_order
    assert exc_info.value.num_errors == 3, exc_info.value


# ---------------------------------------------------------------------------
# Warning-only scenarios
# ---------------------------------------------------------------------------


def test_preflight_warnings_only(preflight_env):
    """Items that are warnings (metadata JSON, flaky AOI folders) should
    be logged but NOT raise ``PreflightError``."""
    dc, _ = preflight_env

    # Remove all warning-level items — should NOT raise
    import shutil

    shutil.rmtree(dc.stimulus_dir.parent / "documentation", ignore_errors=True)
    shutil.rmtree(dc.stimulus_dir / "aoi_stimuli_images_en_uk_1", ignore_errors=True)
    shutil.rmtree(dc.stimulus_dir / "aoi_question_images_en_uk_1", ignore_errors=True)

    run_preflight_check(dc)  # should not raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rmtree(path: Path) -> None:
    """Remove a directory and all its contents."""
    import shutil

    shutil.rmtree(path)


def _remove_glob(directory: Path, pattern: str) -> None:
    """Remove all files matching a glob pattern in the given directory."""
    for p in directory.glob(pattern):
        p.unlink()
