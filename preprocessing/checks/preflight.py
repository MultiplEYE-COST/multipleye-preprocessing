"""Preflight input file validation for the preprocessing pipeline.

Verifies all required input files exist and are parseable for each session
*before* any processing begins, so that missing files are caught in one
consolidated error instead of triggering mid-loop failures one at a time.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import polars as pl

from ..utils.data_path_utils import _ci_exists, _ci_glob, _ci_resolve
from ..utils.logging import get_logger

logger = get_logger()

# Expected columns for format validation
COMPLETED_STIMULI_COLS = {"stimulus_id", "stimulus_name", "trial_id", "completed"}
QUESTION_ORDER_COLS = {
    "question_order_version",
    "local_question_1",
    "local_question_2",
    "bridging_question_1",
    "bridging_question_2",
    "global_question_1",
    "global_question_2",
}


class PreflightError(Exception):
    """Raised with ALL preflight failures consolidated."""

    def __init__(self, groups: dict[str, list[str]]) -> None:
        self.groups = groups
        self.num_errors = sum(len(v) for v in groups.values())
        self._message = _format_message(groups)
        super().__init__(self._message)

    def __str__(self) -> str:
        return self._message


def _print_warnings(warnings: dict[str, list[str]]) -> None:
    """Print a prominent warnings-only banner to stderr."""
    n_total = sum(len(v) for v in warnings.values())
    lines: list[str] = [
        f"\n{'=' * 56}",
        f"  Preflight check \u2014 {n_total} warning(s)",
        f"{'=' * 56}",
    ]

    shared_labels = [
        "Stimulus definition xlsx",
        "Comprehension questions xlsx",
        "Participant instructions CSV",
        "Config python file",
        "Lab configuration JSON",
        "Stimulus order versions CSV",
        "Metadata form JSON",
    ]
    for label in shared_labels:
        if label not in warnings:
            continue
        for path in warnings[label]:
            lines.append(f"\n  {label} not found:\n      {os.path.relpath(path)}")

    for label in list(warnings.keys()):
        if label.startswith("Image folder:"):
            for path in warnings[label]:
                lines.append(f"\n  {label} not found:\n      {os.path.relpath(path)}")

    if "Psychometric tests" in warnings:
        for msg in warnings["Psychometric tests"]:
            lines.append(f"\n  {msg}")

    if "Session completeness" in warnings:
        for msg in warnings["Session completeness"]:
            lines.append(f"\n  {msg}")

    print("\n".join(lines), file=sys.stderr)


def run_preflight_check(data_collection) -> None:
    """Verify all required input files exist for the data collection.

    Checks EDF files, logfiles, CSVs, and stimulus definition files
    across all included sessions.

    Flaky files (those that may legitimately be absent) are logged as
    warnings.  Hard-required files raise ``PreflightError`` with ALL
    failures consolidated in a file-type-grouped message.

    Parameters
    ----------
    data_collection : MultipleyeDataCollection | MeridDataCollection
        A data-collection instance whose ``.sessions`` dict is populated.
    """
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    _check_shared_files(data_collection, errors, warnings)
    _check_skipped_sessions(data_collection, errors)
    _check_sessions(data_collection, errors)
    _check_stimulus_order_coverage(data_collection, errors)
    _check_session_completeness(data_collection, warnings)

    pt_warnings: list[str] = []
    _check_psychometric_tests(data_collection, pt_warnings)

    if errors:
        raise PreflightError(errors)

    if pt_warnings:
        warnings["Psychometric tests"] = pt_warnings
    if warnings:
        _print_warnings(warnings)
        return

    logger.info(
        f"\n{'=' * 56}\n  Preflight check \u2014 all input files found\n{'=' * 56}"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_file(path: Path, label: str, groups: dict[str, list[str]]) -> None:
    """Record a missing file or directory (case-insensitive existence check)."""
    if not _ci_exists(path):
        groups.setdefault(label, []).append(str(path))


def _require_glob(
    directory: Path,
    pattern: str,
    label: str,
    groups: dict[str, list[str]],
) -> None:
    """Record if no files match a glob pattern (case-insensitive)."""
    if not _ci_glob(directory, pattern):
        groups.setdefault(label, []).append(str(directory / pattern))


def _find_archives(directory: Path) -> list[str]:
    """Find common archive files in the given directory."""
    patterns = ["*.zip", "*.tar.gz", "*.tar", "*.tgz", "*.7z", "*.rar"]
    archives: list[str] = []
    for pattern in patterns:
        for p in _ci_glob(directory, pattern):
            archives.append(p.name)
    return archives


def _stim_dir_empty_check(stim_dir: Path, groups: dict[str, list[str]]) -> bool:
    """Check the stimulus directory is usable.

    Returns True if usable, False if missing or empty
    (caller can skip further shared-file checks).
    """
    if not _ci_exists(stim_dir):
        groups.setdefault("Stimulus folder", []).append(
            f"Stimulus folder does not exist: {stim_dir}"
        )
        return False

    try:
        entries = [e for e in os.listdir(stim_dir) if not e.startswith(".")]
    except OSError:
        entries = []

    if not entries:
        msg = f"Stimulus folder is empty: {stim_dir}"
        archives = _find_archives(stim_dir.parent)
        if archives:
            archive_list = ", ".join(sorted(archives))
            msg += (
                f"\n  Found archive(s) in parent directory: {archive_list}"
                f"\n  Extract the archive into the stimulus folder first."
            )
        groups.setdefault("Stimulus folder", []).append(msg)
        return False

    return True


def _check_shared_files(
    data_collection,
    errors: dict[str, list[str]],
    warnings: dict[str, list[str]] | None = None,
) -> None:
    """Check files that are shared across all sessions (data-collection level)."""
    from ..config import settings

    # Preflight always validates the input data/ folder, never the
    # preprocessed_data/ output copy.  Fall back to stimulus_dir only for
    # test/demo contexts that lack a real data_collection_name.
    dcn_name = getattr(data_collection, "data_collection_name", None)
    if dcn_name:
        stim_dir = settings.DATASET_DIR / f"stimuli_{dcn_name}"
    else:
        stim_dir = data_collection.stimulus_dir.resolve()
    lang = data_collection.language
    country = data_collection.country
    labnum = data_collection.lab_number
    city = data_collection.city
    year = data_collection.year

    # --- Stimulus directory empty check -----------------------------------
    if not _stim_dir_empty_check(stim_dir, errors):
        return

    # --- Stimulus definition files (errors) -------------------------------
    _require_file(
        stim_dir / f"multipleye_stimuli_experiment_{lang}.xlsx",
        "Stimulus definition xlsx",
        errors,
    )
    _require_file(
        stim_dir / f"multipleye_comprehension_questions_{lang}.xlsx",
        "Comprehension questions xlsx",
        errors,
    )
    _require_file(
        stim_dir / f"multipleye_participant_instructions_{lang}_with_img_paths.csv",
        "Participant instructions CSV",
        errors,
    )

    # --- Config folder (errors) -------------------------------------------
    config_dir = stim_dir / "config"
    _require_glob(
        config_dir,
        f"config_{lang}_{country}_*_{labnum}_*.py",
        "Config python file",
        errors,
    )
    _require_file(
        config_dir
        / f"MultiplEYE_{lang}_{country}_{city}_{labnum}_{year}_lab_configuration.json",
        "Lab configuration JSON",
        errors,
    )
    _require_file(
        config_dir / f"stimulus_order_versions_{lang}_{country}_{labnum}.csv",
        "Stimulus order versions CSV",
        errors,
    )

    # --- Image/AOI folders (errors) ---------------------------------------
    for folder_name in [
        f"stimuli_images_{lang}_{country}_{labnum}",
        f"aoi_stimuli_{lang}_{country}_{labnum}",
        f"question_images_{lang}_{country}_{labnum}",
        f"participant_instructions_images_{lang}_{country}_{labnum}",
    ]:
        _require_file(stim_dir / folder_name, f"Image folder: {folder_name}", errors)

    # --- Image/AOI folders (warnings — flaky, code handles absence) -------
    _warnings = warnings or {}
    for folder_name in [
        f"aoi_stimuli_images_{lang}_{country}_{labnum}",
        f"aoi_question_images_{lang}_{country}_{labnum}",
    ]:
        _require_file(stim_dir / folder_name, f"Image folder: {folder_name}", _warnings)

    # --- Documentation folder (warning — flaky, code handles absence) -----
    doc_dir = stim_dir.parent / "documentation"
    _require_file(
        doc_dir
        / f"MultiplEYE_{lang}_{country}_{city}_{labnum}_{year}_metadata_form.json",
        "Metadata form JSON",
        _warnings,
    )


def _check_skipped_sessions(data_collection, groups: dict[str, list[str]]) -> None:
    """Record sessions that were skipped during discovery (missing EDF)."""
    skipped: list[str] = getattr(data_collection, "skipped_session_ids", [])
    if skipped:
        groups["EDF data file"] = sorted(skipped)


def _check_sessions(data_collection, groups: dict[str, list[str]]) -> None:
    """Run per-session input file checks."""
    for session in data_collection.sessions.values():
        sid = session.session_identifier

        # 1. EDF data file
        if not _ci_exists(session.session_file_path):
            groups.setdefault("EDF data file", []).append(sid)

        # 2. Logfiles folder
        logfiles: Path = session.session_folder_path / "logfiles"
        if not _ci_exists(logfiles):
            groups.setdefault("Logfiles folder", []).append(sid)
            continue

        # 3. EXPERIMENT_*.txt
        experiment_logs = _ci_glob(logfiles, "EXPERIMENT_*.txt")
        if len(experiment_logs) == 0:
            groups.setdefault("EXPERIMENT_*.txt", []).append(sid)
        elif len(experiment_logs) > 1:
            groups.setdefault("Multiple EXPERIMENT_*.txt logfiles", []).append(
                f"{sid} ({len(experiment_logs)} files)"
            )

        # 4. GENERAL_LOGFILE_*.txt
        general_logs = _ci_glob(logfiles, "GENERAL_LOGFILE_*.txt")
        if len(general_logs) == 0:
            groups.setdefault("GENERAL_LOGFILE_*.txt", []).append(sid)

        # 5. completed_stimuli.csv
        _check_parseable_csv(
            logfiles / "completed_stimuli.csv",
            "completed_stimuli.csv",
            groups,
            sid,
            COMPLETED_STIMULI_COLS,
        )

        # 6. question_order_versions.csv
        _check_parseable_csv(
            logfiles / "question_order_versions.csv",
            "question_order_versions.csv",
            groups,
            sid,
            QUESTION_ORDER_COLS,
        )


def _check_parseable_csv(
    path: Path,
    label: str,
    groups: dict[str, list[str]],
    sid: str,
    required_cols: set[str],
) -> None:
    """Check a CSV exists, is parseable, and has the expected columns (case-insensitive)."""
    if not _ci_exists(path):
        groups.setdefault(label, []).append(f"{sid} (missing)")
        return

    try:
        df = pl.read_csv(_ci_resolve(path), infer_schema_length=0)
    except Exception as e:
        groups.setdefault(label, []).append(f"{sid} ({e})")
        return

    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        groups.setdefault(label, []).append(
            f"{sid} (missing columns: {', '.join(sorted(missing_cols))})"
        )


def _check_stimulus_order_coverage(
    data_collection,
    groups: dict[str, list[str]],
) -> None:
    """Check that every session's participant ID is present in the stimulus order versions CSV.

    Detects missing and duplicate participant IDs, which would cause
    ``_load_session_stimulus_order`` to fail mid-pipeline.
    """
    from ..config import settings
    from ..models.sid import Sid

    # Resolve the *source* stimulus dir (same logic as _check_shared_files)
    # Preflight always validates the input data/ folder, never the
    # preprocessed_data/ output copy.  Fall back to stimulus_dir only for
    # test/demo contexts that lack a real data_collection_name.
    dcn_name = getattr(data_collection, "data_collection_name", None)
    if dcn_name:
        source_stim_dir = settings.DATASET_DIR / f"stimuli_{dcn_name}"
    else:
        source_stim_dir = data_collection.stimulus_dir.resolve()

    csv_path = (
        source_stim_dir
        / "config"
        / f"stimulus_order_versions_{data_collection.language}_{data_collection.country}_{data_collection.lab_number}.csv"
    )
    if not _ci_exists(csv_path):
        return  # already reported by _check_shared_files

    try:
        df = pl.read_csv(_ci_resolve(csv_path), infer_schema_length=0)
    except Exception:
        return  # already reported by _check_shared_files

    if "participant_id" not in df.columns:
        return  # already reported by _check_shared_files

    # Read non-null participant IDs from the CSV
    csv_pids_raw = df.filter(pl.col("participant_id").is_not_null())[
        "participant_id"
    ].to_list()

    # Check each session's PID
    missing_pids: list[str] = []
    duplicate_pids: list[str] = []
    for session in data_collection.sessions.values():
        try:
            pid = Sid(session.session_identifier).pid
        except (ValueError, TypeError):
            continue

        count = sum(1 for p in csv_pids_raw if str(int(float(p))).zfill(3) == pid)
        if count == 0:
            missing_pids.append(f"{session.session_identifier} (PID {pid})")
        elif count > 1:
            duplicate_pids.append(
                f"{session.session_identifier} (PID {pid}, {count} entries)"
            )

    for entry in missing_pids:
        groups.setdefault("Stimulus order versions coverage", []).append(
            f"{entry} — not found in stimulus_order_versions CSV"
        )
    for entry in duplicate_pids:
        groups.setdefault("Stimulus order versions coverage", []).append(
            f"{entry} — duplicate entries in stimulus_order_versions CSV"
        )


def _check_session_completeness(
    data_collection,
    warnings: dict[str, list[str]],
) -> None:
    """Check that every participant has all expected sessions.

    Groups sessions by base_id (participant + language + country + lab)
    and detects the expected number of sessions from the data pattern.
    Participants with fewer sessions than the maximum observed for any
    participant are reported as warnings.

    Non-pilot sessions only; sessions with non-parseable SIDs are skipped.
    """
    from ..models.sid import Sid

    base_sessions: dict[str, set[int]] = {}
    for session in data_collection.sessions.values():
        if getattr(session, "is_pilot", False):
            continue
        try:
            sid = Sid(session.session_identifier)
        except (ValueError, TypeError):
            continue
        base_sessions.setdefault(sid.base_id, set()).add(sid.session_id)

    if not base_sessions:
        return

    max_sessions = max(len(v) for v in base_sessions.values())
    if max_sessions <= 1:
        return

    total_participants = len(base_sessions)
    complete = sum(1 for v in base_sessions.values() if len(v) == max_sessions)
    incomplete = [
        f"{base_id} (has session(s): {sorted(session_ids)}, "
        f"missing: ET{','.join(str(s) for s in sorted(set(range(1, max_sessions + 1)) - session_ids))})"
        for base_id, session_ids in sorted(base_sessions.items())
        if len(session_ids) < max_sessions
    ]

    msg = (
        f"Session completeness: {complete}/{total_participants} participants "
        f"have all {max_sessions} expected ET sessions."
    )
    warnings.setdefault("Session completeness", []).append(msg)
    if incomplete:
        warnings["Session completeness"].extend(incomplete)


def _format_message(groups: dict[str, list[str]]) -> str:
    """Transform the grouped error dict into a human-readable message."""
    n_total = sum(len(v) for v in groups.values())
    lines: list[str] = [
        f"\n{'=' * 56}",
        f"  Preflight check FAILED \u2014 {n_total} error(s)",
        f"{'=' * 56}",
    ]

    # Shared files first (data-collection-level, one path per label)
    shared_labels = [
        "Stimulus definition xlsx",
        "Comprehension questions xlsx",
        "Participant instructions CSV",
        "Config python file",
        "Lab configuration JSON",
        "Stimulus order versions CSV",
        "Metadata form JSON",
    ]
    for label in shared_labels:
        if label not in groups:
            continue
        for path in groups[label]:
            lines.append(f"\n  {label} not found:\n      {os.path.relpath(path)}")

    # Image folders and stimulus folder (shared, with dynamic messages)
    for label in list(groups.keys()):
        if label.startswith("Image folder:"):
            for path in groups[label]:
                lines.append(f"\n  {label} not found:\n      {os.path.relpath(path)}")
    if "Stimulus folder" in groups:
        for msg in groups["Stimulus folder"]:
            lines.append(f"\n  {msg}")

    # Per-session file-type groups
    for label in [
        "EDF data file",
        "Logfiles folder",
        "EXPERIMENT_*.txt",
        "Multiple EXPERIMENT_*.txt logfiles",
        "GENERAL_LOGFILE_*.txt",
        "completed_stimuli.csv",
        "question_order_versions.csv",
        "Stimulus order versions coverage",
    ]:
        if label not in groups:
            continue
        entries = groups[label]
        lines.append(f"\n  {label} \u2014 {len(entries)}:")
        for entry in entries:
            lines.append(f"      {entry}")

    # --- Sessions concerned (summary) -------------------------------------
    per_session_labels = [
        "EDF data file",
        "Logfiles folder",
        "EXPERIMENT_*.txt",
        "Multiple EXPERIMENT_*.txt logfiles",
        "GENERAL_LOGFILE_*.txt",
        "completed_stimuli.csv",
        "question_order_versions.csv",
        "Stimulus order versions coverage",
    ]
    sessions_concerned: set[str] = set()
    for label in per_session_labels:
        for entry in groups.get(label, []):
            sid = entry.split(" (")[0]
            sessions_concerned.add(sid)
    if sessions_concerned:
        lines.append(
            f"\n  Sessions concerned: {', '.join(f"'{s}'" for s in sorted(sessions_concerned))}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Psychometric tests
# ---------------------------------------------------------------------------


def _check_psychometric_tests(
    data_collection,
    pt_warnings: list[str],
) -> None:
    """Check psychometric tests data availability (warn-only).

    Detects the format of psychometric test data and auto-restructures if
    task-first format is found.
    All issues are appended to *pt_warnings*: the batch processing has its own logging.
    """
    from ..config import settings

    if not settings.RUN_PSYCHOMETRIC_TESTS:
        return

    pt_dir = settings.PSYCHOMETRIC_TESTS_DIR
    lang = data_collection.language
    country = data_collection.country
    lab = str(data_collection.lab_number)
    test_names = set(settings.PSYCHOMETRIC_TEST_MAPPING.values())

    if not pt_dir.exists():
        pt_warnings.append(
            f"No 'psychometric-tests-sessions' folder found at {pt_dir}. "
            "Psychometric tests stage will be skipped."
        )
        return

    if _detect_session_first(pt_dir, test_names):
        _validate_session_first(pt_dir, test_names, pt_warnings)
        return

    for base in [pt_dir, pt_dir / "core_data"]:
        config_path = base / f"participant_configs_{lang}_{country}_{lab}"
        data_path = base / f"psychometric_test_{lang}_{country}_{lab}"

        if config_path.exists() and data_path.exists():
            logger.info(
                f"Task-first psychometric test data found at {data_path}. "
                f"Auto-restructuring to {pt_dir}..."
            )
            try:
                from ..scripts.restructure_psycho_tests import (
                    fix_psycho_tests_structure,
                )

                fix_psycho_tests_structure(config_path, data_path)
                logger.info("Psychometric tests restructured to session-first format.")
            except Exception as e:
                pt_warnings.append(
                    f"Auto-restructuring psychometric tests failed: {e}. "
                    "You can run 'restructure_psychometric_tests' CLI manually."
                )
            return

    archives = _find_archives(pt_dir)
    if archives:
        pt_warnings.append(
            f"Archives found in {pt_dir}: {', '.join(archives)}. "
            "Please unzip the psychometric test data and place it in the expected structure:\n"
            f"  {pt_dir}/psychometric_test_{lang}_{country}_{lab}/\n"
            f"    PLAB/{{sid}}/...\n"
            f"    RAN/{{sid}}/...\n"
            f"    Stroop_Flanker/{{sid}}/...\n"
            f"    WMC/{{sid}}/...\n"
            f"    WikiVocab/{{sid}}/...\n"
            f"  {pt_dir}/participant_configs_{lang}_{country}_{lab}/\n"
            f"    {{sid}}.yaml"
        )
        return

    pt_warnings.append(
        f"No recognizable psychometric test data found in {pt_dir}. "
        "Psychometric tests stage will be skipped."
    )


def _detect_session_first(pt_dir: Path, test_names: set[str]) -> bool:
    """Check if *pt_dir* contains session-first (restructured) data.

    A folder counts as session-first if its name is SID-compliant and it
    contains at least one test subfolder (PLAB, RAN, etc.).
    """
    from ..models.sid import Sid

    for child in pt_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            Sid(child.name)
        except (ValueError, TypeError):
            continue
        try:
            for sub in child.iterdir():
                if sub.is_dir() and sub.name in test_names:
                    return True
        except OSError:
            continue
    return False


def _validate_session_first(
    pt_dir: Path,
    test_names: set[str],
    pt_warnings: list[str],
) -> None:
    """Warn-only validation of session-first psychometric test data."""
    for child in sorted(pt_dir.iterdir()):
        if not child.is_dir():
            continue
        has_test_subfolder = any((child / t).is_dir() for t in test_names)
        if not has_test_subfolder:
            continue

        config_files = list(child.glob("*.yaml"))
        if not config_files:
            pt_warnings.append(
                f"Session folder '{child.name}' has no YAML config file."
            )

        for test_name in sorted(test_names):
            if not (child / test_name).is_dir():
                pt_warnings.append(
                    f"Session folder '{child.name}' is missing test folder: {test_name}"
                )
