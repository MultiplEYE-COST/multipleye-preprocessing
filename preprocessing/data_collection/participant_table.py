"""Build the participant-level overview table (``participants.csv``)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import polars as pl
import yaml

from ..config import settings
from ..models.sid import Sid
from ..utils.pq_normalisation import (
    build_mapping,
    find_pq_data,
    find_questionnaire_files,
    normalise_pq,
)
from .completeness import (
    actual_tests_from_pt_rows,
    cross_source_status,
    expected_tests_from_configs,
    read_sheet_expectations,
)
from .experimenter_doc import ExperimenterDoc
from .participant_info import PSYCHOMETRIC_KEY_SCORES, _bi_monolingualism_from_pq

LANGUAGE_SLOTS = [
    "native_language_1",
    "native_language_2",
    "native_language_3",
    "use_language",
    "dominant_language",
    "additional_read_language_1",
    "additional_read_language_2",
    "additional_read_language_3",
    "additional_read_language_4",
]

READING_QUESTIONS = [
    "academic",
    "magazine",
    "newspaper",
    "email",
    "fiction",
    "nonfiction",
    "internet",
    "other",
]

PQ_BASE_FIELDS = [
    "pq_gender",
    "pq_age",
    "pq_years_education",
    "pq_years_education_open_ended",
    "pq_level_education",
    "pq_socio_economic_status",
    "pq_childhood_languages",
    "pq_tiredness",
    "pq_eyewear",
    "pq_alcohol_yesterday",
    "pq_alcohol_today",
]

DOC_FIELDS = {
    "doc_setup_deviation": "setup_deviation",
    "doc_technical_issues": "technical_issues",
    "doc_interruptions": "interruptions",
    "doc_irritations": "irritations",
    "doc_abortion": "abortion",
    "doc_file_issues": "file_issues",
    "doc_comments": "comments",
}

PSYCHOMETRIC_TEST_PREFIXES = (
    "LWMC",
    "RAN",
    "Stroop",
    "Flanker",
    "WikiVocab",
    "PLAB",
)

PARTICIPANT_YAML_DOCUMENTATION = {
    "participant_csv": "participants.csv",
    "note": "Full tabular participant output for download and manual inspection",
}


@dataclass
class ParticipantGroup:
    """One row of the participant table."""

    label: str
    pids: set[str]
    sessions: set[str] | None = None


def _pid(value: object) -> str | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return f"{number:03d}"


def _session_pid(session_id: str) -> str | None:
    try:
        return _pid(Sid(session_id).pid)
    except (ValueError, TypeError):
        return None


def _get(value: object, *keys: str, default: object = None) -> object:
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def _join(values: list[object], separator: str = "; ") -> str:
    return separator.join(
        str(v) for v in values if not _is_missing(v) and v != "unknown"
    )


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _first_value(*values: object) -> object:
    for value in values:
        if not _is_missing(value):
            return value
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _sum_numbers(overviews: list[dict], *keys: str) -> float:
    total = 0.0
    for overview in overviews:
        value = _number(_get(overview, *keys))
        if value is not None:
            total += value
    return round(total, 3)


def _et_sessions(data_collection) -> dict[str, str]:
    sessions: dict[str, str] = {}
    for session_id in getattr(data_collection, "sessions", {}):
        pid = _session_pid(session_id)
        if pid is not None:
            sessions[session_id] = pid
    return sessions


def _filter_sessions(sessions: dict[str, str]) -> dict[str, str]:
    excluded = set(settings.EXCLUDE_SESSIONS or [])
    included = set(settings.INCLUDE_SESSIONS or [])
    result = {}
    for session_id, pid in sessions.items():
        if session_id in excluded:
            continue
        if included and session_id not in included:
            continue
        result[session_id] = pid
    return result


def _pq_files() -> list[Path]:
    dataset_dir = Path(settings.DATASET_DIR)
    files: list[Path] = []
    for root in [dataset_dir, *dataset_dir.glob("participant_questionnaire*")]:
        if not root.exists():
            continue
        files.extend(root.glob("*_pq_data.json"))
    documentation = dataset_dir / "documentation"
    if documentation.exists():
        files.extend(documentation.rglob("*_pq_data.json"))
    return files


def _pq_pids() -> set[str]:
    pids: set[str] = set()
    for path in _pq_files():
        pid = _pid(path.name.split("_", 1)[0])
        if pid is not None:
            pids.add(pid)
    return pids


def _load_pt_table() -> pl.DataFrame | None:
    folder = Path(settings.OUTPUT_DIR) / settings.PSYCHOMETRIC_TESTS_FOLDER
    for name in (
        f"psychometric_results_{settings.DATA_COLLECTION_NAME}.csv",
        f"psychometric_results_{settings.DATA_COLLECTION_NAME}_merged.csv",
    ):
        path = folder / name
        if path.exists():
            try:
                return pl.read_csv(path, infer_schema_length=0)
            except Exception:
                continue
    return None


def _pt_rows_from_folders() -> list[dict]:
    folder = Path(settings.PSYCHOMETRIC_TESTS_DIR)
    rows: list[dict] = []
    if not folder.exists():
        return rows
    for session in folder.iterdir():
        if not session.is_dir():
            continue
        try:
            sid = Sid(session.name)
        except (ValueError, TypeError):
            continue
        tests = [
            child.name
            for child in session.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ]
        row = {"session_id": str(sid), "participant_id": sid.pid}
        for test, folder_name in (
            ("LWMC", "WMC"),
            ("RAN", "RAN"),
            ("Stroop", "Stroop_Flanker"),
            ("Flanker", "Stroop_Flanker"),
            ("WikiVocab", "WikiVocab"),
            ("PLAB", "PLAB"),
        ):
            row[f"{test}_Done"] = 1 if folder_name in tests else 0
        rows.append(row)
    return rows


def _pt_rows(prefer_table: bool = True) -> list[dict]:
    if not prefer_table:
        return _pt_rows_from_folders()
    table = _load_pt_table()
    if table is None:
        return _pt_rows_from_folders()
    rows = []
    for row in table.iter_rows(named=True):
        pid = _pid(row.get("participant_id"))
        if pid is None:
            continue
        rows.append({**row, "participant_id": pid})
    return rows


def _pt_session_id(row: dict) -> str:
    return str(row.get("session_id") or "")


def _pt_status(rows: list[dict]) -> str:
    statuses: list[str] = []

    subtasks = [
        name
        for name, key in (
            ("MU", "LWMC_MU_Done"),
            ("OS", "LWMC_OS_Done"),
            ("SentS", "LWMC_SentS_Done"),
            ("SSTM", "LWMC_SSTM_Done"),
        )
        if any(int(row.get(key) or 0) == 1 for row in rows)
    ]
    if len(subtasks) == 4:
        statuses.append("LWMC:done")
    elif subtasks:
        statuses.append(f"LWMC:partial({','.join(subtasks)})")
    elif any(int(row.get("LWMC_Done") or 0) == 1 for row in rows):
        statuses.append("LWMC:done")

    for test, key in (
        ("RAN", "RAN_Done"),
        ("Stroop", "Stroop_Done"),
        ("Flanker", "Flanker_Done"),
        ("WikiVocab", "WikiVocab_Done"),
        ("PLAB", "PLAB_Done"),
    ):
        if any(int(row.get(key) or 0) == 1 for row in rows):
            statuses.append(f"{test}:done")

    return "; ".join(statuses)


def _build_groups(
    et_sessions: dict[str, str], pt_rows: list[dict], pq_pids: set[str]
) -> list[ParticipantGroup]:
    pt_pids = {row["participant_id"] for row in pt_rows}
    all_pids = set(et_sessions.values()) | pt_pids | pq_pids

    explicit = []
    for entry in settings.PARTICIPANT_GROUPS or []:
        label = str(entry["label"])
        pids = {_pid(pid) for pid in entry.get("pids", [])}
        pids.discard(None)
        sessions = entry.get("sessions")
        explicit.append(
            ParticipantGroup(
                label=label,
                pids=set(pids),
                sessions=set(map(str, sessions)) if sessions else None,
            )
        )

    claimed_pids: set[str] = set()
    claimed_sessions: set[str] = set()
    groups: list[ParticipantGroup] = []

    for group in explicit:
        if group.sessions is None:
            claimed_pids |= group.pids
        else:
            claimed_sessions |= group.sessions
        groups.append(group)

    for pid in sorted(all_pids):
        if pid in claimed_pids:
            continue
        sessions = {
            sid for sid, session_pid in et_sessions.items() if session_pid == pid
        }
        sessions |= {
            _pt_session_id(row) for row in pt_rows if row["participant_id"] == pid
        }
        sessions -= claimed_sessions
        if not sessions and pid in claimed_pids:
            continue
        groups.append(
            ParticipantGroup(label=pid, pids={pid}, sessions=sessions or None)
        )

    labels = [group.label for group in groups]
    if len(labels) != len(set(labels)):
        raise ValueError(
            "Duplicate participant row label. A PID is split across a configured "
            "group and an ungrouped row; give the remaining sessions an explicit "
            "group with a unique 3-digit label."
        )

    return groups


def collect_participant_sources(
    data_collection, prefer_table: bool = True
) -> tuple[dict[str, str], list[dict], set[str]]:
    """Collect ET sessions, PT rows and PQ PIDs for the participant table."""
    et_sessions = _filter_sessions(_et_sessions(data_collection))
    pt_rows = [
        row
        for row in _pt_rows(prefer_table)
        if _session_id_allowed(_pt_session_id(row), apply_include=False)
    ]
    pq_pids = _pq_pids()
    for session in getattr(data_collection, "sessions", {}).values():
        folder = Path(getattr(session, "session_folder_path", ""))
        for pq_file in folder.glob("*_pq_data.json"):
            pid = _pid(pq_file.name.split("_", 1)[0])
            if pid is not None:
                pq_pids.add(pid)
    return et_sessions, pt_rows, pq_pids


def build_participant_groups(
    et_sessions: dict[str, str], pt_rows: list[dict], pq_pids: set[str]
) -> list[ParticipantGroup]:
    """Build participant groups from the collected sources."""
    return _build_groups(et_sessions, pt_rows, pq_pids)


def _pq_values(
    group: ParticipantGroup,
    et_sessions: dict[str, str],
    mapping: dict | None,
    data_collection,
) -> dict:
    group_sessions = group.sessions
    if group_sessions is None:
        group_sessions = {sid for sid, pid in et_sessions.items() if pid in group.pids}
    session_dirs = [
        Path(data_collection.sessions[sid].session_folder_path)
        for sid in group_sessions
        if sid in getattr(data_collection, "sessions", {})
    ]
    questionnaire_dirs = list(
        Path(settings.DATASET_DIR).glob("participant_questionnaire*")
    )
    questionnaire_dirs.append(Path(settings.DATASET_DIR) / "documentation")

    pq_path = None
    for pid in sorted(group.pids):
        pq_path = find_pq_data(pid, session_dirs, questionnaire_dirs)
        if pq_path is not None:
            break
    if pq_path is None:
        return {}

    try:
        pq = json.loads(pq_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(pq, dict):
        return {}
    if "native_language_1_academic_reading_time" not in pq:
        from ..utils.fix_questionnaire_data import remap_wrong_pq_values

        pq = remap_wrong_pq_values(pq)
    if mapping is None:
        return pq
    return {**pq, **normalise_pq(pq, mapping)["values"]}


def _pq_columns(pq: dict) -> dict:
    result = {
        field: _first_value(pq.get(field), pq.get(field.removeprefix("pq_")))
        for field in PQ_BASE_FIELDS
    }
    result["pq_bi_monolingualism"] = _bi_monolingualism_from_pq(pq)
    for slot in LANGUAGE_SLOTS:
        result[f"pq_{slot}"] = _first_value(pq.get(slot), pq.get(f"pq_raw_{slot}"))
    reading_times = {}
    for slot in LANGUAGE_SLOTS:
        values = {}
        for question in READING_QUESTIONS:
            value = pq.get(f"pq_{slot}_{question}_reading_time")
            if not _is_missing(value):
                values[question] = value
        if values:
            reading_times[slot] = values
    result["pq_language_reading_times"] = (
        json.dumps(reading_times, ensure_ascii=False) if reading_times else ""
    )
    return result


def _weighted_ratio(overviews: list[dict], key: str) -> float | None:
    weighted = 0.0
    total_duration = 0.0
    for overview in overviews:
        value = _number(_get(overview, "data_quality", key))
        duration = _number(
            _get(overview, "experiment_procedure", "total_session_duration_s")
        )
        if value is None or duration is None or duration <= 0:
            continue
        weighted += value * duration
        total_duration += duration
    if total_duration <= 0:
        return None
    return round(weighted / total_duration, 6)


def _et_columns(
    group: ParticipantGroup, data_collection
) -> tuple[dict, dict[str, dict], list[dict]]:
    if group.sessions is None:
        session_ids = sorted(
            sid
            for sid, pid in _et_sessions(data_collection).items()
            if pid in group.pids
        )
    else:
        session_ids = sorted(
            sid
            for sid in group.sessions
            if sid in getattr(data_collection, "sessions", {})
        )
    overviews = []
    stats = []
    for session_id in session_ids:
        session = data_collection.sessions[session_id]
        overview = session.create_overview(
            getattr(data_collection, "experimenter_doc", None)
        )
        overviews.append(overview)
        trials = overview.get("trials")
        trials = trials if isinstance(trials, list) else []
        experiment_trials = [t for t in trials if not t.get("is_practice")]
        practice_trials = [t for t in trials if t.get("is_practice")]
        stats.append(
            {
                "session_id": session_id,
                "status": "conducted",
                "trials_completed": len(experiment_trials),
                "trials_total": max(
                    settings.NUM_TRIALS - settings.NUM_PRACTICE_TRIALS, 0
                ),
                "trials_practice": len(practice_trials),
                "reading_time_s": _get(
                    overview, "experiment_procedure", "total_reading_time_s"
                ),
                "session_duration_s": _get(
                    overview, "experiment_procedure", "total_session_duration_s"
                ),
                "data_loss_ratio": _get(
                    overview, "data_quality", "session_total_data_loss_ratio"
                ),
                "blink_loss_ratio": _get(
                    overview, "data_quality", "session_blink_loss_ratio"
                ),
                "validation_error_dva": _get(
                    overview, "calibration_validation", "avg_validation_error_dva"
                ),
            }
        )

    def _sum(key: str) -> float:
        values = [_number(_get(stat, key)) for stat in stats]
        values = [value for value in values if value is not None]
        return round(sum(values), 3) if values else 0.0

    stimuli = []
    for overview in overviews:
        trials = overview.get("trials")
        if not isinstance(trials, list):
            continue
        for trial in trials:
            if not trial.get("is_practice") and trial.get("stimulus_name"):
                stimuli.append(trial["stimulus_name"])

    validation_errors = [
        value
        for overview in overviews
        if (
            value := _number(
                _get(
                    overview,
                    "calibration_validation",
                    "avg_validation_error_dva",
                )
            )
        )
        is not None
    ]

    columns = {
        "et_session_ids": "; ".join(session_ids),
        "et_session_status": "conducted" if session_ids else "",
        "et_trials_completed": _sum("trials_completed"),
        "et_trials_total": _sum("trials_total"),
        "et_trials_practice": _sum("trials_practice"),
        "et_stimuli_presented": "; ".join(sorted(set(stimuli))),
        "et_total_reading_time_s": _sum("reading_time_s"),
        "et_total_session_duration_s": _sum("session_duration_s"),
        "et_total_question_time_ms": _sum_numbers(
            overviews, "experiment_procedure", "total_question_time_ms"
        ),
        "et_total_rating_time_ms": _sum_numbers(
            overviews, "experiment_procedure", "total_rating_time_ms"
        ),
        "et_total_break_time_s": _sum_numbers(
            overviews, "experiment_procedure", "total_break_time_s"
        ),
        "et_blink_loss_ratio": _weighted_ratio(overviews, "session_blink_loss_ratio"),
        "et_data_loss_ratio": _weighted_ratio(
            overviews, "session_total_data_loss_ratio"
        ),
        "et_avg_validation_error_dva": (
            round(sum(validation_errors) / len(validation_errors), 3)
            if validation_errors
            else None
        ),
        "et_num_calibrations": _sum_numbers(
            overviews, "calibration_validation", "num_calibrations"
        ),
        "et_num_validations": _sum_numbers(
            overviews, "calibration_validation", "num_validations"
        ),
        "et_was_interrupted": any(
            _get(o, "experiment_procedure", "was_session_interrupted") is True
            for o in overviews
        ),
        "et_restarted_session_names": _join(
            [
                _get(o, "experiment_procedure", "restarted_session_name")
                for o in overviews
            ]
        ),
        "et_session_stats": json.dumps(stats, ensure_ascii=False) if stats else "",
    }
    return columns, {"overviews": overviews}, stats


def _doc_values(
    experimenter_doc: ExperimenterDoc | None, pids: set[str]
) -> tuple[dict, set[int]]:
    result = {field: "" for field in DOC_FIELDS}
    result["doc_extras"] = ""
    matched: set[int] = set()
    if experimenter_doc is None:
        return result, matched

    for column, source in DOC_FIELDS.items():
        collected = []
        for frame in (experimenter_doc.et_frame, experimenter_doc.pt_frame):
            if frame is None or "participant_id" not in frame.columns:
                continue
            for row in frame.iter_rows(named=True):
                pid = _pid(row.get("participant_id"))
                if pid is None or pid not in pids:
                    continue
                matched.add(int(pid))
                value = row.get(source)
                if value not in (None, ""):
                    collected.append(value)
        result[column] = " | ".join(str(v) for v in collected)

    extras = []
    frame = experimenter_doc.et_frame
    if frame is not None and "participant_id" in frame.columns:
        extra_columns = [
            column
            for column in frame.columns
            if column not in ExperimenterDoc.et_columns
        ]
        for row in frame.iter_rows(named=True):
            pid = _pid(row.get("participant_id"))
            if pid is None or pid not in pids:
                continue
            entry = {column: row.get(column) for column in extra_columns}
            if any(value not in (None, "") for value in entry.values()):
                extras.append(entry)
    result["doc_extras"] = json.dumps(extras, ensure_ascii=False) if extras else ""
    return result, matched


def _preflight_values(
    participant_id: str, session_ids: list[str], data_collection
) -> dict:
    errors = getattr(data_collection, "preflight_errors", {}) or {}
    warnings = getattr(data_collection, "preflight_warnings", {}) or {}
    if not errors and not warnings:
        return {"preflight_status": "unknown", "preflight_failed": ""}

    needles = {participant_id, str(int(participant_id))}
    needles.update(session_ids)
    failed_errors = [
        group
        for group, messages in errors.items()
        if any(needle in message for message in messages for needle in needles)
    ]
    failed_warnings = [
        group
        for group, messages in warnings.items()
        if any(needle in message for message in messages for needle in needles)
    ]
    if failed_errors:
        return {
            "preflight_status": "errors",
            "preflight_failed": "; ".join(failed_errors),
        }
    if failed_warnings:
        return {
            "preflight_status": "warnings",
            "preflight_failed": "; ".join(failed_warnings),
        }
    return {"preflight_status": "ok", "preflight_failed": ""}


def _unassigned_rows(
    experimenter_doc: ExperimenterDoc | None, assigned: set[int]
) -> list[dict]:
    rows: list[dict] = []
    if experimenter_doc is None:
        return rows
    for frame in (experimenter_doc.et_frame, experimenter_doc.pt_frame):
        if frame is None or "participant_id" not in frame.columns:
            continue
        for row in frame.iter_rows(named=True):
            raw = row.get("participant_id")
            pid = _pid(raw)
            if pid is not None and int(pid) in assigned:
                continue
            reason = (
                "doc sheet PID not parseable; please check"
                if pid is None
                else "doc sheet PID not in ET/PT/PQ data; please check"
            )
            result = {field: "" for field in DOC_FIELDS}
            for column, source in DOC_FIELDS.items():
                value = row.get(source)
                if value not in (None, ""):
                    result[column] = str(value)
            result["doc_extras"] = ""
            rows.append(
                {
                    "participant_id": str(raw),
                    **result,
                    "manual_comments": reason,
                }
            )
    return rows


def build_participant_table(data_collection) -> pl.DataFrame:
    """Build one row per participant (ET, PT and questionnaire union)."""
    et_sessions, pt_rows, pq_pids = collect_participant_sources(data_collection)
    groups = build_participant_groups(et_sessions, pt_rows, pq_pids)

    experimenter_doc = getattr(data_collection, "experimenter_doc", None)
    expectations = read_sheet_expectations(experimenter_doc)
    config_expected = expected_tests_from_configs()
    actual_tests = actual_tests_from_pt_rows(pt_rows)
    num_sessions = getattr(data_collection, "num_sessions", 1) or 1
    check_sheet = experimenter_doc is not None

    question_path, language_path = find_questionnaire_files(
        settings.DATASET_DIR, getattr(data_collection, "language", "")
    )
    mapping = (
        build_mapping(question_path, language_path)
        if question_path is not None
        else None
    )

    rows: list[dict] = []
    assigned_pids: set[int] = set()
    for group in groups:
        pq = _pq_values(group, et_sessions, mapping, data_collection)
        pq_columns = _pq_columns(pq) if pq else {}
        et_columns, _et_meta, _stats = _et_columns(group, data_collection)
        group_pt_rows = [row for row in pt_rows if row["participant_id"] in group.pids]
        doc_columns, matched = _doc_values(experimenter_doc, group.pids)
        assigned_pids |= matched
        session_ids = (
            [sid for sid, pid in et_sessions.items() if pid in group.pids]
            if group.sessions is None
            else [sid for sid in group.sessions if sid in et_sessions]
        )
        completeness = cross_source_status(
            group,
            et_sessions,
            pt_rows,
            pq_pids,
            expectations,
            config_expected,
            actual_tests,
            num_sessions,
            check_sheet=check_sheet,
        )
        row = {
            "participant_id": group.label,
            "pids": "; ".join(sorted(group.pids)),
            **et_columns,
            "pt_session_ids": "; ".join(
                sorted({_pt_session_id(row) for row in group_pt_rows})
            ),
            "pt_tests_status": _pt_status(group_pt_rows),
            **completeness,
            **pq_columns,
            **doc_columns,
            **_preflight_values(group.label, session_ids, data_collection),
            "manual_comments": "",
        }
        rows.append(row)

    assigned_pids |= {int(pid) for pid in pq_pids}
    rows.extend(_unassigned_rows(experimenter_doc, assigned_pids))

    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows)


def _split_cell(value: object) -> list[str]:
    """Split a ``"; "`` separated table cell into a list."""
    if _is_missing(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _json_object(value: object) -> dict:
    """Parse a JSON object cell, returning an empty dict on invalid input."""
    if _is_missing(value):
        return {}
    try:
        payload = json.loads(str(value))
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _psychometric_test_name(key: str) -> str:
    """Return the psychometric test prefix for a curated score column."""
    for prefix in PSYCHOMETRIC_TEST_PREFIXES:
        if key.startswith(prefix):
            return prefix
    return key.split("_", 1)[0]


def _psychometric_value(key: str, value: object) -> object | None:
    """Normalise a psychometric result cell for the YAML view."""
    if _is_missing(value):
        return None
    if key.endswith("_Done"):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "1.0", "true", "yes"}
        return bool(value)
    number = _number(value)
    if number is not None:
        return None if _is_missing(number) else number
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in {"unknown", "nan", "none", "null", "na", "n/a"}:
            return None
        return text
    return value


def _curated_psychometric_scores(rows: list[dict]) -> dict[str, dict]:
    """Nest the curated psychometric score subset by test."""
    scores: dict[str, dict] = {}
    for row in rows:
        for key in PSYCHOMETRIC_KEY_SCORES:
            value = _psychometric_value(key, row.get(key))
            if value is None:
                continue
            test_scores = scores.setdefault(_psychometric_test_name(key), {})
            if key.endswith("_Done"):
                test_scores[key] = bool(test_scores.get(key, False) or value)
            else:
                test_scores.setdefault(key, value)
    return scores


def _participant_yaml_record(row: dict, pt_rows_by_pid: dict[str, list[dict]]) -> dict:
    """Convert one participant table row into the nested YAML record."""
    source_pids = _split_cell(row.get("pids"))
    psychometric_session_ids = _split_cell(row.get("pt_session_ids"))
    record = {
        "participant_id": row.get("participant_id"),
        "source_pids": source_pids,
        "session_ids": _split_cell(row.get("et_session_ids")),
        "psychometric_session_ids": psychometric_session_ids,
    }

    for key, value in row.items():
        if not key.startswith("pq_") or _is_missing(value):
            continue
        if key == "pq_language_reading_times":
            reading_times = _json_object(value)
            if reading_times:
                record[key] = reading_times
        else:
            record[key] = value

    allowed_sessions = set(psychometric_session_ids)
    group_pt_rows: list[dict] = []
    for pid in source_pids:
        for pt_row in pt_rows_by_pid.get(pid, []):
            session_id = _pt_session_id(pt_row)
            if allowed_sessions and session_id and session_id not in allowed_sessions:
                continue
            group_pt_rows.append(pt_row)

    scores = _curated_psychometric_scores(group_pt_rows)
    if scores:
        record["psychometric_tests"] = scores
    record["documentation"] = dict(PARTICIPANT_YAML_DOCUMENTATION)
    return record


def build_participants_yaml(data_collection, table: pl.DataFrame | None = None) -> dict:
    """Build the nested participant view for ``participants.yaml``.

    The view is derived from the same participant groups as ``participants.csv``.
    It keeps the curated PQ and psychometric subset, while the CSV remains the
    full download table for eye-tracking, documentation and completeness fields.

    Parameters
    ----------
    data_collection : MultipleyeDataCollection
        Collection used to build the participant table when ``table`` is absent.
    table : polars.DataFrame, optional
        Prebuilt participant table, so the caller can write both outputs from one build.
    """
    table = table if table is not None else build_participant_table(data_collection)
    pt_rows_by_pid: dict[str, list[dict]] = {}
    for pt_row in _pt_rows():
        pid = pt_row.get("participant_id")
        if pid is not None:
            pt_rows_by_pid.setdefault(str(pid), []).append(pt_row)

    participants = [
        _participant_yaml_record(row, pt_rows_by_pid)
        for row in table.iter_rows(named=True)
        if row.get("pids")
    ]
    return {"participants": participants}


def _session_id_allowed(session_id: str, apply_include: bool = True) -> bool:
    if not session_id:
        return True
    excluded = set(settings.EXCLUDE_SESSIONS or [])
    if session_id in excluded:
        return False
    if apply_include:
        included = set(settings.INCLUDE_SESSIONS or [])
        return not (included and session_id not in included)
    return True


def write_participants_table(
    data_collection, path: Path | str, table: pl.DataFrame | None = None
) -> Path:
    """Write ``participants.csv`` and return its path."""
    table = table if table is not None else build_participant_table(data_collection)
    path = Path(path)
    table.write_csv(path)
    return path


def write_participants_yaml(
    data_collection, path: Path | str, table: pl.DataFrame | None = None
) -> Path:
    """Write ``participants.yaml`` and return its path."""
    payload = build_participants_yaml(data_collection, table=table)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
    return path


__all__ = [
    "build_participant_table",
    "build_participants_yaml",
    "write_participants_table",
    "write_participants_yaml",
]
