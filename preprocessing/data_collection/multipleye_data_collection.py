import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path

import pandas as pd
import polars as pl
import pymovements as pm
import yaml
from polars.exceptions import ComputeError
from tqdm import tqdm

from preprocessing.scripts.prepare_language_folder import (
    extract_stimulus_version_number_from_asc,
)

from ..checks.et_quality_checks import (
    check_comprehension_question_answers,
    check_metadata,
    check_validation_requirements,
)
from ..checks.et_quality_checks import (
    report_to_file_metadata as report_meta,
)
from ..checks.formal_experiment_checks import (
    check_all_screens_logfile,
    check_messages,
    sanity_check_gaze_frame,
)
from ..config import settings
from ..metadata.codebook import load_codebook_identity
from ..metadata.codebook import write_codebook_outputs as write_codebook_package
from ..models.dcn import Dcn
from ..models.sid import Sid
from ..plotting.plot import build_page_frames, plot_gaze, plot_main_sequence
from ..utils.conversion import convert_to_time_str
from ..utils.data_collection_utils import _report_to_file
from ..utils.data_path_utils import (
    _ci_resolve,
    find_metadata_form,
    load_metadata_form,
)
from ..utils.eye_tracker import (
    CANONICAL_EYE_TRACKERS,
    eye_tracker_brand,
    normalize_eye_tracker_name,
    suggest_eye_tracker_names,
)
from ..utils.logging import get_edf2asc_version, get_logger, get_pipeline_info
from ..utils.pq_normalisation import (
    build_mapping,
    find_pq_data,
    find_questionnaire_files,
    normalise_pq,
)
from ..utils.stimulus_versions import stimulus_folder_name, version_suffix_for_pid
from .experimenter_doc import ExperimenterDoc
from .participant_info import (
    PSYCHOMETRIC_KEY_SCORES,
    _bi_monolingualism_from_pq,
    _psychometric_dates,
    _psychometric_tests_in_folder,
    _session_date_from_logfile,
)
from .session import Session
from .stimulus import LabConfig, Stimulus


def eyelink(method):
    def wrapper(self):
        if self.eye_tracker == "eyelink":
            return method(self)
        else:
            raise ValueError(
                f"Function {method.__name__} is only supported for EyeLink data. "
                f"You are using {self.eye_tracker}"
            )

    return wrapper


def _metadata_form_value(
    metadata_form: dict, section: str, key: str, legacy_key: str
) -> object:
    """Read a nested metadata-form value with a fallback to the flat legacy key.

    Real metadata forms group values into sections (for example
    ``Tested_language.Language_script``), while older/generated forms store
    them as flat keys (``Script``). The nested value wins when it is present.

    Parameters
    ----------
    metadata_form : dict
        Parsed metadata form.
    section : str
        Name of the nested section.
    key : str
        Key within the nested section.
    legacy_key : str
        Flat key used by older/generated forms.

    Returns
    -------
    object
        The nested value, the flat value, or None if neither exists.
    """
    section_data = metadata_form.get(section)
    if isinstance(section_data, dict):
        value = section_data.get(key)
        if value is not None:
            return value
    return metadata_form.get(legacy_key)


def _known_version(value: object) -> str | None:
    """Return a version string, mapping missing and ``unknown`` values to None.

    Parameters
    ----------
    value : object
        Version or revision string from a version helper.

    Returns
    -------
    str | None
        Stripped value, or None when it is missing or reported as ``unknown``.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "unknown":
        return None
    return text


_ANSWER_OPTION_SET_PREFIX = "question_answer_option_shuffling_"
_ANSWER_OPTION_VERSION_REGEX = re.compile(
    r"question_images_version_(\d+)\.json$", re.IGNORECASE
)


def _answer_option_version_from_path(path: Path) -> int | None:
    """Return the question-image version encoded in an option-key filename."""
    match = _ANSWER_OPTION_VERSION_REGEX.search(path.name)
    if match is None:
        return None
    return int(match.group(1))


def _answer_option_session_version(value: object) -> int | None:
    """Return a session's stimulus-order version as an integer, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        match = re.search(r"(\d+)\s*$", value.strip())
        if match is not None:
            return int(match.group(1))
    return None


def _canonical_json_hash(path: Path) -> str | None:
    """Return a stable content hash for a JSON file, or None if it is unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _answer_option_set_files(
    stimulus_dirs: Iterable[Path],
) -> dict[str, list[tuple[Path, int, Path]]]:
    """Discover shuffled option-key files grouped by stimulus set name.

    Parameters
    ----------
    stimulus_dirs : Iterable[Path]
        Stimulus directories used by the collection, including content versions.

    Returns
    -------
    dict[str, list[tuple[Path, int, Path]]]
        Mapping from set directory name to ``(stimulus_dir, version, path)``
        entries. Only files with a parseable version suffix are included.
    """
    entries: dict[str, list[tuple[Path, int, Path]]] = {}
    seen: set[Path] = set()
    for stimulus_dir in stimulus_dirs:
        config_dir = Path(stimulus_dir) / "config"
        if not config_dir.is_dir():
            continue
        for set_dir in sorted(config_dir.glob(f"{_ANSWER_OPTION_SET_PREFIX}*")):
            if not set_dir.is_dir():
                continue
            for path in sorted(set_dir.glob("*.json")):
                version = _answer_option_version_from_path(path)
                if version is None:
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                entries.setdefault(set_dir.name, []).append(
                    (Path(stimulus_dir), version, path)
                )
    return entries


def _compute_answer_option_shuffling_stats(
    sessions: Iterable[object],
    resolve_stimulus_dir: Callable[[str], Path],
    stimulus_dirs: Iterable[Path],
) -> dict[str, object]:
    """Compute the answer-option shuffling check for the DCN overview.

    The session rule uses the option-key file selected by each session's
    ``randomization_version``. ``all_files_identical`` is computed from every
    readable file in the set, including versions not used by a session.

    Parameters
    ----------
    sessions : Iterable[object]
        Non-pilot sessions. Each item must expose ``session_identifier`` and
        ``randomization_version``.
    resolve_stimulus_dir : Callable[[str], Path]
        Resolve a session identifier to its stimulus directory.
    stimulus_dirs : Iterable[Path]
        All stimulus directories, including content versions.

    Returns
    -------
    dict[str, object]
        The ``answer_option_shuffling`` mapping written to the DCN overview.
    """
    files_by_set = _answer_option_set_files(stimulus_dirs)
    records: dict[str, dict[str, object]] = {}
    for set_name, entries in files_by_set.items():
        hash_by_dir_version: dict[tuple[Path, int], str] = {}
        all_hashes: list[str] = []
        for stimulus_dir, version, path in entries:
            digest = _canonical_json_hash(path)
            if digest is None:
                continue
            hash_by_dir_version[(Path(stimulus_dir).resolve(), version)] = digest
            all_hashes.append(digest)
        records[set_name] = {
            "hash_by_dir_version": hash_by_dir_version,
            "all_hashes": all_hashes,
            "session_ids": set(),
            "session_hashes": [],
            "used_versions": set(),
        }

    session_ids: set[str] = set()
    for session in sessions:
        session_id = getattr(session, "session_identifier", None)
        version = _answer_option_session_version(
            getattr(session, "randomization_version", None)
        )
        if not session_id or version is None:
            continue
        stimulus_dir = Path(resolve_stimulus_dir(str(session_id))).resolve()
        for record in records.values():
            digest = record["hash_by_dir_version"].get((stimulus_dir, version))
            if digest is None:
                continue
            record["session_ids"].add(str(session_id))
            record["session_hashes"].append(digest)
            record["used_versions"].add(version)
            session_ids.add(str(session_id))

    sets: dict[str, dict[str, object]] = {}
    num_flagged_sets = 0
    for set_name in sorted(records):
        record = records[set_name]
        session_hashes = record["session_hashes"]
        used_versions = record["used_versions"]
        all_hashes = record["all_hashes"]
        num_sessions = len(record["session_ids"])
        max_identical_sessions = max(Counter(session_hashes).values(), default=0)
        max_identical_share = (
            round(max_identical_sessions / num_sessions, 3) if num_sessions else 0.0
        )
        all_files_identical = len(set(all_hashes)) == 1 if all_hashes else None
        flagged = max_identical_sessions >= 2 and (
            all_files_identical is True or max_identical_share >= 0.5
        )
        if flagged:
            num_flagged_sets += 1
        sets[set_name] = {
            "flagged": flagged,
            "num_sessions": num_sessions,
            "num_versions": len(used_versions),
            "num_unique": len(set(session_hashes)),
            "max_identical_sessions": max_identical_sessions,
            "max_identical_share": max_identical_share,
            "all_files_identical": all_files_identical,
        }

    return {
        "flagged": num_flagged_sets > 0,
        "num_sets": len(sets),
        "num_sessions": len(session_ids),
        "num_flagged_sets": num_flagged_sets,
        "sets": sets,
    }


def _capture_overview_warning(message: str) -> None:
    """Append a warning to the DCN overview warning list."""
    if not hasattr(logging, "_captured_warnings"):
        logging._captured_warnings = []  # type: ignore[attr-defined]
    logging._captured_warnings.append(message)  # type: ignore[attr-defined]


def _compute_session_completeness(data_collection) -> dict:
    """Compute session completeness stats grouped by participant base ID.

    The expected number of sessions per participant is taken from the data
    collection's ``num_sessions`` (1 for MultiplEYE, 2 for MeRID). Participants
    with fewer sessions are listed under ``incomplete_participants``; those with
    more sessions than expected are listed under ``extra_sessions_participants``.

    Returns a dict with keys ``expected_sessions_per_participant``,
    ``total_participants`` and ``complete_participants`` (plus the two optional
    lists above).

    Non-pilot sessions only; sessions with non-parseable SIDs are skipped.
    """
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
        return {
            "expected_sessions_per_participant": expected_sessions,
            "total_participants": 0,
            "complete_participants": 0,
        }

    total = len(base_sessions)
    complete = sum(1 for ids in base_sessions.values() if len(ids) == expected_sessions)

    result: dict = {
        "expected_sessions_per_participant": expected_sessions,
        "total_participants": total,
        "complete_participants": complete,
    }

    incomplete = sorted(
        base_id
        for base_id, ids in base_sessions.items()
        if len(ids) < expected_sessions
    )
    if incomplete:
        result["incomplete_participants"] = incomplete

    extra = sorted(
        base_id
        for base_id, ids in base_sessions.items()
        if len(ids) > expected_sessions
    )
    if extra:
        result["extra_sessions_participants"] = extra

    return result


def _reading_span_ms(start: object, stop: object) -> tuple[int, bool]:
    """Return the duration for a start/stop timestamp pair.

    Reversed or out-of-order timestamps yield ``(0, True)`` so reading times
    never become negative.

    Parameters
    ----------
    start, stop : object
        Timestamps convertible to float (for example millisecond strings).

    Returns
    -------
    tuple[int, bool]
        The non-negative duration in milliseconds and whether it was clamped.
    """
    span_ms = int(float(stop)) - int(float(start))
    if span_ms < 0:
        return 0, True
    return span_ms, False


def _summarize_reading_times(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-page reading-time rows per (stimulus, trial, type).

    Timestamps are cast to numeric before aggregation so ``min``/``max`` are
    numeric. Comparing them as strings gives a wrong range when the timestamp
    string length changes (for example ``"999999"`` vs ``"1000000"``), which can
    make ``stop_ts`` smaller than ``start_ts``.
    """
    sum_df = df[
        ["stimulus", "trial", "type", "duration_ms", "start_ts", "stop_ts"]
    ].dropna()
    sum_df = sum_df.assign(
        duration_ms=sum_df["duration_ms"].astype(float),
        start_ts=sum_df["start_ts"].astype(float),
        stop_ts=sum_df["stop_ts"].astype(float),
    )
    return (
        sum_df.groupby(by=["stimulus", "trial", "type"])
        .agg({"duration_ms": "sum", "start_ts": "min", "stop_ts": "max"})
        .reset_index()
    )


def _build_stimulus_start_end_ts(sum_df: pd.DataFrame) -> list[dict]:
    """Build the per-stimulus reading-time records stored on the session.

    Selects the reading-time rows (excluding the synthetic "time before pages and
    breaks" rows) and keeps ``type`` and ``duration_ms`` alongside ``start_ts``/
    ``stop_ts``. Downstream consumers (e.g. ``Session._compute_rt_per_stim``) need
    ``type`` and ``duration_ms``; dropping them silently breaks those computations.
    """
    records = sum_df[
        ["stimulus", "trial", "type", "duration_ms", "start_ts", "stop_ts"]
    ].dropna()
    records = records[~records["type"].str.contains("time before")]
    return records.to_dict(orient="records")


def _find_experimenter_doc(
    dataset_dir: Path,
    base_name: str,
    language: str,
    country: str,
    city: str,
) -> Path | None:
    """Find the experimenter documentation workbook in ``documentation/``.

    Accepts filenames with and without the lab number, case-insensitively.
    """
    documentation = dataset_dir / "documentation"
    if not documentation.is_dir():
        return None
    prefix = "multipleye_experimenter_session_documentation_"
    candidates = [
        path
        for path in documentation.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".xlsx"
        and path.name.lower().startswith(prefix)
    ]
    wanted = [
        f"{prefix}{base_name}.xlsx".lower(),
        f"{prefix}{language}_{country}_{city}.xlsx".lower(),
    ]
    for target in wanted:
        for path in candidates:
            if path.name.lower() == target:
                return path
    if len(candidates) == 1:
        return candidates[0]
    return None


class MultipleyeDataCollection:
    crashed_session_ids: list[str] = []
    skipped_sessions: dict = {}
    num_sessions = 1
    overview = {}

    data_collection_name: str
    year: int
    country: str
    session_folder_regex: str = ""
    data_root: Path = None
    excluded_sessions: list = []
    type = "MultiplEYE"

    # TODO: read instruction excel

    def __init__(
        self,
        data_collection_name: str,
        stimulus_language: str,
        country: str,
        year: int,
        eye_tracker: str,
        config_file: Path,
        stimulus_dir: Path,
        lab_number: int,
        city: str,
        data_root: Path,
        lab_configuration: LabConfig,
        session_folder_regex: str,
        experimenter_doc: ExperimenterDoc | None = None,
        included_sessions: list[str] | None = None,
        excluded_sessions: list[str] | None = None,
        # stimuli: list[Stimulus],
        **kwargs,
    ):
        self.sessions: dict[str, Session] = {}
        self.skipped_sessions: dict[str, Session] = {}
        self.experimenter_doc = experimenter_doc
        self.preflight_errors: dict[str, list[str]] = {}
        self.preflight_warnings: dict[str, list[str]] = {}
        # TODO: in theory this can be multiple languages for the stimuli..
        self.language = stimulus_language
        self.country = country
        self.year = year
        self.data_collection_name = data_collection_name

        self.include_pilots = kwargs.get("include_pilots", False)
        self.output_dir = kwargs.get("output_dir", "")
        self.pilot_folder = kwargs.get("pilot_folder", "")
        self.reports_folder = "reports"

        canonical_eye_tracker = normalize_eye_tracker_name(eye_tracker)
        if canonical_eye_tracker is None:
            suggestions = suggest_eye_tracker_names(eye_tracker)
            supported = ", ".join(CANONICAL_EYE_TRACKERS)
            message = (
                f"Eye tracker {eye_tracker!r} is not supported. "
                f"Supported models are: {supported}."
            )
            if suggestions:
                message += f" Did you mean: {', '.join(suggestions)}?"
            raise ValueError(message)

        self.eye_tracker_name_raw = str(eye_tracker)
        self.eye_tracker_name = canonical_eye_tracker
        self.eye_tracker = eye_tracker_brand(canonical_eye_tracker)
        self.config_file = config_file
        self.stimulus_dir = stimulus_dir
        self.lab_number = lab_number
        self.city = city
        self.lab_configuration = lab_configuration
        self.data_root = data_root
        self.session_folder_regex = session_folder_regex
        self.psychometric_tests = kwargs.get("psychometric_tests", [])
        self.excluded_sessions = excluded_sessions
        self.included_sessions = included_sessions
        self.pid_stimulus_dirs = kwargs.get("pid_stimulus_dirs", None)
        self.logger = get_logger()

        self.logger.info(
            f"MultipleyeDataCollection initialized. data_root: {self.data_root}"
        )
        self.logger.info(f"Main config loaded from {self.config_file}")

        self.add_recorded_sessions(self.data_root, self.session_folder_regex)

        if len(self.sessions) == 0 and len(self.skipped_sessions) == 0:
            msg = f"No sessions found in {self.data_root}. "
            if self.included_sessions:
                msg += (
                    f"Check if 'include_sessions' {self.included_sessions} is correct. "
                )
            if self.excluded_sessions:
                msg += (
                    f"Check if 'exclude_sessions' {self.excluded_sessions} "
                    "is filtering all available data. "
                )

            msg += "Please check the session_folder_regex and the data_root."
            raise ValueError(msg)

        # load stimulus order versions to know what stimulus randomization was used for
        # each participant
        stim_order_versions = _ci_resolve(
            self.stimulus_dir / "config" / f"stimulus_order_versions_"
            f"{self.language}_{self.country}_{self.lab_number}.csv"
        )
        stim_order_versions = pd.read_csv(stim_order_versions)
        self.stim_order_versions = stim_order_versions

        if self.stim_order_versions.empty:
            warnings.warn(
                "Stimulus order version is not updated with participants numbers.\n"
                "Please ask the team to upload the correct stimulus folder that "
                "has been used and changed during the experiment.\n"
                "Version will be extracted from the asc files."
            )
            self.stim_order_versions = stim_order_versions

        self.overview = self.create_dataset_overview()

    def _resolve_stimulus_dir(self, session_identifier: str) -> Path:
        """Resolve the stimulus directory for a session based on its PID.

        Uses the ``pid_stimulus_dirs`` map (built from the ``stimulus_versions``
        config) to pick the version-specific stimulus folder. Unmapped PIDs and
        collections without a version map fall back to ``self.stimulus_dir``.

        Parameters
        ----------
        session_identifier : str
            The session identifier (e.g. ``"001_EN_UK_1_ET1"``).

        Returns
        -------
        Path
            The stimulus directory to use for this session.
        """
        if not self.pid_stimulus_dirs:
            return self.stimulus_dir
        pid = Sid(session_identifier).pid
        return self.pid_stimulus_dirs.get(pid, self.stimulus_dir)

    def _answer_option_stimulus_dirs(self) -> list[Path]:
        """Return the default and configured version-specific stimulus directories."""
        directories = [Path(self.stimulus_dir)]
        if self.pid_stimulus_dirs:
            directories.extend(Path(path) for path in self.pid_stimulus_dirs.values())
        unique: list[Path] = []
        seen: set[Path] = set()
        for directory in directories:
            resolved = directory.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(directory)
        return unique

    def _compute_answer_option_shuffling(self) -> dict[str, object]:
        """Check whether shuffled answer-option keys repeat across sessions.

        The check compares canonical JSON hashes per stimulus set. A set is
        flagged when all readable files are identical, or when at least half of
        the non-pilot sessions share the same content and at least two sessions
        use it. The threshold avoids flagging a one-versus-one split.

        Returns
        -------
        dict[str, object]
            The ``processing.answer_option_shuffling`` mapping.
        """
        result = _compute_answer_option_shuffling_stats(
            [session for session in self.sessions.values() if not session.is_pilot],
            self._resolve_stimulus_dir,
            self._answer_option_stimulus_dirs(),
        )
        sets = result.get("sets")
        if isinstance(sets, dict):
            for set_name, stats in sets.items():
                if not isinstance(stats, dict) or not stats.get("flagged"):
                    continue
                max_sessions = int(stats["max_identical_sessions"])
                num_sessions = int(stats["num_sessions"])
                share = float(stats["max_identical_share"])
                if stats.get("all_files_identical") is True:
                    message = (
                        "Answer-option shuffling check: all shuffled option-key files "
                        f"in set '{set_name}' are identical. This can indicate a broken "
                        "randomization seed; verify the option keys before using the data."
                    )
                else:
                    message = (
                        "Answer-option shuffling check: "
                        f"{max_sessions} of {num_sessions} sessions in set '{set_name}' "
                        "share identical shuffled option keys "
                        f"({share:.1%}). This can indicate a broken randomization seed; "
                        "verify the option keys before using the data."
                    )
                self.logger.warning(message)
                _capture_overview_warning(message)
        return result

    def __repr__(self):
        if not self.overview:
            self.overview = self.create_dataset_overview()

        lines = []
        for section_name, section in self.overview.items():
            if isinstance(section, dict):
                lines.append(f"[{section_name}]")
                for k, v in section.items():
                    lines.append(f"  {k}: {v}")
            elif isinstance(section, list):
                lines.append(f"[{section_name}]")
                for item in section:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{section_name}: {section}")
        return "\n".join(lines)

    # TODO: check these chatgpt functions :D
    def __iter__(self):
        self._iter_keys = sorted(self.sessions)
        self._iter_index = 0
        return self

    def __next__(self):
        if self._iter_index >= len(self._iter_keys):
            raise StopIteration
        key = self._iter_keys[self._iter_index]
        self._iter_index += 1
        return self.sessions[key]

    def __getitem__(self, item):
        return self.sessions[item]

    def add_recorded_sessions(
        self,
        data_root: Path,
        session_folder_regex: str = "",
        session_file_suffix: str = "",
    ) -> None:
        """
        Checks what sessions there exist for this data collection and adds them to the sessions dict. No preprocessing or anything happends in here.
        :param data_root: Specifies the root folder where the data is stored
        :param session_folder_regex: The pattern for the session folder names. It is possible to include infomration in
        regex groups. Those will be parsed directly and stored in the session object.
        Those folders should be in the root folder. If '' then the root folder is assumed to contain all files
        from the sessions.
        :param session_file_suffix: The pattern for the session file names. If no pattern is given, all files in the
        session folder are assumed to be the data files depending on the eye tracker.
        """

        self.data_root = data_root
        self.session_folder_regex = session_folder_regex

        found_sessions = []

        if not session_file_suffix and self.eye_tracker == "eyelink":
            # TODO: add configs for each eye tracker such that we don't always have to loop through all eye trackers
            #  but can write generic code. E.g. self.eye_tracker.session_file_regex
            session_file_suffix = r".edf"

        # get a list of all folders in the data folder
        if session_folder_regex:
            items = list(os.scandir(self.data_root))
            pilots = []
            if self.include_pilots:
                pilots = list(os.scandir(self.data_root / self.pilot_folder))
                items = items + pilots

            for item in items:
                if item.is_dir():
                    if re.match(session_folder_regex, item.name, re.IGNORECASE):
                        found_sessions.append(item.name)
                        # Determine if the session should be included based on filters
                        keep = True
                        if self.included_sessions:
                            keep = item.name in self.included_sessions
                        elif self.excluded_sessions:
                            keep = item.name not in self.excluded_sessions

                        if keep:
                            is_pilot = self.include_pilots and (item in pilots)
                            session_file = list(
                                Path(item.path).glob("*" + session_file_suffix)
                            )

                            if len(session_file) == 0:
                                self.logger.warning(
                                    f"No EDF file found for {item.name}, only parsing comprehension answers."
                                )
                                self.skipped_sessions[item.name] = Session(
                                    participant_id=int(item.name.split("_")[0]),
                                    session_identifier=item.name,
                                    session_folder_path=Path(item.path),
                                    session_file_path="unknown",
                                    session_file_name="unknown",
                                    is_pilot=is_pilot,
                                )
                                continue

                            elif len(session_file) > 1:
                                raise ValueError(
                                    f"More than one file found in folder {item.name} that match the pattern "
                                    f"{session_file_suffix}. Please specify a more specific pattern and check "
                                    f"your data."
                                )
                            else:
                                session_file = session_file[0]

                            # When a core and pilot session share the same identifier,
                            # keep the core one (added first) and skip the pilot duplicate.
                            if is_pilot and item.name in self.sessions:
                                self.logger.warning(
                                    f"Skipping pilot session '{item.name}' — "
                                    f"a core session with the same identifier already exists."
                                )
                                continue

                            ses = Session(
                                participant_id=int(item.name.split("_")[0]),
                                session_identifier=item.name,
                                session_folder_path=Path(item.path),
                                session_file_path=session_file,
                                session_file_name=session_file.name,
                                is_pilot=is_pilot,
                            )

                            self.sessions[item.name] = ses

                    else:
                        if item.name not in settings.IGNORED_SESSION_FOLDERS:
                            self.logger.warning(
                                f"Folder in eye-tracking-sessions '{item.name}' does not match the eye-tracking session regex pattern "
                                f"{session_folder_regex}. Not considered an eye-tracking session."
                            )

        if not found_sessions:
            raise ValueError(
                f"No sessions found (or none matching the ex-/inclusion criteria) in data folder {self.data_root}"
            )

        unique_sessions = set(found_sessions)

        if len(unique_sessions) != len(found_sessions):
            # Duplicate names (e.g. pilot + core sharing the same identifier).
            # Keep the first occurrence (core) and skip pilot duplicates.
            seen = set()
            deduped = []
            skipped = []
            for name in found_sessions:
                if name not in seen:
                    seen.add(name)
                    deduped.append(name)
                else:
                    skipped.append(name)
            found_sessions[:] = deduped
            self.logger.warning(
                f"Removed duplicate session identifiers: {', '.join(skipped)}. "
                "Pilot sessions with the same name as core sessions were skipped. "
                "Check your pilot_sessions folder to resolve naming conflicts."
            )

        if self.included_sessions:
            missing_included = set(self.included_sessions) - unique_sessions
            if missing_included:
                self.logger.warning(
                    f"The following sessions were specified in 'include_sessions' but "
                    f"were not found in the data folder: {sorted(missing_included)}"
                )

        if self.excluded_sessions:
            missing_excluded = set(self.excluded_sessions) - unique_sessions
            if missing_excluded:
                self.logger.warning(
                    f"The following sessions were specified in 'exclude_sessions' but "
                    f"were not found in the data folder: {sorted(missing_excluded)}"
                )

    @eyelink
    def convert_edf_to_asc(self) -> None:
        if not self.sessions:
            raise ValueError("No sessions added. Please add sessions first.")

        self.logger.info(
            f"Starting EDF to ASC conversion for {len(self.sessions)} sessions."
        )

        # Check if edf2asc is installed
        if shutil.which("edf2asc") is None:
            raise RuntimeError(
                "The 'edf2asc' binary was not found on your system. "
                "Please make sure it is installed and added to your PATH. "
                "You can download the EyeLink Developers Kit from the SR Research support forum."
            )

        # Create copy of sessions dict without unconvertable sessions
        converted_sessions = {}
        to_convert = []
        for session_identifier, session in self.sessions.items():
            edf_path = Path(session.session_file_path)

            output_asc_folder = (
                settings.OUTPUT_DIR / settings.ASC_FOLDER / session_identifier
            )
            output_asc_path = output_asc_folder / f"{session_identifier}.asc"

            if output_asc_path.exists() and not settings.FORCE_RECONVERT_ASC:
                self.logger.debug(
                    f"ASC already exists in output folder for {session_identifier}. Skipping conversion."
                )
                session.asc_path = output_asc_path
                converted_sessions[session_identifier] = session
                continue

            to_convert.append(
                (
                    session_identifier,
                    session,
                    edf_path,
                    output_asc_folder,
                    output_asc_path,
                )
            )

        def _convert(item):
            (
                session_identifier,
                session,
                edf_path,
                output_asc_folder,
                output_asc_path,
            ) = item
            self.logger.debug(f"Converting EDF to ASC for {session_identifier}")
            output_asc_folder.mkdir(parents=True, exist_ok=True)
            # edf2asc is single-threaded per file, so we run several processes.
            # -p writes the .asc directly into a staging directory instead of
            # next to the .edf (which may be read-only). The staging directory
            # is always removed, so a failed conversion leaves neither a partial
            # .asc nor a stray temporary file behind.
            staging_dir = Path(
                tempfile.mkdtemp(prefix=".edf2asc-", dir=output_asc_folder)
            )
            try:
                subprocess.run(
                    ["edf2asc", "-y", "-c", "-p", str(staging_dir), str(edf_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

                produced_asc = staging_dir / f"{edf_path.stem}.asc"
                if produced_asc.exists():
                    os.replace(produced_asc, output_asc_path)
                    return session_identifier, session, output_asc_path
                return session_identifier, session, None
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

        if to_convert:
            workers = max(1, min(settings.EDF2ASC_WORKERS, len(to_convert)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_convert, item) for item in to_convert]
                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Converting EDF to ASC",
                ):
                    session_identifier, session, converted_asc_path = future.result()
                    if converted_asc_path is not None:
                        session.asc_path = converted_asc_path
                        converted_sessions[session_identifier] = session
                    else:
                        self.logger.error(
                            f"Failed to convert EDF to ASC for {session_identifier}. Only processing comprehension answers."
                        )
                        self.skipped_sessions[session_identifier] = session

        self.sessions = converted_sessions
        self.logger.info("EDF to ASC conversion completed.")

    @staticmethod
    def load_lab_config(
        stimulus_dir: Path,
        lang: str,
        country: str,
        labnum: int,
        city: str,
        year: int,
    ) -> LabConfig:
        """
        Load the lab configuration from the specified directory.
        :param stimulus_dir: The directory where the stimuli are stored.
        :param lang: The language of the stimuli.
        :param country: The country of the stimuli.
        :param labnum: The lab number.
        :param city: The city of the stimuli.
        :param year: The year of the stimuli.

        """
        return LabConfig.load(stimulus_dir, lang, country, labnum, city, year)

    @classmethod
    def create_from_data_folder(
        cls,
        data_dir: str | Path,
        additional_folder: str | None = None,
        include_pilots: bool = False,
        excluded_sessions: list[str] | None = None,
        included_sessions: list[str] | None = None,
        output_dir: Path | None = None,
    ) -> "MultipleyeDataCollection":
        """
        :param data_dir: str  path to the data folder
        :param additional_folder: if additional sub-folders in the data folder are used,
        e.g. 'core_dataset', test_dataset, pilot_dataset
        :param different_stimulus_names: if the stimulus names are different from the default ones they can be extracted
        from the multipleye_stimuli_experiment_en.xlsx file, at the moment only used for testing purposes
        :param include_pilots: If True, the pilot sessions are included in the data collection.
        :param excluded_sessions: If not None, the sessions excluded from the data collection.
        :param included_sessions: If not None, the sessions included in the data collection.
        :return:
        MultipleyeDataCollection object
        """

        excluded_sessions = excluded_sessions or []
        included_sessions = included_sessions or []

        if excluded_sessions and included_sessions:
            raise ValueError(
                "Both 'included_sessions' and 'excluded_sessions' are provided and not empty. "
                "The pipeline only supports using one type of filter at a time to avoid ambiguity. "
                "Please check your configuration and ensure that either 'include_sessions' is used "
                "to process only specific sessions, or 'exclude_sessions' is used to skip specific sessions, "
                "but not both."
            )
        data_dir = Path(data_dir)

        data_folder_name = data_dir.name

        try:
            dcn = Dcn(data_folder_name)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid data collection name: {data_folder_name}. {e}"
            ) from e

        stimulus_language = dcn.lang
        country = dcn.country
        city = dcn.city
        lab_number = dcn.lab
        year = dcn.year

        session_folder_regex = (
            r"\d\d\d"
            + f"_{stimulus_language}_{country}_{lab_number}"
            + r"_ET\d(?:_.*)?"
        )

        stimulus_folder_path = (
            settings.OUTPUT_DIR / f"stimuli_{data_folder_name}"
        ).resolve()
        if not stimulus_folder_path.exists():
            stimulus_folder_path = (data_dir / f"stimuli_{data_folder_name}").resolve()

        config_file = (
            stimulus_folder_path
            / "config"
            / f"config_{stimulus_language.lower()}_{country.lower()}_{city}_{lab_number}.py"
        )

        lab_configuration_data = cls.load_lab_config(
            stimulus_folder_path,
            stimulus_language,
            country,
            int(lab_number),
            city,
            int(year),
        )

        eye_tracker = lab_configuration_data.name_eye_tracker
        psychometric_tests = lab_configuration_data.psychometric_tests

        et_data_path = (
            (data_dir / "eye-tracking-sessions" / additional_folder)
            if additional_folder
            else data_dir / "eye-tracking-sessions"
        )
        ps_tests_path = (
            (data_dir / "psychometric-tests-sessions" / additional_folder)
            if additional_folder
            else data_dir / "psychometric-tests"
        )

        # import raw data from experimenter doc file
        base_name = f"{stimulus_language}_{country}_{city}_{lab_number}"
        doc_sheet_path = _find_experimenter_doc(
            Path(settings.DATASET_DIR),
            base_name,
            stimulus_language,
            country,
            city,
        )
        if doc_sheet_path is not None:
            doc_sheet = ExperimenterDoc.create_from_excel(doc_sheet_path)
        else:
            doc_sheet = None

        # Build the per-PID stimulus directory map from the stimulus_versions config.
        pid_stimulus_dirs = cls._build_pid_stimulus_dirs(data_dir, stimulus_folder_path)

        return cls(
            data_collection_name=data_folder_name,
            stimulus_language=stimulus_language,
            country=country,
            year=int(year),
            eye_tracker=eye_tracker,
            experimenter_doc=doc_sheet,
            session_folder_regex=session_folder_regex,
            config_file=config_file,
            stimulus_dir=stimulus_folder_path,
            lab_number=int(lab_number),
            city=city,
            data_root=et_data_path,
            lab_configuration=lab_configuration_data,
            include_pilots=include_pilots,
            pilot_folder=et_data_path / "pilot_sessions" if include_pilots else None,
            psychometric_tests=psychometric_tests,
            ps_tests_path=ps_tests_path,
            included_sessions=included_sessions,
            excluded_sessions=excluded_sessions,
            output_dir=output_dir,
            pid_stimulus_dirs=pid_stimulus_dirs,
        )

    @classmethod
    def _build_pid_stimulus_dirs(
        cls, data_folder_path: Path, default_stimulus_dir: Path
    ) -> dict[str, Path] | None:
        """Build a map from participant ID to its stimulus folder.

        Reads the configured ``stimulus_versions`` and resolves each versioned
        folder (``stimuli_<dcn>_<suffix>``) under the data folder or the default
        stimulus dir's parent.

        Parameters
        ----------
        data_folder_path : Path
            The raw data collection directory (contains ``stimuli_<dcn>``).
        default_stimulus_dir : Path
            The resolved default stimulus directory.

        Returns
        -------
        dict[str, Path] | None
            Mapping from PID to stimulus directory, or ``None`` if no versions
            are configured.
        """
        pid_map = settings.STIMULUS_VERSIONS_PID_MAP or {}
        if not pid_map:
            return None

        # Prefer the prepared copy next to the default stimulus dir (the output
        # folder the pipeline uses, where AOIs are split/fixed); fall back to the
        # raw data folder.
        result: dict[str, Path] = {}
        for version, pids in pid_map.items():
            folder_name = stimulus_folder_name(data_folder_path.name, version)
            version_dir = default_stimulus_dir.parent / folder_name
            if not version_dir.exists():
                version_dir = data_folder_path / folder_name
            for pid in pids:
                result[str(pid)] = version_dir
        return result

    def create_sanity_check_report(
        self,
        gaze: pm.Gaze,
        session_name: str,
        output_dir: Path | str = "",
        plotting: bool = True,
        recalculate: bool | None = None,
    ) -> None:
        """
        Create the sanity checks and reports if for one or multiple sessions.
        :param output_dir:
        :param gaze:
        :param session_name: Specifies which session to create the report for.
        :param plotting: If True, all plots are also created for all the sessions.
        :param recalculate: If True, the sanity check report is overwritten if it already exists.
        """

        if session_name in self.excluded_sessions:
            logging.info(
                f"Session {session_name} is excluded from the analysis. Skipping sanity check report."
            )
            return

        if not output_dir:
            output_dir = self.output_dir

        if recalculate is None:
            recalculate = settings.RECALCULATE

        session_results = (
            Path(output_dir) / settings.SANITY_CHECKS_FOLDER / session_name
        )
        os.makedirs(session_results, exist_ok=True)

        self.sessions[session_name].uncategorized_messages = self.parse_messages(
            session_name
        )

        report_file_path = session_results / f"{session_name}_{self.city}_report.md"
        self.sessions[session_name].sanity_report_path = report_file_path

        if not report_file_path.exists() or recalculate:
            open(report_file_path, "w", encoding="utf-8").close()

            messages = self.sessions[session_name].messages

            if isinstance(messages, pl.DataFrame):
                messages_for_check = [
                    {"message": row["content"], "timestamp": row["time"]}
                    for row in messages.iter_rows(named=True)
                ]
            else:
                messages_for_check = messages or []

            stimuli = self.sessions[session_name].stimuli

            _report_to_file(
                f"# Sanity Check: {session_name} — {self.city}\n",
                report_file_path,
            )
            _report_to_file("## Metadata", report_file_path)

            with open(report_file_path, "a+", encoding="utf-8") as report_file:
                report = partial(report_meta, report_file=report_file)
                check_metadata(
                    self.sessions[session_name].pm_gaze_metadata,
                    self.sessions[session_name].calibrations,
                    self.sessions[session_name].validations,
                    report,
                    total_data_loss_ratio=getattr(
                        self.sessions[session_name],
                        "_measure_total_data_loss_ratio",
                        None,
                    ),
                    blink_loss_ratio=getattr(
                        self.sessions[session_name],
                        "_measure_blink_loss_ratio",
                        None,
                    ),
                )

            _report_to_file("## Logfile", report_file_path)
            self._check_logfiles(stimuli, session_name)
            _report_to_file("## Gaze Frame", report_file_path)
            self._check_stimuli_gaze_frame(gaze, stimuli, session_name)
            _report_to_file("## ASC Messages", report_file_path)
            if messages_for_check:
                self._check_asc_messages(stimuli, messages_for_check, session_name)
            else:
                self.logger.warning(f"No messages found in asc file of {session_name}.")
            _report_to_file("## Validation & Calibration", report_file_path)
            self._check_asc_validation(session_name)
            self._load_psychometric_tests(session_name)
            _report_to_file("## Comprehension Answers", report_file_path)
            self._extract_question_answers(stimuli, session_name)
            fix_report = self._check_avg_fix_durations(gaze)

            fix_report.write_csv(
                session_results / f"fixation_statistics_per_page_{session_name}.tsv",
                separator="\t",
            )

            _report_to_file("## Per-trial Data Loss", report_file_path)
            per_trial_loss = self._compute_per_trial_loss_table(session_name)
            if per_trial_loss is not None and not per_trial_loss.is_empty():
                # One row per trial. The mean over rows weights every trial equally:
                # trials are NOT weighted by their recording length.
                num_trials = per_trial_loss.height
                mean_data_loss = (
                    per_trial_loss["data_loss_ratio"].mean()
                    if "data_loss_ratio" in per_trial_loss
                    else None
                )
                mean_blink_loss = (
                    per_trial_loss["blink_loss_ratio"].mean()
                    if "blink_loss_ratio" in per_trial_loss
                    else None
                )
                if mean_data_loss is not None:
                    _report_to_file(
                        f"- Mean per-trial data loss: {mean_data_loss:.3f} "
                        f"(across {num_trials} trials)",
                        report_file_path,
                    )
                if mean_blink_loss is not None:
                    _report_to_file(
                        f"- Mean per-trial blink loss: {mean_blink_loss:.3f} "
                        f"(across {num_trials} trials)",
                        report_file_path,
                    )

                per_trial_loss.write_csv(
                    session_results / f"per_trial_data_loss_{session_name}.tsv",
                    separator="\t",
                )

                per_page_loss = self._compute_per_page_loss_table(session_name)
                if per_page_loss is not None and not per_page_loss.is_empty():
                    per_page_loss.write_csv(
                        session_results / f"per_page_data_loss_{session_name}.tsv",
                        separator="\t",
                    )
                    _report_to_file("Data loss by page type:", report_file_path)
                    by_page_type = self._data_loss_by_page_type(session_name)
                    if by_page_type is not None:
                        for row in by_page_type.iter_rows(named=True):
                            _report_to_file(
                                f"- {row['page_type']}: {row['mean_data_loss']:.3f} "
                                f"(mean over {row['num_pages']} pages)",
                                report_file_path,
                            )
            else:
                _report_to_file("- No per-trial metrics available.", report_file_path)

            legend = "\n---\n\n**Legend:** ✅ Pass | ❌ Fail | ⚠️ Warning\n"
            _report_to_file(legend, report_file_path)

            if plotting:
                self._create_plots(
                    gaze, stimuli, session_name, session_results, aoi=True
                )

        else:
            logging.info(f"Skipping sanity check report for session {session_name}.")
            return

    def _load_session_names(self, session: str | list[str] | None) -> list[str]:
        """
        Get the session names from the data root folder.
        :param session: If a session identifier is specified only the gaze data for this session is loaded.
        :return:
        """
        if not session:
            sessions = [key for key in self.sessions]
            return sessions
        elif session not in self.sessions:
            raise KeyError(f"Session {session} not found in {self.data_root}.")

        elif isinstance(session, str):
            return [session]
        elif isinstance(session, list):
            return session

    def create_dataset_overview(self, path: str | Path = "") -> dict:
        """
        Create an overview of the dataset and save it as a yaml file in the top data folder.
        :return: overview dict
        """

        if not path:
            overview_path = (
                self.data_root.parent / f"{self.data_collection_name}_overview.yaml"
            )

        else:
            overview_path = path / f"{self.data_collection_name}_overview.yaml"

        num_sessions = len(
            [
                session
                for session in self.sessions
                if not self.sessions[session].is_pilot
            ]
        )
        num_pilots = len(
            [session for session in self.sessions if self.sessions[session].is_pilot]
        )

        session_completeness = _compute_session_completeness(self)

        metadata_form = self._load_metadata_form()
        metadata_form_exists = bool(metadata_form)

        language_script = _metadata_form_value(
            metadata_form, "Tested_language", "Language_script", "Script"
        )
        language_family = _metadata_form_value(
            metadata_form, "Tested_language", "Language_family", "Language_family"
        )
        start_date = _metadata_form_value(
            metadata_form,
            "Time_frame",
            "Start_date",
            "Start_date_of_data_collection",
        )
        end_date = _metadata_form_value(
            metadata_form,
            "Time_frame",
            "End_date",
            "End_date_of_data_collection",
        )

        dataset_description = (
            f"{self.country}, {self.city} (lab {self.lab_number}). "
            f"{self.language} corpus. "
            f"Data collected from {start_date if start_date is not None else 'unknown'} "
            f"to {end_date if end_date is not None else 'unknown'}."
        )

        def _lab_pair(attr: str) -> tuple[object, object]:
            value = getattr(self.lab_configuration, attr, None)
            if isinstance(value, (tuple, list)) and len(value) == 2:
                return value[0], value[1]
            return None, None

        screen_res_w, screen_res_h = _lab_pair("screen_resolution")
        screen_size_w, screen_size_h = _lab_pair("screen_size_cm")
        image_res_w, image_res_h = _lab_pair("image_resolution")
        image_size_w, image_size_h = _lab_pair("image_size_cm")
        screen_distance_cm = getattr(self.lab_configuration, "screen_distance_cm", None)
        codebook_info = load_codebook_identity()

        overview = {
            "administrative": {
                "title": self.data_collection_name,
                "dataset_type": self.type,
                "dataset_description": dataset_description,
                "number_of_sessions": num_sessions,
                "number_of_pilots": num_pilots,
                "number_of_et_sessions_per_participant": self.num_sessions,
                "session_completeness": session_completeness,
                "city": self.city,
                "lab_number": self.lab_number,
                "country": self.country,
                "tested_language": self.language,
            },
            "language_details": {
                "metadata_form_exists": metadata_form_exists,
                "language_script": language_script,
                "language_family": language_family,
                "start_date_of_data_collection": start_date,
                "end_date_of_data_collection": end_date,
            },
            "data_availability": {
                "raw_data_available": True,
                "fixations_available": True,
                "saccades_available": True,
                "reading_measures_available": True,
            },
            "psychometric_tests": {
                "tests_available": getattr(
                    self.lab_configuration, "psychometric_tests", None
                ),
            },
            "technical_setup": {
                "eye_tracker_name_raw": self.eye_tracker_name_raw,
                "eye_tracker_name": self.eye_tracker_name,
                "sampling_frequency_hz": getattr(
                    self.lab_configuration, "sampling_frequency_hz", None
                ),
                "monitor_name": metadata_form.get("Monitor_name"),
                "screen_resolution_width_px": screen_res_w,
                "screen_resolution_height_px": screen_res_h,
                "screen_size_width_cm": screen_size_w,
                "screen_size_height_cm": screen_size_h,
                "screen_distance_cm": screen_distance_cm,
                "image_resolution_width_px": image_res_w,
                "image_resolution_height_px": image_res_h,
                "image_size_width_cm": image_size_w,
                "image_size_height_cm": image_size_h,
            },
            "processing": {
                "preprocessing_date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
                "pipeline_version": self._get_pipeline_version(),
                "number_of_stimulus_versions": len(
                    self.stim_order_versions["version_number"].unique()
                )
                if hasattr(self, "stim_order_versions")
                and len(self.stim_order_versions) > 0
                else 0,
                # Flags from metadata_form.json
                "required_pq_fixing": metadata_form.get("Required_pq_fixing"),
                "psychotests_restructuring": metadata_form.get(
                    "Psychotests_restructuring"
                ),
                "custom_units_of_analysis": metadata_form.get(
                    "Custom_units_of_analysis"
                ),
                "answer_option_shuffling": self._compute_answer_option_shuffling(),
            },
            "processing_environment": self._get_processing_environment(),
            "processing_config": {
                "fixation_method": settings.FIXATION_METHOD,
                "fixation_minimum_duration_ms": settings.FIXATION_MINIMUM_DURATION_MS,
                "fixation_velocity_threshold": settings.FIXATION_VELOCITY_THRESHOLD,
                "saccade_method": settings.SACCADE_METHOD,
                "saccade_minimum_duration": settings.SACCADE_MINIMUM_DURATION,
                "saccade_threshold_factor": settings.SACCADE_THRESHOLD_FACTOR,
                "velocity_estimation_method": settings.VELOCITY_ESTIMATION_METHOD,
                "velocity_smoothing_window_ms": settings.VELOCITY_SMOOTHING_WINDOW_MS,
                "velocity_polynomial_degree": settings.VELOCITY_POLYNOMIAL_DEGREE,
                "psym_wikivocab_min_rt": settings.PSYM_WIKIVOCAB_MIN_RT,
                "psym_wikivocab_max_rt": settings.PSYM_WIKIVOCAB_MAX_RT,
                "psym_stroop_min_rt": settings.PSYM_STROOP_MIN_RT,
                "psym_stroop_max_rt": settings.PSYM_STROOP_MAX_RT,
                "psym_flanker_min_rt": settings.PSYM_FLANKER_MIN_RT,
                "psym_flanker_max_rt": settings.PSYM_FLANKER_MAX_RT,
                "tracked_eye": settings.TRACKED_EYE,
                "trial_cols": settings.TRIAL_COLS,
                "trial_col": settings.TRIAL_COL,
                "page_col": settings.PAGE_COL,
                "stimulus_col": settings.STIMULUS_COL,
                "word_idx_col": settings.WORD_IDX_COL,
                "char_idx_col": settings.CHAR_IDX_COL,
                "aoi_enlargement": "half_line_spacing",
                "reading_measures_null_fill": 0,
                "scanpath_drop_unmapped": True,
                "data_loss_missingness_column": "pixel",
                "per_trial_loss_weighting": "equal",
            },
            "data_quality": {
                "attrition_rate": self._compute_attrition_rate(),
                **self._compute_dcn_averages(),
            },
            "codebook": {
                "version": codebook_info.get("codebook_version"),
                "credit": codebook_info.get("credit"),
                "hash": codebook_info.get("hash"),
            },
        }

        # Add warnings to overview
        if hasattr(logging, "_captured_warnings") and logging._captured_warnings:
            overview["warnings"] = list(set(logging._captured_warnings))

        with open(overview_path, "w", encoding="utf8") as f:
            yaml.dump(overview, f, sort_keys=False)

        return overview

    def write_codebook_outputs(self, path: str | Path) -> Path | None:
        """Write the codebook package, environment and generated bundle."""
        environment = self._get_processing_environment()
        environment["pipeline_version"] = self._get_pipeline_version()
        return write_codebook_package(path, environment)

    @staticmethod
    def _get_pipeline_version() -> str | None:
        """
        Return the installed pipeline version, or None if it cannot be determined.

        Returns
        -------
        str | None
            Version string from package metadata, or None on failure.
        """
        try:
            version, _ = get_pipeline_info()
            return version
        except (ImportError, KeyError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _get_processing_environment() -> dict:
        """
        Return the tool versions and git revision used for this run.

        Unavailable values are reported as ``None``. ``pipeline_version`` stays in
        ``processing``.

        Returns
        -------
        dict
            Mapping with ``pipeline_git``, ``pymovements_version``,
            ``edf2asc_version`` and ``python_version``.
        """
        try:
            _, pipeline_git = get_pipeline_info()
        except (ImportError, KeyError, subprocess.SubprocessError):
            pipeline_git = None

        python_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )

        return {
            "pipeline_git": _known_version(pipeline_git),
            "pymovements_version": _known_version(getattr(pm, "__version__", None)),
            "edf2asc_version": _known_version(get_edf2asc_version()),
            "python_version": _known_version(python_version),
        }

    def _load_metadata_form(self) -> dict:
        """
        Load the final metadata form JSON for this data collection, if present.

        Uploads use either ``metadataForm_MultiplEYE_<dcn>.json`` or
        ``metadataform_MultiplEYE_<dcn>.json`` in the ``documentation`` folder,
        sometimes with a trailing space before the extension. The older
        ``MultiplEYE_<...>_metadata_form.json`` naming is still supported as a
        fallback.

        Returns
        -------
        dict
            Parsed metadata form contents, or an empty dict if the file is
            missing or cannot be matched unambiguously.
        """
        documentation_dir = self.stimulus_dir.parent / "documentation"
        metadata_path = find_metadata_form(
            documentation_dir,
            self.data_collection_name,
            language=self.language,
            country=self.country,
            city=self.city,
            lab_number=self.lab_number,
            year=self.year,
        )
        if metadata_path is None:
            return {}
        return load_metadata_form(metadata_path)

    def _compute_attrition_rate(self) -> float | None:
        """
        Compute the session attrition rate across non-pilot sessions.

        Attrition is the fraction of non-pilot sessions that crashed, rounded to
        two decimal places.

        Returns
        -------
        float | None
            Crashed session ratio, or None if there are no non-pilot sessions.
        """
        non_pilot_sessions = [s for s in self.sessions.values() if not s.is_pilot]
        total_sessions = len(non_pilot_sessions)
        if total_sessions == 0:
            return None
        crashed = (
            len(self.crashed_session_ids) if hasattr(self, "crashed_session_ids") else 0
        )
        return round(crashed / total_sessions, 2)

    def _compute_dcn_averages(self) -> dict[str, float | None]:
        """
        Compute simple means across non-pilot sessions for the data quality fields.

        Averages are unweighted means across sessions (not time-weighted). Session
        fields that are not numeric (e.g. the string default "unknown") are skipped,
        so a field is None when no session has a computed value for it.

        Returns
        -------
        dict[str, float | None]
            Mapping of metric name to mean value, or None if no data is available.
        """
        non_pilot_sessions = [s for s in self.sessions.values() if not s.is_pilot]
        if not non_pilot_sessions:
            return {
                "mean_calibration_error_dva": None,
                "mean_validation_error_dva": None,
                "mean_data_loss_ratio": None,
                "mean_blink_ratio": None,
                "mean_total_reading_time_s": None,
                "mean_total_session_duration_s": None,
                "mean_rt_per_stim_ms": None,
                "mean_total_question_time_ms": None,
                "mean_total_rating_time_ms": None,
                "mean_wpm": None,
                "mean_comprehension_score": None,
                "mean_comprehension_score_local": None,
                "mean_comprehension_score_global": None,
                "mean_comprehension_score_bridging": None,
            }

        calib_errors = [
            s.avg_calibration_error
            for s in non_pilot_sessions
            if isinstance(s.avg_calibration_error, (int, float))
        ]
        val_errors = [
            s.avg_validation_error
            for s in non_pilot_sessions
            if isinstance(s.avg_validation_error, (int, float))
        ]
        data_loss = [
            getattr(s, "_measure_total_data_loss_ratio", None)
            for s in non_pilot_sessions
        ]
        data_loss = [v for v in data_loss if isinstance(v, (int, float))]
        blink_loss = [
            getattr(s, "_measure_blink_loss_ratio", None) for s in non_pilot_sessions
        ]
        blink_loss = [v for v in blink_loss if isinstance(v, (int, float))]
        reading_times_s = [
            s.total_reading_time
            for s in non_pilot_sessions
            if isinstance(s.total_reading_time, (int, float))
        ]
        session_durations = [
            s.total_session_duration
            for s in non_pilot_sessions
            if isinstance(s.total_session_duration, (int, float))
        ]

        def _mean_of(attr: str) -> float | None:
            values = [
                getattr(s, attr, None)
                for s in non_pilot_sessions
                if isinstance(getattr(s, attr, None), (int, float))
            ]
            return round(sum(values) / len(values), 2) if values else None

        comp_scores = [
            s.avg_comprehension_score
            for s in non_pilot_sessions
            if isinstance(s.avg_comprehension_score, (int, float))
        ]

        # WPM: total words / total_minutes
        # Word count computed from stimulus page texts
        mean_wpm = None
        if reading_times_s:
            total_reading_s = sum(reading_times_s)
            if total_reading_s > 0:
                mean_wpm = self._compute_dcn_wpm(non_pilot_sessions, total_reading_s)

        return {
            "mean_calibration_error_dva": (
                round(sum(calib_errors) / len(calib_errors), 2)
                if calib_errors
                else None
            ),
            "mean_validation_error_dva": (
                round(sum(val_errors) / len(val_errors), 2) if val_errors else None
            ),
            "mean_rt_per_stim_ms": _mean_of("mean_rt_per_stim_ms"),
            "mean_total_question_time_ms": _mean_of("total_question_time_ms"),
            "mean_total_rating_time_ms": _mean_of("total_rating_time_ms"),
            "mean_data_loss_ratio": (
                round(sum(data_loss) / len(data_loss), 2) if data_loss else None
            ),
            "mean_blink_ratio": (
                round(sum(blink_loss) / len(blink_loss), 2) if blink_loss else None
            ),
            "mean_total_reading_time_s": (
                round(sum(reading_times_s) / len(reading_times_s), 2)
                if reading_times_s
                else None
            ),
            "mean_total_session_duration_s": (
                round(sum(session_durations) / len(session_durations), 2)
                if session_durations
                else None
            ),
            "mean_wpm": round(mean_wpm, 1) if mean_wpm else None,
            "mean_comprehension_score": (
                round(sum(comp_scores) / len(comp_scores), 2) if comp_scores else None
            ),
            "mean_comprehension_score_local": _mean_of("avg_comprehension_score_local"),
            "mean_comprehension_score_global": _mean_of(
                "avg_comprehension_score_global"
            ),
            "mean_comprehension_score_bridging": _mean_of(
                "avg_comprehension_score_bridging"
            ),
        }

    def _compute_dcn_wpm(
        self,
        non_pilot_sessions: list,
        total_reading_seconds: float,
    ) -> float | None:
        """
        Compute words per minute across non-pilot sessions.

        Word count is derived from the stimulus page texts; total words divided by
        total reading time in minutes.

        Parameters
        ----------
        non_pilot_sessions : list
            Non-pilot Session objects to aggregate.
        total_reading_seconds : float
            Total reading time across those sessions, in seconds.

        Returns
        -------
        float | None
            Words per minute, or None if no words or no reading time is available.
        """
        total_words = 0
        for session in non_pilot_sessions:
            if not isinstance(session.stimuli, list):
                continue
            for stim in session.stimuli:
                if not hasattr(stim, "pages"):
                    continue
                for page in stim.pages:
                    if hasattr(page, "text") and page.text:
                        total_words += len(page.text.split())
        if total_words == 0:
            return None
        total_minutes = total_reading_seconds / 60
        if total_minutes <= 0:
            return None
        return total_words / total_minutes

    def create_session_overview(self, session_idf: str, path: str | Path = "") -> dict:
        sess = self.sessions[session_idf]

        if not path:
            overview_path = self.data_root.parent / f"{session_idf}_overview.yaml"
        else:
            overview_path = (
                Path(path)
                / settings.METADATA_FOLDER
                / session_idf
                / f"{session_idf}_overview.yaml"
            )
            overview_path.parent.mkdir(parents=True, exist_ok=True)

        with open(overview_path, "w", encoding="utf8") as f:
            yaml.dump(sess.create_overview(self.experimenter_doc), f)

    def prepare_session_level_information(self):
        """
        Load the logfiles and completed stimuli for all sessions. All of this information is needed repeatedly
        in the sanity checks and is therefore loaded once here.
        :return:
        """

        for session in (pbar := tqdm(self.sessions.keys(), total=len(self.sessions))):
            pbar.set_description(f"Preparing session {session}")
            try:
                p_id = Sid(session).pid
            except (ValueError, TypeError):
                p_id = session.split("_")[0] if "_" in session else session

            if "start_after_trial" in session and p_id not in self.crashed_session_ids:
                self.crashed_session_ids.append(p_id)
                self.logger.warning(
                    f"Session {session} started after a trial. Only the completed stimuli will be considered."
                )

            self.sessions[session].stimulus_content_version = version_suffix_for_pid(
                p_id
            )

            (
                self.sessions[session].completed_stimuli_ids,
                self.sessions[session].completed_stimuli_names,
                self.sessions[session].stimuli_trial_mapping,
            ) = self._load_session_completed_stimuli(session)
            self.sessions[session].logfile = self._load_session_logfile(session)
            self.sessions[
                session
            ].randomization_version = self._load_stimulus_order_version_from_logfile(
                session
            )
            self.sessions[
                session
            ].stimulus_order_ids = self._load_session_stimulus_order(
                session, self.sessions[session].randomization_version
            )

            # TODO: lab config should be changeable for each session
            self.sessions[session].lab_config = self.lab_configuration

            if (
                self.sessions[session].stimulus_order_ids
                != self.sessions[session].completed_stimuli_ids
            ) and p_id not in self.crashed_session_ids:
                msg = (
                    f"Stimulus order and completed stimuli do not match for "
                    f"session {session}. Please check the files carefully."
                )
                self.logger.warning(msg)
                if not hasattr(logging, "_captured_warnings"):
                    logging._captured_warnings = []  # type: ignore
                logging._captured_warnings.append(msg)  # type: ignore

            self.sessions[session].stimuli = self._load_session_stimuli(
                self._resolve_stimulus_dir(session),
                self.language,
                self.country,
                self.lab_number,
                self.sessions[session].randomization_version,
                session,
            )

        for session in (
            pbar := tqdm(self.skipped_sessions.keys(), total=len(self.skipped_sessions))
        ):
            pbar.set_description(f"Preparing session {session}")
            try:
                p_id = Sid(session).pid
            except (ValueError, TypeError):
                p_id = session.split("_")[0] if "_" in session else session

            if "start_after_trial" in session and p_id not in self.crashed_session_ids:
                self.crashed_session_ids.append(p_id)
                self.logger.warning(
                    f"Session {session} started after a trial. Only the completed stimuli will be considered."
                )

            self.skipped_sessions[
                session
            ].stimulus_content_version = version_suffix_for_pid(p_id)

            (
                self.skipped_sessions[session].completed_stimuli_ids,
                self.skipped_sessions[session].completed_stimuli_names,
                self.skipped_sessions[session].stimuli_trial_mapping,
            ) = self._load_session_completed_stimuli(session)
            self.skipped_sessions[session].logfile = self._load_session_logfile(session)
            self.skipped_sessions[
                session
            ].randomization_version = self._load_stimulus_order_version_from_logfile(
                session
            )
            self.skipped_sessions[
                session
            ].stimulus_order_ids = self._load_session_stimulus_order(
                session, self.skipped_sessions[session].randomization_version
            )

            # TODO: lab config should be changeable for each session
            self.skipped_sessions[session].lab_config = self.lab_configuration

            if (
                self.skipped_sessions[session].stimulus_order_ids
                != self.skipped_sessions[session].completed_stimuli_ids
            ) and p_id not in self.crashed_session_ids:
                msg = (
                    f"Stimulus order and completed stimuli do not match for "
                    f"session {session}. Please check the files carefully."
                )
                self.logger.warning(msg)
                if not hasattr(logging, "_captured_warnings"):
                    logging._captured_warnings = []  # type: ignore
                logging._captured_warnings.append(msg)  # type: ignore

            self.skipped_sessions[session].stimuli = self._load_session_stimuli(
                self._resolve_stimulus_dir(session),
                self.language,
                self.country,
                self.lab_number,
                self.skipped_sessions[session].randomization_version,
                session,
            )

        self._assign_participant_info()

    def _assign_participant_info(self) -> None:
        """Attach the per-session ``participant`` section.

        Combines participant-questionnaire (PQ) data with psychometric-test session
        metadata: available tests, tests conducted in this vs a separate session,
        same-day indicator and day gaps to other sessions/tests, plus a curated set
        of psychometric scores for the participant.

        All lookups are best-effort: missing data yields ``"unknown"`` (or ``None``
        for the same-day flag) rather than raising.
        """
        participants: dict[str, list[str]] = {}
        for sid_str in self.sessions:
            try:
                sid = Sid(sid_str)
            except (ValueError, TypeError):
                continue
            participants.setdefault(sid.base_id.upper(), []).append(sid_str)

        pt_folders = self._index_psychometric_sessions()
        results = self._load_psychometric_results()
        pq_mapping = self._pq_mapping()

        for base_id, sid_strs in participants.items():
            ordered = sorted(sid_strs, key=lambda s: Sid(s).session_id)
            pid = Sid(ordered[0]).pid if ordered else None
            pq = self._participant_pq_data(sid_strs, pid)
            pq_values = (
                normalise_pq(pq, pq_mapping)["values"]
                if pq_mapping is not None and pq
                else {}
            )
            session_dates = {
                s: _session_date_from_logfile(self.sessions[s].logfile) for s in ordered
            }
            pt_by_session = pt_folders.get(base_id, {})

            all_pt_dates: set[date] = set()
            all_pt_tests: set[str] = set()
            for folder in pt_by_session.values():
                all_pt_dates |= _psychometric_dates(folder)
                all_pt_tests |= set(_psychometric_tests_in_folder(folder))

            scores = self._psychometric_scores_for_participant(results, pid)

            for position, sid_str in enumerate(ordered):
                session_id = Sid(sid_str).session_id
                matched = pt_by_session.get(session_id)
                if matched is not None:
                    self.sessions[sid_str].psychometric_tests_session = matched.name

                this_tests = set(_psychometric_tests_in_folder(matched))
                et_date = session_dates.get(sid_str)
                matched_dates = _psychometric_dates(matched)

                gap_to_tests: int | str = "unknown"
                if et_date is not None and all_pt_dates:
                    gap_to_tests = min(abs((et_date - d).days) for d in all_pt_dates)

                gap_prev: int | str = "unknown"
                if et_date is not None and position > 0:
                    prev_date = session_dates.get(ordered[position - 1])
                    if prev_date is not None:
                        gap_prev = (et_date - prev_date).days

                gap_next: int | str = "unknown"
                if et_date is not None and position < len(ordered) - 1:
                    next_date = session_dates.get(ordered[position + 1])
                    if next_date is not None:
                        gap_next = (next_date - et_date).days

                self.sessions[sid_str].participant_info = {
                    "gender": pq_values.get(
                        "pq_gender", (pq or {}).get("gender", "unknown")
                    ),
                    "bi_monolingualism": _bi_monolingualism_from_pq(pq_values or pq),
                    "psychometric_tests": sorted(all_pt_tests),
                    "tests_conducted_this_session": sorted(this_tests),
                    "tests_conducted_separate_session": sorted(
                        all_pt_tests - this_tests
                    ),
                    "has_pt_data_same_day_as_session": (
                        bool(et_date in matched_dates) if et_date is not None else None
                    ),
                    "gap_to_previous_session_days": gap_prev,
                    "gap_to_next_session_days": gap_next,
                    "gap_to_psychometric_tests_days": gap_to_tests,
                    "psychometric_test_scores": scores,
                }

    def _index_psychometric_sessions(self) -> dict[str, dict[int, Path]]:
        """Index psychometric-test session folders by participant and session number."""
        index: dict[str, dict[int, Path]] = {}
        pt_dir = settings.PSYCHOMETRIC_TESTS_DIR
        if not Path(pt_dir).exists():
            return index
        for folder in Path(pt_dir).iterdir():
            if not folder.is_dir():
                continue
            try:
                sid = Sid(folder.name)
            except (ValueError, TypeError):
                continue
            index.setdefault(sid.base_id.upper(), {})[sid.session_id] = folder
        return index

    def _pq_mapping(self) -> dict | None:
        """Build the PQ label mapping from the data collection's workbooks."""
        language = getattr(self, "language", None)
        if not language:
            return None
        question_path, language_path = find_questionnaire_files(
            settings.DATASET_DIR, language
        )
        if question_path is None:
            return None
        return build_mapping(question_path, language_path)

    def _participant_pq_data(self, sid_strs: list[str], pid: str | None = None) -> dict:
        """Return the participant's raw PQ data, if present.

        Searches the ET session folders and ``participant_questionnaire_*``
        (covering participants whose PQ file is not stored with an ET session).
        """
        session_dirs = [
            Path(self.sessions[sid].session_folder_path) for sid in sid_strs
        ]
        questionnaire_dirs = list(
            Path(settings.DATASET_DIR).glob("participant_questionnaire*")
        )
        questionnaire_dirs.append(Path(settings.DATASET_DIR) / "documentation")

        pq_file = None
        if pid is not None:
            pq_file = find_pq_data(pid, session_dirs, questionnaire_dirs)
        if pq_file is None:
            for folder in session_dirs:
                files = sorted(folder.glob("*_pq_data.json"))
                if files:
                    pq_file = files[0]
                    break
        if pq_file is None:
            return {}
        try:
            data = json.loads(pq_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _load_psychometric_results(self):
        """Load the psychometric results table for this data collection, if present."""
        out = Path(settings.OUTPUT_DIR) / settings.PSYCHOMETRIC_TESTS_FOLDER
        for name in (
            f"psychometric_results_{self.data_collection_name}_merged.csv",
            f"psychometric_results_{self.data_collection_name}.csv",
        ):
            path = out / name
            if path.exists():
                try:
                    return pl.read_csv(path)
                except (ComputeError, OSError):
                    continue
        return None

    @staticmethod
    def _psychometric_scores_for_participant(results, pid: str | None) -> dict | str:
        """Return the curated psychometric scores for a participant, else ``"unknown"``."""
        if results is None or pid is None or "participant_id" not in results.columns:
            return "unknown"
        try:
            wanted = int(str(pid))
        except (ValueError, TypeError):
            return "unknown"
        rows = results.filter(
            pl.col("participant_id").cast(pl.Int64, strict=False) == wanted
        )
        if rows.is_empty():
            return "unknown"
        row = rows.row(0, named=True)
        return {key: row.get(key) for key in PSYCHOMETRIC_KEY_SCORES if key in row}

    def _load_session_stimuli(
        self,
        stimulus_dir: Path,
        lang: str,
        country: str,
        lab_num: int,
        stimulus_order_version: int,
        session_identifier: str,
        stimulus_names: None | list = None,
    ) -> list[Stimulus]:
        """
        Load the stimuli from the specified directory.
        :param stimulus_dir: The directory where the stimuli are stored.
        :param lang: The language of the stimuli.
        :param country: The country of the stimuli.
        :param stimulus_names: The names of the stimuli to load. If None, the predefined stimuli names in the
        global variable self.stimulus_names are used.
        :param stimulus_order_version: The version of the questions to load. Specifies how the questions are ordered and the
        shuffling of the answer options.
        :param lab_num: The lab number.

        """
        if session_identifier in self.sessions:
            session = self.sessions[session_identifier]
        else:
            session = self.skipped_sessions[session_identifier]

        stimuli = []
        if stimulus_names is None:
            stimulus_names = [
                name
                for name, num in settings.STIMULUS_NAME_MAPPING.items()
                if num in session.completed_stimuli_ids
            ]

        for stimulus_name in stimulus_names:
            trial_mapping = session.stimuli_trial_mapping
            # get the trial id from the mapping, keys are ids and values are strings
            trial_id = [
                key for key, value in trial_mapping.items() if value == stimulus_name
            ]
            if len(trial_id) == 0:
                raise KeyError(
                    f"Stimulus name {stimulus_name} not found in the trial mapping for session "
                    f"{session_identifier}. Please check the completed_stimuli.csv file."
                )

            stimulus = Stimulus.load(
                stimulus_dir,
                lang,
                country,
                lab_num,
                stimulus_name,
                stimulus_order_version,
                trial_id[0],
            )
            stimuli.append(stimulus)

        return stimuli

    def _load_stimulus_order_version_from_logfile(self, session_identifier: str) -> int:
        """
        Extract the question order and version from the session identifier.
        :param session_identifier: The session identifier.
        :return: The question order version to correctly map participant, stimulus and question order versions.
        """
        if session_identifier in self.sessions:
            session_path = self.sessions[session_identifier].session_folder_path
        else:
            session_path = self.skipped_sessions[session_identifier].session_folder_path

        logfile_path = Path(f"{session_path}/logfiles")
        general_logfile = logfile_path.glob("GENERAL_LOGFILE_*.txt")
        general_logfile = next(general_logfile)
        assert general_logfile.exists(), (
            f"Logfile path {general_logfile} does not exist."
        )

        regex = settings.LOGFILE_ORDER_VERSION_REGEX
        with open(general_logfile, encoding="utf-8") as f:
            text = f.read()
        match = re.search(regex, text)

        if match:
            stimulus_order_version_logfile = int(match.groupdict()["order_version"])
        else:
            raise ValueError(
                f"Could not find question order version in {general_logfile}."
            )

        return stimulus_order_version_logfile

    def _load_session_logfile(self, session_identifier):
        """
        Load the logfiles for the specified session. Stores the logfile and the completed stimuli as a polars DataFrame,
        the order of the stimuli as list, and the version of the question oder as an int.
        :param session_identifier: The session identifier.
        """

        if session_identifier in self.sessions:
            session_path = self.sessions[session_identifier].session_folder_path
        else:
            session_path = self.skipped_sessions[session_identifier].session_folder_path
        logfile_folder = Path(f"{session_path}/logfiles")

        assert logfile_folder.exists(), (
            f"Logfile folder {logfile_folder} does not exist."
        )
        logfile = logfile_folder.glob("EXPERIMENT_*.txt")

        logfiles = list(logfile)

        if len(logfiles) != 1:
            raise ValueError(
                f"More than one or no logfile found in {logfile_folder}. Please check the logfiles carefully. "
                f"This can happen if the experiment crashed early and was restarted, in that case the earlier logfiles can be deleted."
            )

        try:
            logfile = pl.read_csv(logfiles[0], separator="\t")
        except ComputeError:
            raise ValueError(
                f"Could not read logfile {logfiles[0]}. Most probably there is a line break in one of the "
                f"answer options that is written to the file. Please check manually and remove the line break."
            )
        return logfile

    def _load_session_completed_stimuli(
        self, session_identifier
    ) -> tuple[list, list, dict]:
        if session_identifier in self.sessions:
            session_path = self.sessions[session_identifier].session_folder_path
        else:
            session_path = self.skipped_sessions[session_identifier].session_folder_path

        logfile_folder = Path(f"{session_path}/logfiles")
        completed_stim_path = logfile_folder / "completed_stimuli.csv"

        completed_stimuli = pl.read_csv(completed_stim_path, separator=",")

        p_id = Sid(session_identifier).pid

        if completed_stimuli["completed"].cast(pl.Utf8).str.contains("restart").any():
            if p_id not in self.crashed_session_ids:
                self.crashed_session_ids.append(p_id)
                self.logger.warning(
                    f"Session {session_identifier} has been restarted. Only the completed stimuli will be considered."
                )
            # delete the last row in the csv if it contains 'restart' in the completed column
            completed_stimuli = completed_stimuli[:-1]

        completed_stimuli = completed_stimuli.cast({"completed": pl.Int8})
        # Only completed stimuli are considered, so the trial->stimulus mapping and
        # the completed stimulus ids always describe the same set of trials.
        completed_stimuli = completed_stimuli.filter(
            completed_stimuli["completed"] == 1
        )

        completed_stimuli_ids = completed_stimuli["stimulus_id"].to_list()
        stimulus_names = completed_stimuli["stimulus_name"].to_list()
        # get completed stimuli completes names, i.e. name + id
        completed_stimulus_names = [
            str(name) + "_" + str(stim_id)
            for name, stim_id in zip(stimulus_names, completed_stimuli_ids)
        ]

        # load trial to stimulus mapping (completed stimuli only). Sometimes there
        # are None values in the trial ids if a session was interrupted; those rows
        # are excluded so the mapping stays aligned with the stimulus names.
        stimulus_trial_pairs = [
            (trial, name)
            for trial, name in zip(
                completed_stimuli["trial_id"].to_list(), stimulus_names
            )
            if trial is not None
        ]

        stimuli_trial_mapping = {}
        for trial, name in stimulus_trial_pairs:
            if trial == "PRACTICE_1":
                trial = "PRACTICE_trial_1"
            elif trial == "PRACTICE_2":
                trial = "PRACTICE_trial_2"
            else:
                try:
                    trial = f"trial_{int(trial)}"
                except (TypeError, ValueError):
                    pass  # trial id already in the target format, leave as-is
            stimuli_trial_mapping[str(trial)] = name

        return completed_stimuli_ids, completed_stimulus_names, stimuli_trial_mapping

    def _load_stim_order_versions(self, session_identifier: str) -> pd.DataFrame:
        """Load the stimulus order versions CSV for a session's version folder.

        Reads the ``stimulus_order_versions_*.csv`` from the stimulus directory
        that applies to this session (resolved per PID).

        Parameters
        ----------
        session_identifier : str
            The session identifier.

        Returns
        -------
        pd.DataFrame
            The stimulus order versions as read from the CSV (including rows
            without a participant ID).
        """
        stimulus_dir = self._resolve_stimulus_dir(session_identifier)
        path = _ci_resolve(
            stimulus_dir
            / "config"
            / f"stimulus_order_versions_{self.language}_{self.country}_{self.lab_number}.csv"
        )
        df = pd.read_csv(path)
        # Do not drop rows with a null participant_id: the version-number
        # fallback in _resolve_stim_order_version needs them (the PID match
        # ignores nulls on its own). Filtering here made versions that are not
        # yet assigned to a participant, for example a pilot, unresolvable.
        return df

    def _load_session_stimulus_order(
        self, session_identifier, logfile_order_version: int
    ) -> list[int]:
        p_id = Sid(session_identifier).pid

        # Check whether an asc should be available for this session or not
        if session_identifier in self.sessions:
            asc_available = True
        elif session_identifier in self.skipped_sessions:
            asc_available = False
        else:
            raise KeyError(
                f"{session_identifier} not in sessions or skipped_sessions of {self.data_collection_name}."
            )

        # if the session crashed, only load the stimuli that were actually completed in that session
        incomplete_order = []
        if p_id in self.crashed_session_ids:
            if asc_available:
                incomplete_order = self.sessions[
                    session_identifier
                ].completed_stimuli_ids
            else:
                incomplete_order = self.skipped_sessions[
                    session_identifier
                ].completed_stimuli_ids

        stim_order_versions = self._load_stim_order_versions(session_identifier)

        # get the entry where the participant id matches
        stim_order_version = stim_order_versions[
            stim_order_versions["participant_id"] == int(p_id)
        ]

        if stim_order_version.empty:
            # stimulus order couldn't be found from participant ID, use version number instead
            stim_order_version = self._resolve_stim_order_version(
                session_identifier,
                p_id,
                logfile_order_version,
                asc_available,
                stim_order_versions=stim_order_versions,
            )

        if len(stim_order_version) == 1:
            # version number could be retrieved and is unique in csv. Retrieve completed stimuli
            version = stim_order_version["version_number"].values[0]
            if logfile_order_version != version:
                # If pid found and unique in csv, but number doesn't match the logfile version number
                self.logger.warning(
                    f"Stimulus order version in logfile ({logfile_order_version}) does not match the version "
                    f"in the stimulus order versions file ({version}) for participant ID {p_id}. Using the number from the csv."
                )
            stimulus_order = (
                stim_order_version.drop(columns=["version_number", "participant_id"])
                .values[0]
                .tolist()
            )

            if incomplete_order:
                # only collect completed stimuli for crashed sessions
                stimulus_order_copy = stimulus_order.copy()
                incom, comp = 0, 0
                for _ in range(len(stimulus_order)):
                    if len(incomplete_order) == incom:
                        return incomplete_order

                    if incomplete_order[incom] == stimulus_order_copy[comp]:
                        incom += 1
                        comp += 1
                        continue

                    if incomplete_order[incom] != stimulus_order_copy[comp]:
                        stimulus_order_copy.pop(incom)

                    if stimulus_order_copy == incomplete_order:
                        return incomplete_order

                    if len(stimulus_order_copy) < len(incomplete_order):
                        raise ValueError(
                            "Crashed session stimulus order is not a subset of the stimuli order which was "
                            "supposed to be completed."
                        )
                return incomplete_order

            return stimulus_order

        else:
            raise ValueError(
                f"More than one or no entry found for participant ID {p_id} in stimulus order versions. "
                f"Please add the used stimulus folder from the experiment. Or check the stimulus order versions file for missing IDs or duplicates."
            )

    def _warn_stim_order_missing(self, p_id: int) -> None:
        """Loudly warn that the participant ID is missing from the stimulus order CSV."""
        message = (
            f"Participant ID {p_id} not found in stimulus order versions. Please check the "
            f"participant IDs in the stimulus order versions file. It is possible that the team did not "
            f"upload the correct stimulus version from the experiment folder. Extracting from asc or logfile. "
            f"Gaze data may be mapped to the wrong stimuli/AOIs. Please verify that the stimulus folder "
            f"contains the exact stimuli that were presented to this participant."
        )
        banner = "-" * (len(message) + len("WARNING: "))
        print(f"\n{banner}\nWARNING: {message}\n{banner}", file=sys.stderr)
        self.logger.warning(message)

    def _resolve_stim_order_version(
        self,
        session_identifier,
        p_id: int,
        logfile_order_version: int,
        asc_available: bool,
        stim_order_versions: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Resolve the stimulus-order row when the participant ID is not in the CSV.

        Falls back to the version embedded in the ASC file (or the logfile for sessions
        without an ASC), then looks the version up by ``version_number``.

        Parameters
        ----------
        stim_order_versions : pd.DataFrame | None
            The stimulus-order CSV to search. Defaults to the collection-level
            ``self.stim_order_versions``; pass the per-session frame when stimulus
            content versions are configured.

        Raises
        ------
        ValueError
            If the ASC version disagrees with the logfile version, or if the resolved
            version cannot be found in the stimulus order versions CSV.
        """
        if stim_order_versions is None:
            stim_order_versions = self.stim_order_versions

        self._warn_stim_order_missing(p_id)

        if asc_available:
            version = int(
                extract_stimulus_version_number_from_asc(
                    self.sessions[session_identifier].asc_path
                )
            )
            if version != logfile_order_version:
                raise ValueError(
                    f"Stimulus order version in logfile ({logfile_order_version}) does not match the version "
                    f"extracted from the asc file ({version}) for participant ID {p_id}. OR no version found in asc file. "
                    f"Please check the files carefully."
                )
        else:
            # For skipped sessions, no asc file is available so we depend on the version number from the logfile
            version = logfile_order_version

        stim_order_version = stim_order_versions[
            stim_order_versions["version_number"] == version
        ]

        if stim_order_version.empty:
            raise ValueError(
                f"Stimulus order version {version} extracted from the ASC file or logfile "
                f"cannot be found in the stimulus order versions CSV. "
                f"The team should upload the correct stimulus folder."
            )

        self.logger.warning(
            "Using the stimulus order version from the ASC or logfile. "
            "The team should still upload the correct stimulus folder!"
        )
        return stim_order_version

    def _create_empty_rt_frame(self, session_identifier: str) -> pl.DataFrame:
        session = self.sessions[session_identifier]
        mapping = session.stimuli_trial_mapping
        num_of_pages_per_trial = {
            stimulus.name: [page.number for page in stimulus.pages]
            for stimulus in session.stimuli
        }

        trial_col = settings.TRIAL_COL
        page_col = settings.PAGE_COL

        rows: list[dict] = []
        for stimulus_name in mapping.values():
            if stimulus_name not in num_of_pages_per_trial:
                continue
            for page_num in num_of_pages_per_trial[stimulus_name]:
                rows.append(
                    {
                        "stimulus_name": stimulus_name,
                        "start_ts": None,
                        "stop_ts": None,
                        "start_msg": None,
                        "stop_msg": None,
                        "duration_ms": None,
                        "duration_str": None,
                        trial_col: None,
                        page_col: f"page_{page_num}",
                        "status": None,
                    }
                )

        schema = {
            "stimulus_name": pl.String,
            "start_ts": pl.String,
            "stop_ts": pl.String,
            "start_msg": pl.String,
            "stop_msg": pl.String,
            "duration_ms": pl.String,
            "duration_str": pl.String,
            trial_col: pl.String,
            page_col: pl.String,
            "status": pl.String,
        }
        return (
            pl.DataFrame(rows, schema=schema) if rows else pl.DataFrame(schema=schema)
        )

    def _categorize_asc_messages(self, session_identifier: str):
        reading_times_df = self._create_empty_rt_frame(session_identifier)
        break_msg: list[dict] = []
        other_screens: list[dict] = []
        uncategorized_msgs: list[dict] = []

        page_col = settings.PAGE_COL

        initial_ts = 0
        messages = self.sessions[session_identifier].messages

        if messages is None:
            return (
                reading_times_df,
                break_msg,
                other_screens,
                uncategorized_msgs,
                initial_ts,
            )

        if isinstance(messages, pl.DataFrame) and messages.is_empty():
            return (
                reading_times_df,
                break_msg,
                other_screens,
                uncategorized_msgs,
                initial_ts,
            )

        if isinstance(messages, pl.DataFrame):
            row_iter = messages.iter_rows(named=True)
        else:
            row_iter = messages.copy()

        for msg in row_iter:
            content = msg.get("content", msg.get("message", ""))
            ts_val = msg.get("time", msg.get("timestamp", ""))

            timestamp = str(ts_val)
            if not initial_ts:
                initial_ts = timestamp

            if settings.BREAK_REGEX.match(content):
                break_msg.append({"message": content, "timestamp": timestamp})
            elif settings.OTHER_SCREENS_REGEX.match(content):
                other_screens.append({"message": content, "timestamp": timestamp})
            elif match := settings.START_RECORDING_REGEX.match(content):
                event = match.groupdict()
                event["start_ts"] = timestamp
                reading_times_df = reading_times_df.update(
                    pl.DataFrame(event), on=["stimulus_name", page_col], how="left"
                )
            elif match := settings.STOP_RECORDING_REGEX.match(content):
                event = match.groupdict()
                event["stop_ts"] = timestamp
                reading_times_df = reading_times_df.update(
                    pl.DataFrame(event), on=["stimulus_name", page_col], how="left"
                )
            else:
                uncategorized_msgs.append({"message": content, "timestamp": timestamp})

        return (
            reading_times_df,
            break_msg,
            other_screens,
            uncategorized_msgs,
            initial_ts,
        )

    def _document_other_screens(
        self, session_idf: str, other_screens: list[dict]
    ) -> None:
        result_folder = self.output_dir / self.reports_folder / session_idf
        os.makedirs(result_folder, exist_ok=True)

        data = {
            "timestamp": [m["timestamp"] for m in other_screens],
            "screen": [m["message"] for m in other_screens],
        }
        pd.DataFrame(data).to_csv(
            result_folder / f"other_screens_{session_idf}.tsv",
            sep="\t",
            index=False,
        )

    def _document_breaks(self, session_idf: str, breaks: list[dict]) -> None:
        result_folder = self.output_dir / self.reports_folder / session_idf
        os.makedirs(result_folder, exist_ok=True)

        breaks_df: dict[str, list] = {
            "start_ts": [],
            "stop_ts": [],
            "duration_ms": [],
            "type": [],
        }
        in_break = False

        for entry in breaks:
            msg = entry["message"]
            ts = entry["timestamp"]

            if msg == "optional_break" and not in_break:
                in_break = True
                breaks_df["start_ts"].append(ts)
                breaks_df["type"].append("optional")
            elif msg == "optional_break_end" and in_break:
                in_break = False
                breaks_df["stop_ts"].append(ts)
            elif msg.split()[0] == "optional_break_duration:":
                breaks_df["duration_ms"].append(msg.split()[1])
            elif msg == "obligatory_break" and not in_break:
                in_break = True
                breaks_df["start_ts"].append(ts)
                breaks_df["type"].append("obligatory")
            elif msg == "obligatory_break_end" and in_break:
                in_break = False
                breaks_df["stop_ts"].append(ts)
            elif msg.split()[0] == "obligatory_break_duration:":
                breaks_df["duration_ms"].append(msg.split()[1])

        if in_break:
            breaks_df["stop_ts"].append(None)
            self.logger.warning(
                f"Session {session_idf} did not finish a break properly, "
                f"missing end message."
            )

        max_len = max(
            len(breaks_df["start_ts"]),
            len(breaks_df["stop_ts"]),
            len(breaks_df["duration_ms"]),
            len(breaks_df["type"]),
        )
        for col in ("start_ts", "stop_ts", "duration_ms", "type"):
            while len(breaks_df[col]) < max_len:
                breaks_df[col].append(None)

        pd.DataFrame(breaks_df).to_csv(
            result_folder / f"breaks_{session_idf}.tsv",
            sep="\t",
            index=False,
        )

    def parse_messages(self, session_identifier: str) -> list[dict]:
        (
            stimulus_times_df,
            break_msg,
            other_screens,
            uncategorized_msgs,
            initial_ts,
        ) = self._categorize_asc_messages(session_identifier)

        self._document_other_screens(session_identifier, other_screens)
        self._document_breaks(session_identifier, break_msg)

        result_folder = self.output_dir / self.reports_folder / session_identifier
        os.makedirs(result_folder, exist_ok=True)
        self._document_reading_times(
            initial_ts,
            stimulus_times_df,
            result_folder,
            session_identifier,
        )

        return uncategorized_msgs

    def _document_reading_times(
        self, initial_ts, reading_times, result_folder, session_identifier
    ):
        """Document reading times from categorized messages.

        :param initial_ts: Timestamp of the first message.
        :param reading_times: A polars DataFrame or dict of lists with start_ts/stop_ts per page.
        :param result_folder: Output directory for TSV files.
        :param session_identifier: The session identifier.
        """
        stimuli_trial_mapping = self.sessions[session_identifier].stimuli_trial_mapping

        if isinstance(reading_times, pl.DataFrame):
            valid = reading_times.filter(
                pl.col("start_ts").is_not_null() & pl.col("stop_ts").is_not_null()
            )
            reading_times_dict: dict[str, list] = {
                "start_ts": valid["start_ts"].to_list(),
                "stop_ts": valid["stop_ts"].to_list(),
                "start_msg": [],
                "stop_msg": [],
                "duration_ms": [],
                "duration_str": [],
                "trials": [],
                "pages": valid["page"].to_list(),
                "status": [],
                "stimulus_name": [],
            }
            stimuli_trial_mapping = self.sessions[
                session_identifier
            ].stimuli_trial_mapping
            for row in valid.iter_rows(named=True):
                reading_times_dict["start_msg"].append("start_recording")
                reading_times_dict["stop_msg"].append("stop_recording")
                reading_times_dict["status"].append("reading time")
                page = row["page"]
                stim = row["stimulus_name"]
                trial = None
                for t, s in stimuli_trial_mapping.items():
                    if s == stim:
                        trial = t
                        break
                reading_times_dict["trials"].append(trial or "unknown")
                reading_times_dict["stimulus_name"].append(stim)
            reading_times = reading_times_dict

        total_reading_duration_ms = 0
        negative_spans: list[str] = []

        for start, stop in zip(reading_times["start_ts"], reading_times["stop_ts"]):
            time_ms, was_negative = _reading_span_ms(start, stop)
            if was_negative:
                negative_spans.append(f"{start}->{stop}")
            reading_times["duration_ms"].append(time_ms)
            reading_times["duration_str"].append(convert_to_time_str(time_ms))
            total_reading_duration_ms += time_ms

        # calculate duration between pages
        temp_stop_ts = reading_times["stop_ts"].copy()
        temp_stop_ts.insert(0, initial_ts)
        temp_stop_ts = temp_stop_ts[:-1]
        total_set_up_time_ms = 0

        for stop, start, page, trial in zip(
            temp_stop_ts,
            reading_times["start_ts"],
            reading_times["pages"],
            reading_times["trials"],
        ):
            time_ms, was_negative = _reading_span_ms(stop, start)
            if was_negative:
                negative_spans.append(f"{stop}->{start}")
            reading_times["duration_ms"].append(time_ms)
            reading_times["duration_str"].append(convert_to_time_str(time_ms))
            reading_times["start_msg"].append("time inbetween")
            reading_times["stop_msg"].append("time inbetween")
            reading_times["start_ts"].append(stop)
            reading_times["stop_ts"].append(start)
            reading_times["trials"].append(trial)
            total_set_up_time_ms += time_ms

            if trial in stimuli_trial_mapping:
                reading_times["stimulus_name"].append(stimuli_trial_mapping[trial])
            else:
                reading_times["stimulus_name"].append("unknown")

            reading_times["pages"].append(page)
            reading_times["status"].append("time before pages and breaks")

        try:
            df = pd.DataFrame(
                {
                    "start_ts": reading_times["start_ts"],
                    "stop_ts": reading_times["stop_ts"],
                    "trial": reading_times["trials"],
                    "stimulus": reading_times["stimulus_name"],
                    "page": reading_times["pages"],
                    "type": reading_times["status"],
                    "duration_ms": reading_times["duration_ms"],
                    "duration-hh:mm:ss": reading_times["duration_str"],
                }
            )
        except ValueError:
            raise ValueError(
                f"The reading times could not be computed properly for {session_identifier}. Please check 1) if the completed "
                "stimulus file is alright (i.e. completed should be 1 for all, no missing values, etc.), "
                "2) if anything happened during the session (crash or "
                "technical errors, e.g. check the end of the asc file if it looks normal), 3) contact the support team."
            )

        df.to_csv(
            result_folder / f"times_per_page_{session_identifier}.tsv",
            sep="\t",
            index=False,
        )
        if negative_spans:
            self.logger.warning(
                "Clamped %d negative reading-time span(s) to 0 for %s "
                "(for example %s). Check the order of the ASC start/stop messages.",
                len(negative_spans),
                session_identifier,
                ", ".join(negative_spans[:3]),
            )
        sum_df = _summarize_reading_times(df)
        duration = sum_df["duration_ms"].apply(lambda x: convert_to_time_str(x))
        sum_df["duration-hh:mm:ss"] = duration

        sum_df.to_csv(
            result_folder / f"times_per_stimulus_{session_identifier}.tsv",
            index=False,
            sep="\t",
        )

        start_end_per_stimulus = _build_stimulus_start_end_ts(sum_df)

        self.sessions[session_identifier].stimulus_start_end_ts = start_end_per_stimulus

        total_times = pd.DataFrame(
            {
                "session": session_identifier,
                "lab": self.lab_number,
                "language": self.language,
                "total_trials": [len(sum_df) / 2],
                "total_pages": [len(df) / 2],
                "total_reading_time": [convert_to_time_str(total_reading_duration_ms)],
                "total_non-reading_time": [convert_to_time_str(total_set_up_time_ms)],
                "total_exp_time": [
                    convert_to_time_str(
                        total_reading_duration_ms + total_set_up_time_ms
                    )
                ],
            }
        )

        if os.path.exists(self.data_root.parent / "total_reading_times.tsv"):
            temp_total_times = pd.read_csv(
                self.data_root.parent / "total_reading_times.tsv", sep="\t"
            )
            if session_identifier not in temp_total_times["session"].tolist():
                total_times = pd.concat(
                    [temp_total_times, total_times], ignore_index=True
                )

        total_times.to_csv(
            self.data_root.parent / "total_reading_times.tsv", sep="\t", index=False
        )

    def _check_asc_validation(self, session_identifier: str) -> None:
        """
        Check the validations in the asc file for the specified session.
        :param session_identifier: The session identifier.
        :param gaze: If the gaze data has already been created it can be passed as an argument.
        If not it will be created.
        """

        # sort stimulus times into list by start and end time
        sorted_stimuli = sorted(
            self.sessions[session_identifier].stimulus_start_end_ts,
            key=lambda x: float(x["start_ts"]),
        )
        sorted_start_end = []
        for stimulus in sorted_stimuli:
            sorted_start_end.append(
                {
                    "message": f"{stimulus['stimulus']}_start",
                    "time": float(stimulus["start_ts"]),
                }
            )
            sorted_start_end.append(
                {
                    "message": f"{stimulus['stimulus']}_end",
                    "time": float(stimulus["stop_ts"]),
                }
            )

        check_validation_requirements(
            self.sessions[session_identifier].validations,
            self.sessions[session_identifier].calibrations,
            self.sessions[session_identifier].sanity_report_path,
            sorted_start_end,
        )

    def _check_stimuli_gaze_frame(self, gaze, stimuli, session_identifier):
        """Check the gaze data for all stimuli screens of a session."""
        logging.debug(
            f"Checking asc file all screens for {session_identifier} all screens."
        )

        sanity_check_gaze_frame(
            gaze, stimuli, self.sessions[session_identifier].sanity_report_path
        )

    def _check_asc_messages(self, stimuli, messages, session_identifier: str) -> None:
        """
        Check the instructions for the specified session.
        :param messages:
        :param stimuli:
        :param session_identifier: The session identifier. eg "005_ET_EE_1_ET1"
        """

        p_id = Sid(session_identifier).pid
        check_messages(
            messages,
            stimuli,
            self.sessions[session_identifier].sanity_report_path,
            self.sessions[session_identifier].completed_stimuli_ids,
            restarted=p_id in self.crashed_session_ids,
        )

    def _check_logfiles(self, stimuli, session_identifier):
        """
        Check the experiment logfile for the specified session.
        :param stimuli:
        :param session_identifier: The session identifier.
        :return:
        """

        check_all_screens_logfile(
            self.sessions[session_identifier].logfile,
            stimuli,
            self.sessions[session_identifier].sanity_report_path,
        )

    @staticmethod
    def _check_avg_fix_durations(gaze: pm.Gaze) -> pl.DataFrame:
        """
        Check the average fixation durations for the specified session.
        :param gaze: Gaze object for this session.
        """

        # for each gaze and page compute the average fixation duration
        fixation_durations_page_avg = (
            gaze.events.frame.filter(pl.col("name") == settings.FIXATION)
            .group_by(gaze.trial_columns)
            .agg(
                [
                    pl.col("duration").mean().alias("mean_fixation_duration_ms"),
                    pl.col("duration").median().alias("median_fixation_duration_ms"),
                    pl.col("duration").max().alias("max_fixation_duration_ms"),
                    pl.col("duration").min().alias("min_fixation_duration_ms"),
                    pl.col("duration").sum().alias("sum_fixation_duration_ms"),
                ]
            )
        )

        # write to file
        return fixation_durations_page_avg

    def _compute_per_trial_loss_table(self, session_name: str):
        data_loss_df = getattr(
            self.sessions[session_name], "_per_trial_data_loss", None
        )
        blink_loss_df = getattr(
            self.sessions[session_name], "_per_trial_blink_loss", None
        )

        if data_loss_df is None and blink_loss_df is None:
            return None

        trial_cols = ["trial", "stimulus"]
        if data_loss_df is not None and blink_loss_df is not None:
            return data_loss_df.join(blink_loss_df, on=trial_cols, how="left")
        if data_loss_df is not None:
            return data_loss_df
        return blink_loss_df

    def _compute_per_page_loss_table(self, session_name: str):
        data_loss_df = getattr(self.sessions[session_name], "_per_page_data_loss", None)
        blink_loss_df = getattr(
            self.sessions[session_name], "_per_page_blink_loss", None
        )

        if data_loss_df is None and blink_loss_df is None:
            return None

        page_cols = ["trial", "stimulus", "page"]
        if data_loss_df is not None and blink_loss_df is not None:
            table = data_loss_df.join(blink_loss_df, on=page_cols, how="left")
        elif data_loss_df is not None:
            table = data_loss_df
        else:
            table = blink_loss_df

        return table.with_columns(
            pl.col("page")
            .map_elements(
                self._page_type,
                return_dtype=pl.Utf8,
            )
            .alias("page_type")
        )

    def _data_loss_by_page_type(self, session_name: str):
        """Aggregate mean data-loss ratio per page type.

        Parameters
        ----------
        session_name : str
            The session identifier.

        Returns
        -------
        pl.DataFrame | None
            A DataFrame with ``page_type``, ``mean_data_loss`` and ``num_pages``
            columns, or ``None`` if no per-page data-loss data is available.
        """
        per_page_loss = self._compute_per_page_loss_table(session_name)
        if per_page_loss is None or per_page_loss.is_empty():
            return None
        if "data_loss_ratio" not in per_page_loss.columns:
            return None
        return (
            per_page_loss.group_by("page_type")
            .agg(
                pl.col("data_loss_ratio").mean().alias("mean_data_loss"),
                pl.len().alias("num_pages"),
            )
            .sort("page_type")
        )

    def _page_type(self, page: str) -> str:
        """Classify a page name into a coarse page type.

        Parameters
        ----------
        page : str
            The page name from the gaze trial_columns.

        Returns
        -------
        str
            One of "reading", "question", "rating", or "other".
        """
        if page.startswith("page_"):
            return "reading"
        if page.startswith("question_"):
            return "question"
        if page.startswith("familiarity_rating_screen") or page == (
            "subject_difficulty_screen"
        ):
            return "rating"
        return "other"

    def _load_psychometric_tests(self, session_identifier: str):
        # Match the eye-tracking session to a psychometric test folder
        # We use Sid.equals_soft to handle prefix variations (e.g., ET1 matching PT1 or PT2)
        try:
            et_sid = Sid(session_identifier)
        except (ValueError, TypeError):
            et_sid = None

        if self.psychometric_tests:
            pt_dir = settings.PSYCHOMETRIC_TESTS_DIR
            found_path = None

            if pt_dir.exists() and et_sid:
                # Iterate through folders in psychometric-tests-sessions
                for potential_dir in pt_dir.iterdir():
                    if potential_dir.is_dir():
                        try:
                            folder_sid = Sid(potential_dir.name)
                            if et_sid.equals_soft(folder_sid):
                                found_path = potential_dir
                                break
                        except (ValueError, TypeError):
                            continue

            if found_path:
                self.sessions[
                    session_identifier
                ].psychometric_tests_session = found_path.name
            else:
                self.logger.warning(
                    f"No psychometric tests session folder for {session_identifier} could be found. Please check."
                )

    def _extract_question_answers(
        self, stimuli: list[Stimulus], session_identifier: str
    ) -> None:
        check_comprehension_question_answers(
            self.sessions[session_identifier].logfile,
            stimuli,
            self.sessions[session_identifier].sanity_report_path,
        )

    def _create_plots(self, gaze, stimuli, session_identifier, directory, aoi=False):
        plot_dir = directory / f"{session_identifier}_plots"
        plot_dir.mkdir(exist_ok=True)

        plot_main_sequence(gaze.events, plot_dir)

        # Clone/unnest the gaze and index pages once, instead of per stimulus.
        data, samples_by_key, events_by_key = build_page_frames(gaze)

        for stimulus in stimuli:
            plot_gaze(
                gaze,
                stimulus,
                plot_dir,
                aoi_image=aoi,
                data=data,
                samples_by_key=samples_by_key,
                events_by_key=events_by_key,
            )


if __name__ == "__main__":
    settings.setup_logging()
    data_collection_folder = "MultiplEYE_ET_EE_Tartu_1_2025"

    this_repo = Path.cwd().parent

    data_folder_path = this_repo / "data" / data_collection_folder

    multipleye = MultipleyeDataCollection.create_from_data_folder(str(data_folder_path))
    # multipleye.add_recorded_sessions(data_root= data_folder_path / 'eye-tracking-sessions' / 'core_dataset', convert_to_asc=False, session_folder_regex=r"005_ET_EE_1_ET1")
    # multipleye.create_gaze_frame("005_ET_EE_1_ET1")
    multipleye.create_sanity_check_report(["005_ET_EE_1_ET1", "006_ET_EE_1_ET1"])
    multipleye.create_experiment_frame("005_ET_EE_1_ET1")
