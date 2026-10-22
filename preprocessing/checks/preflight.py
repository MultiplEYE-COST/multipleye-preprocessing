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

from ..config import settings
from ..data_collection.session import Session
from ..models.sid import Sid
from ..utils.data_path_utils import _ci_exists, _ci_glob, _ci_resolve
from ..utils.logging import get_logger
from ..utils.pq_normalisation import find_questionnaire_files

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
                lines.append(f"  {label} not found:\n      {os.path.relpath(path)}")

        if label == "EDF data file":
            for sid in warnings[label]:
                lines.append(f"\n {label} not found in {sid}")

    if "Psychometric tests" in warnings:
        for msg in warnings["Psychometric tests"]:
            lines.append(f"\n  {msg}")

    if "Session completeness" in warnings:
        for msg in warnings["Session completeness"]:
            lines.append(f"\n  {msg}")

    if "Doc sheet evaluation" in warnings:
        for msg in warnings["Doc sheet evaluation"]:
            lines.append(f"\n  {msg}")

    if "Participant questionnaire" in warnings:
        for msg in warnings["Participant questionnaire"]:
            lines.append(f"\n  {msg}")

    lines.append(f"{'=' * 56}")
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
    _check_pq_assets(data_collection, errors, warnings)
    _check_sessions(data_collection, errors, warnings)
    _check_stimulus_order_coverage(data_collection, errors)
    _check_session_completeness(data_collection, warnings)
    _check_stimulus_versions(data_collection, errors)
    if data_collection.experimenter_doc:
        _check_doc_sheet_pids(data_collection, warnings)
    else:
        warnings.setdefault("Doc sheet evaluation", []).append(
            "No experimenter documentation sheet found. If this is a full data collection, please reach out to the lab!"
        )

    pt_warnings: list[str] = []
    _check_psychometric_tests(data_collection, pt_warnings)

    if errors:
        data_collection.preflight_errors = errors
        data_collection.preflight_warnings = warnings
        raise PreflightError(errors)

    if pt_warnings:
        warnings["Psychometric tests"] = pt_warnings
    data_collection.preflight_errors = errors
    data_collection.preflight_warnings = warnings
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


def _check_sessions(
    data_collection, errors: dict[str, list[str]], warnings: dict[str, list[str]]
) -> None:
    """Run per-session input file checks."""
    for session in data_collection.sessions.values():
        _check_single_session(session, skipped=False, errors=errors, warnings=warnings)

    for session in data_collection.skipped_sessions.values():
        _check_single_session(session, skipped=True, errors=errors, warnings=warnings)


def _check_single_session(
    session: Session,
    skipped: bool,
    errors: dict[str, list[str]],
    warnings: dict[str, list[str]],
):
    sid = session.session_identifier

    # 1. EDF data file
    if skipped:
        warnings.setdefault("EDF data file", []).append(sid)
    else:
        if not _ci_exists(session.session_file_path):
            errors.setdefault("EDF data file", []).append(sid)

    # 2. Logfiles folder
    logfiles: Path = session.session_folder_path / "logfiles"
    if not _ci_exists(logfiles):
        errors.setdefault("Logfiles folder", []).append(sid)
        return

    # 3. EXPERIMENT_*.txt
    experiment_logs = _ci_glob(logfiles, "EXPERIMENT_*.txt")
    if len(experiment_logs) == 0:
        errors.setdefault("EXPERIMENT_*.txt", []).append(sid)
    elif len(experiment_logs) > 1:
        errors.setdefault("Multiple EXPERIMENT_*.txt logfiles", []).append(
            f"{sid} ({len(experiment_logs)} files)"
        )

    # 4. DATA_LOGFILE_*.txt
    data_logs = _ci_glob(logfiles, "DATA_LOGFILE_*.txt")
    if len(data_logs) == 0:
        errors.setdefault("DATA_LOGFILE_*.txt", []).append(sid)
    elif len(data_logs) > 1:
        errors.setdefault("Multiple DATA_LOGFILE_*.txt logfiles", []).append(
            f"{sid} ({len(data_logs)} files)"
        )

    # 5. GENERAL_LOGFILE_*.txt
    general_logs = _ci_glob(logfiles, "GENERAL_LOGFILE_*.txt")
    if len(general_logs) == 0:
        errors.setdefault("GENERAL_LOGFILE_*.txt", []).append(sid)
    elif len(general_logs) > 1:
        errors.setdefault("Multiple GENERAL_LOGFILE_*.txt logfiles", []).append(
            f"{sid} ({len(general_logs)} files)"
        )

    # 6. completed_stimuli.csv
    _check_parseable_csv(
        logfiles / "completed_stimuli.csv",
        "completed_stimuli.csv",
        errors,
        sid,
        COMPLETED_STIMULI_COLS,
    )

    # 7. question_order_versions.csv
    _check_parseable_csv(
        logfiles / "question_order_versions.csv",
        "question_order_versions.csv",
        errors,
        sid,
        QUESTION_ORDER_COLS,
    )

    # 8. participant questionnaire file
    sid = Sid(sid)
    path = session.session_folder_path / f"{sid.base_id}_pq_data.json"
    if not _ci_exists(path):
        warnings.setdefault("Participant questionnaire", []).append(
            f"Participant questionnaire JSON missing for {sid!s}"
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
    """Check that every session's participant ID is present in its stimulus order versions CSV.

    The CSV is resolved per session content version, so participants assigned to
    a versioned stimulus folder are checked against that folder's CSV. Detects
    missing and duplicate participant IDs, which would cause
    ``_load_session_stimulus_order`` to fail mid-pipeline.
    """
    from ..config import settings
    from ..models.sid import Sid
    from ..utils.stimulus_versions import (
        stimulus_folder_name,
        version_dir,
        version_suffix_for_pid,
    )

    # Resolve the *source* stimulus dir (same logic as _check_shared_files).
    # Preflight always validates the input data/ folder, never the
    # preprocessed_data/ output copy. Fall back to stimulus_dir only for
    # test/demo contexts that lack a real data_collection_name.
    dcn_name = getattr(data_collection, "data_collection_name", None)
    if dcn_name:
        base_stim_dir = settings.DATASET_DIR / stimulus_folder_name(dcn_name, None)
    else:
        base_stim_dir = data_collection.stimulus_dir.resolve()

    order_csv_name = (
        f"stimulus_order_versions_{data_collection.language}_"
        f"{data_collection.country}_{data_collection.lab_number}.csv"
    )

    # Group sessions by their resolved version dir so each CSV is read once.
    sessions_by_dir: dict[Path, list[tuple[str, str]]] = {}
    for session in data_collection.sessions.values():
        try:
            pid = Sid(session.session_identifier).pid
        except (ValueError, TypeError):
            continue
        vdir = version_dir(base_stim_dir, version_suffix_for_pid(pid))
        sessions_by_dir.setdefault(vdir, []).append((session.session_identifier, pid))

    for vdir, entries in sessions_by_dir.items():
        csv_path = vdir / "config" / order_csv_name
        if not _ci_exists(csv_path):
            continue  # already reported by _check_shared_files / _check_stimulus_versions
        try:
            df = pl.read_csv(_ci_resolve(csv_path), infer_schema_length=0)
        except Exception:
            continue  # already reported elsewhere
        if "participant_id" not in df.columns:
            continue

        csv_pids_raw = df.filter(pl.col("participant_id").is_not_null())[
            "participant_id"
        ].to_list()
        normalized = [str(int(float(p))).zfill(3) for p in csv_pids_raw]

        for session_identifier, pid in entries:
            count = normalized.count(pid)
            if count == 0:
                groups.setdefault("Stimulus order versions coverage", []).append(
                    f"{session_identifier} (PID {pid}) — not found in "
                    "stimulus_order_versions CSV"
                )
            elif count > 1:
                groups.setdefault("Stimulus order versions coverage", []).append(
                    f"{session_identifier} (PID {pid}, {count} entries) — duplicate "
                    "entries in stimulus_order_versions CSV"
                )


def _check_session_completeness(
    data_collection,
    warnings: dict[str, list[str]],
) -> None:
    """Warn when participants do not have the expected number of ET sessions.

    Groups sessions by base_id (participant + language + country + lab). The
    expected number of sessions per participant comes from the data collection's
    ``num_sessions`` (1 for MultiplEYE, 2 for MeRID). Participants with fewer
    sessions are reported as missing; participants with more sessions than
    expected are also reported, since extra sessions per participant are not the
    MeRID multi-session format.

    Non-pilot sessions only; sessions with non-parseable SIDs are skipped.
    """
    from ..models.sid import Sid

    expected_sessions = getattr(data_collection, "num_sessions", 1) or 1

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

    max_observed = max(len(v) for v in base_sessions.values())
    has_extra = max_observed > expected_sessions
    if expected_sessions <= 1 and not has_extra:
        return

    total_participants = len(base_sessions)
    complete = sum(1 for ids in base_sessions.values() if len(ids) == expected_sessions)
    incomplete = [
        f"{base_id} (has session(s): {sorted(session_ids)}, "
        f"missing: ET{','.join(str(s) for s in sorted(set(range(1, expected_sessions + 1)) - session_ids))})"
        for base_id, session_ids in sorted(base_sessions.items())
        if len(session_ids) < expected_sessions
    ]
    extra = [
        f"{base_id} (has session(s): {sorted(session_ids)}, "
        f"expected: {expected_sessions}) — more sessions than expected; "
        f"check the `experiment_type` config setting"
        for base_id, session_ids in sorted(base_sessions.items())
        if len(session_ids) > expected_sessions
    ]

    msg = (
        f"Session completeness: {complete}/{total_participants} participants "
        f"have all {expected_sessions} expected ET sessions."
    )
    warnings.setdefault("Session completeness", []).append(msg)
    if incomplete:
        warnings["Session completeness"].extend(incomplete)
    if extra:
        warnings["Session completeness"].extend(extra)


def _check_pq_assets(
    data_collection,
    errors: dict[str, list[str]],
    warnings: dict[str, list[str]],
) -> None:
    """Check the participant questionnaire workbooks are available.

    Only applies to real MultiplEYE data collections. MeRID and test fixtures do
    not use the participant questionnaire.
    """
    if getattr(settings, "EXPERIMENT_TYPE", "") == "MeRID":
        return
    if not getattr(data_collection, "data_collection_name", None):
        return

    dataset_dir = Path(settings.DATASET_DIR)
    language = getattr(data_collection, "language", None)
    if not language:
        return

    question_path, language_path = find_questionnaire_files(dataset_dir, language)
    allow_fallback = bool(getattr(settings, "ALLOW_PQ_FALLBACK", False))
    target = warnings if allow_fallback else errors
    group = "Participant questionnaire"
    lang = str(language).lower()

    if question_path is None:
        target.setdefault(group, []).append(
            "Questionnaire workbook not found. Place "
            f"multipleye_questionnaire_questions_{lang}.xlsx in the data "
            f"collection folder (for example "
            f"{dataset_dir}/participant_questionnaire_{lang}_*/) or in "
            f"{dataset_dir}/documentation/questionnaire/."
        )
    if language_path is None:
        target.setdefault(group, []).append(
            "Language-code workbook not found. Place "
            f"language_iso639_1_{lang}.xlsx next to the questionnaire "
            "workbook."
        )


def _check_doc_sheet_pids(
    data_collection,
    warnings: dict[str, list[str]],
) -> None:

    experimenter_doc = data_collection.experimenter_doc
    if experimenter_doc is None or experimenter_doc.et_frame is None:
        return

    session_ids = [
        session.participant_id for session in data_collection.sessions.values()
    ]

    valid_ids, invalid_ids = experimenter_doc.get_pids(sheet="et")
    missing_ids = [pid for pid in valid_ids if pid not in session_ids]

    if not (invalid_ids or missing_ids):
        return

    warnings.setdefault("Doc sheet evaluation", []).append(
        "Experimenter doc sheet eval of ET participant IDs: "
        f"{len(invalid_ids)} could not be converted to integers, "
        f"{len(missing_ids)} have no corresponding ET session."
    )

    for pid in missing_ids:
        warnings["Doc sheet evaluation"].append(
            f"Participant {pid:03} in documentation sheet not in session data. Please check!"
        )

    for invalid_id in invalid_ids:
        warnings["Doc sheet evaluation"].append(
            f"Participant ID {invalid_id} in the Experimenter documentation sheet could not be converted to an integer. Impossible to verify whether session data exists."
        )


def _check_stimulus_versions(
    data_collection,
    groups: dict[str, list[str]],
) -> None:
    """Check configured stimulus content version folders exist and cover sessions.

    Only active when ``stimulus_versions`` is configured.  Verifies that every
    versioned stimulus folder (``stimuli_<dcn>_<suffix>``) exists next to the
    default folder, that each contains its ``stimulus_order_versions_*.csv``, and
    that every session PID assigned to a version is present in that version's CSV.
    """
    from ..config import settings
    from ..models.sid import Sid
    from ..utils.stimulus_versions import version_dir, version_suffix_for_pid

    pid_map = settings.STIMULUS_VERSIONS_PID_MAP or {}
    if not pid_map:
        return

    # Resolve the *source* stimulus dir (same logic as _check_shared_files).
    dcn_name = getattr(data_collection, "data_collection_name", None)
    if dcn_name:
        source_stim_dir = settings.DATASET_DIR / f"stimuli_{dcn_name}"
    else:
        source_stim_dir = data_collection.stimulus_dir.resolve()

    lang = data_collection.language
    country = data_collection.country
    labnum = data_collection.lab_number
    order_csv_name = f"stimulus_order_versions_{lang}_{country}_{labnum}.csv"

    # Only versions that a session is actually mapped to need to be present.
    # Unused configured versions are not prepared (see prepare_language_folder),
    # so requiring their folder here would be a false error.
    needed_versions: set[str] = set()
    session_ids = list(data_collection.sessions.keys()) + list(
        getattr(data_collection, "skipped_sessions", {}).keys()
    )
    for session_id in session_ids:
        try:
            pid = Sid(session_id).pid
        except (ValueError, TypeError):
            continue
        suffix = version_suffix_for_pid(pid)
        if suffix is not None:
            needed_versions.add(suffix)

    version_dirs: dict[str, Path] = {}
    for version in sorted(needed_versions):
        vdir = version_dir(source_stim_dir, version)
        version_dirs[version] = vdir
        if not _ci_exists(vdir):
            groups.setdefault("Stimulus versions", []).append(
                f"Stimulus folder for version '{version}' does not exist: {vdir}"
            )
            continue
        _require_file(
            vdir / "config" / order_csv_name,
            "Stimulus versions",
            groups,
        )

    # Every session PID mapped to a version must appear in that version's CSV.
    for session in data_collection.sessions.values():
        try:
            pid = Sid(session.session_identifier).pid
        except (ValueError, TypeError):
            continue
        version = version_suffix_for_pid(pid)
        if version is None:
            continue
        vdir = version_dirs.get(version)
        csv_path = vdir / "config" / order_csv_name
        if not _ci_exists(csv_path):
            continue  # already reported above
        try:
            df = pl.read_csv(_ci_resolve(csv_path), infer_schema_length=0)
        except Exception:
            continue  # already reported above
        if "participant_id" not in df.columns:
            continue
        csv_pids = df.filter(pl.col("participant_id").is_not_null())[
            "participant_id"
        ].to_list()
        normalized = {str(int(float(p))).zfill(3) for p in csv_pids}
        if pid not in normalized:
            groups.setdefault("Stimulus versions", []).append(
                f"{session.session_identifier} (PID {pid}) — not found in "
                f"stimulus_order_versions CSV for version '{version}'"
            )


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
        "DATA_LOGFILE_*.txt",
        "Multiple DATA_LOGFILE_*.txt logfiles",
        "GENERAL_LOGFILE_*.txt",
        "Multiple GENERAL_LOGFILE_*.txt logfiles",
        "completed_stimuli.csv",
        "question_order_versions.csv",
        "Stimulus order versions coverage",
        "Stimulus versions",
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
        "DATA_LOGFILE_*.txt",
        "Multiple DATA_LOGFILE_*.txt logfiles",
        "GENERAL_LOGFILE_*.txt",
        "Multiple GENERAL_LOGFILE_*.txt logfiles",
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
                from ..scripts.restructure_psychometric_tests import (
                    fix_psychometric_tests_structure,
                )

                fix_psychometric_tests_structure(config_path, data_path)
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
