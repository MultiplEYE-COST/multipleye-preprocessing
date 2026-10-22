"""Cross-source and source-of-truth completeness checks for participants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..config import settings
from ..models.sid import Sid
from ..utils.data_path_utils import find_psychometric_config_files

TEST_MAPPING = {
    "plab": "PLAB",
    "ran": "RAN",
    "stroop_flanker": "Stroop_Flanker",
    "wmc": "WMC",
    "wiki_vocab": "WikiVocab",
}

_NOT_ABORTED = {"", "no", "n", "none", "false", "0", "nan", "n/a"}


@dataclass
class SheetExpectation:
    pid: str
    session_type: str
    session_id: str | None
    aborted: bool
    tests: set[str]


def _pid(value: object) -> str | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return f"{number:03d}"


def _flag(row: dict, key: str) -> bool:
    try:
        return int(row.get(key) or 0) == 1
    except (TypeError, ValueError):
        return False


def _is_aborted(value: object) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() not in _NOT_ABORTED


def _session_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _tests(value: object) -> set[str]:
    if value is None:
        return set()
    result: set[str] = set()
    for part in re.split(r"[;,]", str(value)):
        text = part.strip().lower().replace("-", "_")
        if not text:
            continue
        if "wmc" in text:
            result.add("WMC")
        elif "ran" in text:
            result.add("RAN")
        elif "stroop" in text or "flanker" in text:
            result.add("Stroop_Flanker")
        elif "wiki" in text or "lextale" in text:
            result.add("WikiVocab")
        elif "plab" in text:
            result.add("PLAB")
    return result


def read_sheet_expectations(experimenter_doc) -> list[SheetExpectation]:
    """Return the ET and PT rows recorded in the experimenter sheet."""
    if experimenter_doc is None:
        return []

    expectations: list[SheetExpectation] = []
    et_frame = getattr(experimenter_doc, "et_frame", None)
    if et_frame is not None and "participant_id" in et_frame.columns:
        for row in et_frame.iter_rows(named=True):
            pid = _pid(row.get("participant_id"))
            if pid is None:
                continue
            expectations.append(
                SheetExpectation(
                    pid=pid,
                    session_type="ET",
                    session_id=_session_id(row.get("session_id")),
                    aborted=_is_aborted(row.get("abortion")),
                    tests=set(),
                )
            )

    pt_frame = getattr(experimenter_doc, "pt_frame", None)
    if pt_frame is not None and "participant_id" in pt_frame.columns:
        for row in pt_frame.iter_rows(named=True):
            pid = _pid(row.get("participant_id"))
            if pid is None:
                continue
            expectations.append(
                SheetExpectation(
                    pid=pid,
                    session_type="PT",
                    session_id=_session_id(row.get("session_id")),
                    aborted=False,
                    tests=_tests(row.get("test")),
                )
            )

    return expectations


def expected_tests_from_configs() -> dict[str, set[str]]:
    """Return the expected tests per PID from the participant configs."""
    config_folder = getattr(settings, "PSYM_PARTICIPANT_CONFIGS", None)
    if config_folder is None:
        return {}
    configs = find_psychometric_config_files(
        Path(config_folder),
        Path(settings.PSYCHOMETRIC_TESTS_DIR),
        is_restructured=True,
    )
    expected: dict[str, set[str]] = {}
    for path in configs:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        pid = _pid(data.get("participant_id"))
        if pid is None:
            try:
                pid = _pid(Sid(path.stem).pid)
            except (ValueError, TypeError):
                pid = None
        if pid is None:
            continue
        tests = {test for flag, test in TEST_MAPPING.items() if data.get(flag) is True}
        expected.setdefault(pid, set()).update(tests)
    return expected


def actual_tests_from_pt_rows(pt_rows: list[dict]) -> dict[str, set[str]]:
    """Return the tests actually present per PID from the PT result rows."""
    actual: dict[str, set[str]] = {}
    for row in pt_rows:
        pid = row.get("participant_id")
        tests: set[str] = set()
        if _flag(row, "LWMC_Done") or any(
            _flag(row, key)
            for key in (
                "LWMC_MU_Done",
                "LWMC_OS_Done",
                "LWMC_SentS_Done",
                "LWMC_SSTM_Done",
            )
        ):
            tests.add("WMC")
        if _flag(row, "RAN_Done"):
            tests.add("RAN")
        if _flag(row, "Stroop_Done") or _flag(row, "Flanker_Done"):
            tests.add("Stroop_Flanker")
        if _flag(row, "WikiVocab_Done"):
            tests.add("WikiVocab")
        if _flag(row, "PLAB_Done"):
            tests.add("PLAB")
        actual.setdefault(pid, set()).update(tests)
    return actual


def _matches_session(
    expected: str | None, actual_ids: set[str], session_type: str
) -> bool:
    if not expected:
        return bool(actual_ids)
    if expected in actual_ids:
        return True
    if expected.isdigit():
        number = int(expected)
        for sid in actual_ids:
            try:
                parsed = Sid(sid)
            except (ValueError, TypeError):
                continue
            if parsed.session_id == number and parsed.session.startswith(session_type):
                return True
        return False
    try:
        Sid(expected)
    except (ValueError, TypeError):
        return bool(actual_ids)
    return False


def cross_source_status(
    group: Any,
    et_sessions: dict[str, str],
    pt_rows: list[dict],
    pq_pids: set[str],
    expectations: list[SheetExpectation],
    config_expected: dict[str, set[str]],
    actual_tests: dict[str, set[str]],
    num_sessions: int,
    check_sheet: bool = True,
) -> dict:
    """Return completeness columns for one participant group."""
    pids = set(group.pids)
    et_ids = {sid for sid, pid in et_sessions.items() if pid in pids}
    group_pt = [row for row in pt_rows if row["participant_id"] in pids]
    pt_ids = {str(row.get("session_id")) for row in group_pt if row.get("session_id")}
    has_et = bool(et_ids)
    has_pt = bool(group_pt)
    has_pq = any(pid in pq_pids for pid in pids)

    group_ex = [entry for entry in expectations if entry.pid in pids]
    et_ex = [
        entry for entry in group_ex if entry.session_type == "ET" and not entry.aborted
    ]
    pt_ex = [
        entry for entry in group_ex if entry.session_type == "PT" and not entry.aborted
    ]

    expected_sessions: list[str] = []
    missing_sessions: list[str] = []
    for entry in et_ex:
        expected_sessions.append(entry.session_id or "ET")
        if entry.session_id:
            if not _matches_session(entry.session_id, et_ids, "ET"):
                missing_sessions.append(entry.session_id)
        elif not has_et:
            missing_sessions.append("ET")
    for entry in pt_ex:
        expected_sessions.append(entry.session_id or "PT")
        if entry.session_id:
            if not _matches_session(entry.session_id, pt_ids, "PT"):
                missing_sessions.append(entry.session_id)
        elif not has_pt:
            missing_sessions.append("PT")

    missing_sources: list[str] = []
    if (et_ex and not has_et) or (has_et and not et_ex and len(et_ids) < num_sessions):
        missing_sources.append("ET")
    if pt_ex and not has_pt:
        missing_sources.append("PT")
    if (has_et or has_pt) and not has_pq:
        missing_sources.append("PQ")

    missing_sheet: list[str] = []
    if check_sheet:
        if has_et and not et_ex:
            missing_sheet.append("ET")
        if has_pt and not pt_ex:
            missing_sheet.append("PT")
        if has_pq and not group_ex:
            missing_sheet.append("PQ")

    expected_tests: set[str] = set()
    for entry in pt_ex:
        expected_tests |= entry.tests
    for pid in pids:
        expected_tests |= config_expected.get(pid, set())
    actual: set[str] = set()
    for pid in pids:
        actual |= actual_tests.get(pid, set())
    missing_tests = expected_tests - actual

    return {
        "expected_session_ids": "; ".join(sorted(set(expected_sessions))),
        "missing_session_ids": "; ".join(sorted(set(missing_sessions))),
        "missing_sources": "; ".join(missing_sources),
        "missing_sheet": "; ".join(missing_sheet),
        "pt_tests_expected": "; ".join(sorted(expected_tests)),
        "pt_tests_missing": "; ".join(sorted(missing_tests)),
    }


__all__ = [
    "SheetExpectation",
    "actual_tests_from_pt_rows",
    "cross_source_status",
    "expected_tests_from_configs",
    "read_sheet_expectations",
]
