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

    if errors:
        combined = {}
        combined.update(warnings)
        combined.update(errors)
        raise PreflightError(combined)

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
    """Record a missing file or directory."""
    if not path.exists():
        groups.setdefault(label, []).append(str(path))


def _require_glob(
    directory: Path,
    pattern: str,
    label: str,
    groups: dict[str, list[str]],
) -> None:
    """Record if no files match a glob pattern in the given directory."""
    if not list(directory.glob(pattern)):
        groups.setdefault(label, []).append(str(directory / pattern))


def _check_shared_files(
    data_collection,
    errors: dict[str, list[str]],
    warnings: dict[str, list[str]] | None = None,
) -> None:
    """Check files that are shared across all sessions (data-collection level)."""
    stim_dir = data_collection.stimulus_dir
    lang = data_collection.language
    country = data_collection.country
    labnum = data_collection.lab_number
    city = data_collection.city
    year = data_collection.year

    lang_lower = lang.lower()
    country_lower = country.lower()

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
        stim_dir
        / f"multipleye_participant_instructions_{lang_lower}_with_img_paths.csv",
        "Participant instructions CSV",
        errors,
    )

    # --- Config folder (errors) -------------------------------------------
    config_dir = stim_dir / "config"
    _require_glob(
        config_dir,
        f"config_{lang_lower}_{country_lower}_*_{labnum}_*.py",
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
        f"stimuli_images_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_stimuli_{lang_lower}_{country_lower}_{labnum}",
        f"question_images_{lang_lower}_{country_lower}_{labnum}",
        f"participant_instructions_images_{lang_lower}_{country_lower}_{labnum}",
    ]:
        _require_file(stim_dir / folder_name, f"Image folder: {folder_name}", errors)

    # --- Image/AOI folders (warnings — flaky, code handles absence) -------
    _warnings = warnings or {}
    for folder_name in [
        f"aoi_stimuli_images_{lang_lower}_{country_lower}_{labnum}",
        f"aoi_question_images_{lang_lower}_{country_lower}_{labnum}",
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
        if not session.session_file_path.exists():
            groups.setdefault("EDF data file", []).append(sid)

        # 2. Logfiles folder
        logfiles: Path = session.session_folder_path / "logfiles"
        if not logfiles.exists():
            groups.setdefault("Logfiles folder", []).append(sid)
            continue

        # 3. EXPERIMENT_*.txt
        experiment_logs = list(logfiles.glob("EXPERIMENT_*.txt"))
        if len(experiment_logs) == 0:
            groups.setdefault("EXPERIMENT_*.txt", []).append(sid)

        # 4. GENERAL_LOGFILE_*.txt
        general_logs = list(logfiles.glob("GENERAL_LOGFILE_*.txt"))
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
    """Check a CSV exists, is parseable, and has the expected columns."""
    if not path.exists():
        groups.setdefault(label, []).append(f"{sid} (missing)")
        return

    try:
        df = pl.read_csv(path, infer_schema_length=0)
    except Exception as e:
        groups.setdefault(label, []).append(f"{sid} ({e})")
        return

    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        groups.setdefault(label, []).append(
            f"{sid} (missing columns: {', '.join(sorted(missing_cols))})"
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

    # Image folders (shared, but with dynamic names)
    for label in list(groups.keys()):
        if label.startswith("Image folder:"):
            for path in groups[label]:
                lines.append(f"\n  {label} not found:\n      {os.path.relpath(path)}")

    # Per-session file-type groups
    for label in [
        "EDF data file",
        "Logfiles folder",
        "EXPERIMENT_*.txt",
        "GENERAL_LOGFILE_*.txt",
        "completed_stimuli.csv",
        "question_order_versions.csv",
    ]:
        if label not in groups:
            continue
        entries = groups[label]
        lines.append(f"\n  {label} \u2014 {len(entries)}:")
        for entry in entries:
            lines.append(f"      {entry}")

    return "\n".join(lines)
