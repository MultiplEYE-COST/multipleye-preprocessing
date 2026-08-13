"""Unit tests for the preflight input file check."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from preprocessing.checks.preflight import (
    PreflightError,
    _check_psychometric_tests,
    run_preflight_check,
)
from preprocessing.config import settings


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
    (logfiles / "DATA_LOGFILE_001.txt").write_text("logfile data", encoding="utf-8")
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
        (
            "experiment_log_duplicate",
            lambda env: (
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "EXPERIMENT_LOGFILE_002.txt"
            ).write_text("duplicate experiment log", encoding="utf-8"),
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
        (
            "general_log_duplicate",
            lambda env: (
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "GENERAL_LOGFILE_002.txt"
            ).write_text("duplicate general log", encoding="utf-8"),
            1,
        ),
        # ---- DATA_LOGFILE_*.txt ---------------------------------------------
        (
            "data_logfile_missing",
            lambda env: _remove_glob(
                env[0].sessions[env[1]].session_folder_path / "logfiles",
                "DATA_LOGFILE_*.txt",
            ),
            1,
        ),
        (
            "data_logfile_duplicate",
            lambda env: (
                env[0].sessions[env[1]].session_folder_path
                / "logfiles"
                / "DATA_LOGFILE_002.txt"
            ).write_text("duplicate data log", encoding="utf-8"),
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
        # ---- empty stimulus folder ------------------------------------------
        (
            "stimulus_folder_empty",
            lambda env: _make_empty(env[0].stimulus_dir),
            1,
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
        "participant_id,version_number\n000,1\n001,1\n002,1\n", encoding="utf-8"
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
        (logfiles / "DATA_LOGFILE_001.txt").write_text("data", encoding="utf-8")
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
# Empty stimulus directory
# ---------------------------------------------------------------------------


def test_preflight_duplicate_experiment_log_message(preflight_env):
    """Multiple EXPERIMENT_*.txt files produce a descriptive message."""
    dc, sid = preflight_env
    logfiles = dc.sessions[sid].session_folder_path / "logfiles"
    (logfiles / "EXPERIMENT_LOGFILE_002.txt").write_text(
        "duplicate experiment log", encoding="utf-8"
    )

    with pytest.raises(PreflightError) as exc_info:
        run_preflight_check(dc)

    msg = str(exc_info.value)
    assert "Multiple EXPERIMENT_*.txt logfiles" in msg
    assert sid in msg
    assert "2 files" in msg
    assert exc_info.value.num_errors == 1


def test_preflight_stimulus_dir_empty_message(preflight_env):
    """Empty stimulus directory produces a descriptive message."""
    dc, _ = preflight_env
    _make_empty(dc.stimulus_dir)

    with pytest.raises(PreflightError) as exc_info:
        run_preflight_check(dc)

    msg = str(exc_info.value)
    assert "Stimulus folder is empty" in msg
    assert exc_info.value.num_errors == 1


def test_preflight_stimulus_dir_empty_with_archive(tmp_path: Path):
    """If an archive sits next to the empty stim dir, mention it."""
    stim_dir = tmp_path / "stimuli"
    stim_dir.mkdir()
    # Create a dummy archive
    (tmp_path / "stimuli_data.zip").write_text("fake zip", encoding="utf-8")
    # Session still works
    sid = "001_EN_UK_1_ET1"
    sess_folder = tmp_path / "sessions" / sid
    sess_folder.mkdir(parents=True)
    (sess_folder / "data.edf").write_text("data", encoding="utf-8")
    logfiles = sess_folder / "logfiles"
    logfiles.mkdir()
    (logfiles / "EXPERIMENT_LOGFILE_001.txt").write_text("data", encoding="utf-8")
    (logfiles / "DATA_LOGFILE_001.txt").write_text("data", encoding="utf-8")
    (logfiles / "GENERAL_LOGFILE_001.txt").write_text("data", encoding="utf-8")
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
        session_identifier=sid,
        session_file_path=sess_folder / "data.edf",
        session_folder_path=sess_folder,
    )
    dc = FakeDataCollection(
        stimulus_dir=stim_dir,
        language="EN",
        country="UK",
        lab_number=1,
        sessions={sid: session},
    )

    with pytest.raises(PreflightError) as exc_info:
        run_preflight_check(dc)

    msg = str(exc_info.value)
    assert "Stimulus folder is empty" in msg
    assert "stimuli_data.zip" in msg
    assert "Extract the archive" in msg


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


def _make_empty(path: Path) -> None:
    """Remove all contents of a directory, leaving it empty."""
    import shutil

    for child in list(path.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


# ---------------------------------------------------------------------------
# Psychometric tests preflight checks
# ---------------------------------------------------------------------------

ALL_TESTS = ["PLAB", "RAN", "Stroop_Flanker", "WMC", "WikiVocab"]


@pytest.fixture
def pt_env(tmp_path: Path, monkeypatch):
    """Set up a basic environment with PT dir and a FakeDataCollection."""
    pt_dir = tmp_path / "data" / "dcn" / "psychometric-tests-sessions"
    pt_dir.mkdir(parents=True)
    monkeypatch.setattr(type(settings), "PSYCHOMETRIC_TESTS_DIR", pt_dir)
    monkeypatch.setattr(settings, "RUN_PSYCHOMETRIC_TESTS", True)

    dc = FakeDataCollection(
        stimulus_dir=tmp_path / "stimuli",
        language="EN",
        country="UK",
        lab_number=1,
        sessions={},
    )
    return dc, pt_dir


def _make_session_first(
    pt_dir: Path,
    sid: str = "001_EN_UK_1_PT1",
    tests: list[str] | None = None,
    with_yaml: bool = True,
):
    """Create a session-first folder with given test subfolders."""
    tests = tests if tests is not None else ALL_TESTS
    session = pt_dir / sid
    session.mkdir(parents=True, exist_ok=True)
    if with_yaml:
        (session / f"{sid}.yaml").touch()
    for t in tests:
        (session / t).mkdir()
    return session


def _make_task_first(
    base: Path,
    lang: str = "EN",
    country: str = "UK",
    lab: str = "1",
    tests: list[str] | None = None,
):
    """Create a task-first structure under *base* (either pt_dir or core_data)."""
    tests = tests if tests is not None else ["PLAB", "RAN"]
    config_dir = base / f"participant_configs_{lang}_{country}_{lab}"
    config_dir.mkdir(parents=True)
    with open(config_dir / "001_EN_UK_1_S1.yaml", "w") as f:
        yaml.safe_dump({"dummy": True}, f)

    data_dir = base / f"psychometric_test_{lang}_{country}_{lab}"
    for t in tests:
        s = data_dir / t / "001_EN_UK_1_PT1"
        s.mkdir(parents=True)
        (s / "data.csv").write_text("dummy", encoding="utf-8")
    return config_dir, data_dir


@pytest.mark.parametrize(
    "scenario, setup_fn, expect_warnings",
    [
        (
            "session_first_missing_tests",
            lambda pt_dir: _make_session_first(pt_dir, tests=["PLAB"]),
            ["missing test folder: RAN", "missing test folder: WMC"],
        ),
        (
            "session_first_missing_yaml",
            lambda pt_dir: _make_session_first(pt_dir, with_yaml=False),
            ["no YAML config"],
        ),
    ],
    ids=["session_first_missing_tests", "session_first_missing_yaml"],
)
def test_pt_check_session_first_warnings(pt_env, scenario, setup_fn, expect_warnings):
    """Session-first data with issues produces the expected warnings."""
    dc, pt_dir = pt_env
    setup_fn(pt_dir)
    pt_warnings: list[str] = []
    _check_psychometric_tests(dc, pt_warnings)
    for substr in expect_warnings:
        assert any(substr in w for w in pt_warnings), (
            f"Expected '{substr}' in warnings: {pt_warnings}"
        )


def test_pt_check_session_first_valid(pt_env):
    """Well-formed session-first data produces no warnings."""
    dc, pt_dir = pt_env
    _make_session_first(pt_dir)
    pt_warnings: list[str] = []
    _check_psychometric_tests(dc, pt_warnings)
    assert pt_warnings == []


def test_pt_check_task_first_auto_restructure_flat(pt_env):
    """Auto-restructures flat task-first data to session-first."""
    dc, pt_dir = pt_env
    _make_task_first(pt_dir)

    pt_warnings: list[str] = []
    _check_psychometric_tests(dc, pt_warnings)

    assert not any("No recognizable" in w for w in pt_warnings)
    assert not any("Archives found" in w for w in pt_warnings)

    restructured = pt_dir / "001_EN_UK_1_PT1"
    assert restructured.exists()
    assert (restructured / "PLAB").is_dir()
    assert (restructured / "001_EN_UK_1_S1.yaml").exists()


def test_pt_check_task_first_auto_restructure_core_data(pt_env):
    """Auto-restructures task-first data under core_data/ wrapper."""
    dc, pt_dir = pt_env
    core_data = pt_dir / "core_data"
    core_data.mkdir()
    _make_task_first(core_data)

    pt_warnings: list[str] = []
    _check_psychometric_tests(dc, pt_warnings)

    restructured = pt_dir / "001_EN_UK_1_PT1"
    assert restructured.exists()
    assert (restructured / "PLAB").is_dir()


def test_pt_check_no_folder(tmp_path: Path, monkeypatch):
    """Warns when psychometric-tests-sessions folder doesn't exist."""
    monkeypatch.setattr(
        type(settings), "PSYCHOMETRIC_TESTS_DIR", tmp_path / "nonexistent"
    )
    monkeypatch.setattr(settings, "RUN_PSYCHOMETRIC_TESTS", True)

    dc = FakeDataCollection(
        stimulus_dir=tmp_path / "stimuli",
        language="EN",
        country="UK",
        lab_number=1,
        sessions={},
    )
    pt_warnings: list[str] = []
    _check_psychometric_tests(dc, pt_warnings)
    assert len(pt_warnings) == 1
    assert "No 'psychometric-tests-sessions' folder" in pt_warnings[0]


@pytest.mark.parametrize(
    "setup_fn, expected_substrings",
    [
        (
            lambda pt_dir: (pt_dir / "psychometric_data.zip").write_text(
                "fake", encoding="utf-8"
            ),
            ["Archives found", "psychometric_data.zip", "psychometric_test_EN_UK_1"],
        ),
        (
            lambda pt_dir: (
                (pt_dir / "random_folder").mkdir()
                or (pt_dir / "random_folder" / "stuff.txt").write_text(
                    "x", encoding="utf-8"
                )
            ),
            ["No recognizable"],
        ),
    ],
    ids=["archives_found", "unrecognized_data"],
)
def test_pt_check_data_issues(
    tmp_path: Path, monkeypatch, setup_fn, expected_substrings
):
    """Warns about archives or unrecognized data in the PT folder."""
    pt_dir = tmp_path / "pt"
    pt_dir.mkdir()
    monkeypatch.setattr(type(settings), "PSYCHOMETRIC_TESTS_DIR", pt_dir)
    monkeypatch.setattr(settings, "RUN_PSYCHOMETRIC_TESTS", True)
    setup_fn(pt_dir)

    dc = FakeDataCollection(
        stimulus_dir=tmp_path / "stimuli",
        language="EN",
        country="UK",
        lab_number=1,
        sessions={},
    )
    pt_warnings: list[str] = []
    _check_psychometric_tests(dc, pt_warnings)
    assert len(pt_warnings) == 1
    for substr in expected_substrings:
        assert substr in pt_warnings[0]


def test_pt_check_flag_disabled(pt_env, monkeypatch):
    """No warnings when RUN_PSYCHOMETRIC_TESTS is False."""
    dc, _pt_dir = pt_env
    monkeypatch.setattr(settings, "RUN_PSYCHOMETRIC_TESTS", False)
    pt_warnings: list[str] = []
    _check_psychometric_tests(dc, pt_warnings)
    assert pt_warnings == []


def test_pt_does_not_inflate_error_count(tmp_path: Path, monkeypatch):
    """PT warnings must not inflate PreflightError.num_errors."""
    monkeypatch.setattr(
        type(settings), "PSYCHOMETRIC_TESTS_DIR", tmp_path / "nonexistent_pt"
    )
    monkeypatch.setattr(settings, "RUN_PSYCHOMETRIC_TESTS", True)

    stim_dir = tmp_path / "stimuli"
    stim_dir.mkdir()
    lang = "EN"
    lang_lower = lang.lower()
    country = "UK"
    country_lower = country.lower()
    labnum = 1
    city = "city"
    year = 2024

    (stim_dir / f"multipleye_stimuli_experiment_{lang}.xlsx").write_text("x")
    (stim_dir / f"multipleye_comprehension_questions_{lang}.xlsx").write_text("x")
    (
        stim_dir
        / f"multipleye_participant_instructions_{lang_lower}_with_img_paths.csv"
    ).write_text("x")

    config_dir = stim_dir / "config"
    config_dir.mkdir()
    (
        config_dir / f"config_{lang_lower}_{country_lower}_{city}_{labnum}_{year}.py"
    ).write_text("x")
    (
        config_dir
        / f"MultiplEYE_{lang}_{country}_{city}_{labnum}_{year}_lab_configuration.json"
    ).write_text("{}")
    (config_dir / f"stimulus_order_versions_{lang}_{country}_{labnum}.csv").write_text(
        "participant_id,version_number\n001,1\n"
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
    ).write_text("{}")

    sid = "001_EN_UK_1_ET1"
    sess_folder = tmp_path / "sessions" / sid
    sess_folder.mkdir(parents=True)
    logfiles = sess_folder / "logfiles"
    logfiles.mkdir()
    (logfiles / "EXPERIMENT_LOGFILE_001.txt").write_text("x")
    (logfiles / "DATA_LOGFILE_001.txt").write_text("x")
    (logfiles / "GENERAL_LOGFILE_001.txt").write_text("x")
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
        session_identifier=sid,
        session_file_path=sess_folder / "data.edf",
        session_folder_path=sess_folder,
    )
    dc = FakeDataCollection(
        stimulus_dir=stim_dir,
        language="EN",
        country="UK",
        lab_number=1,
        city=city,
        year=year,
        sessions={sid: session},
    )

    with pytest.raises(PreflightError) as exc_info:
        run_preflight_check(dc)
    assert exc_info.value.num_errors == 1
