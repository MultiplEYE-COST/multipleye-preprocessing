"""Participant information helpers shared by the session overview and participant table."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import polars as pl
from polars.exceptions import ComputeError

SESSION_DATE_PREFIX = "*** DATE:"
_PQ_NULL_VALUES = {"", "nan", "none", "null", "unknown", "na", "n/a"}

#: Curated psychometric score columns surfaced in the session overview participant section.
#: The full results table has ~70 columns; the participant table keeps only status.
PSYCHOMETRIC_KEY_SCORES = [
    "LWMC_Done",
    "LWMC_Total_score_mean",
    "RAN_Done",
    "RAN_experimental_rt_sec",
    "Stroop_Done",
    "StroopRTEffect_sec",
    "Flanker_Done",
    "FlankerRTEffect_sec",
    "WikiVocab_Done",
    "WikiVocab_accuracy",
    "PLAB_Done",
    "PLAB_accuracy",
]


def _parse_iso_date(value: object) -> date | None:
    """Parse a leading ISO date (``YYYY-MM-DD``) from a value, else ``None``."""
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _session_date_from_logfile(logfile: object) -> date | None:
    """Return the session date from the ``*** DATE:`` logfile header, if present."""
    if not isinstance(logfile, pl.DataFrame) or "message" not in logfile.columns:
        return None
    try:
        messages = logfile.filter(
            pl.col("message").cast(pl.Utf8).str.starts_with(SESSION_DATE_PREFIX)
        ).get_column("message")
    except (ComputeError, pl.exceptions.InvalidOperationError, TypeError):
        return None
    if messages.len() == 0:
        return None
    return _parse_iso_date(str(messages[0]).split(SESSION_DATE_PREFIX, 1)[-1].strip())


def _psychometric_dates(pt_dir: Path | None) -> set[date]:
    """Return the set of test dates found in a psychometric-test session folder."""
    dates: set[date] = set()
    if pt_dir is None or not pt_dir.exists():
        return dates
    for path in pt_dir.glob("*/*"):
        match = re.search(r"(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}", path.name)
        if match and (parsed := _parse_iso_date(match.group(1))) is not None:
            dates.add(parsed)
    return dates


def _psychometric_tests_in_folder(pt_dir: Path | None) -> list[str]:
    """Return the test folder names present in a psychometric-test session folder."""
    if pt_dir is None or not pt_dir.exists():
        return []
    return sorted(
        p.name for p in pt_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def _bi_monolingualism_from_pq(pq: dict) -> str:
    """Classify language background from the participant questionnaire.

    Uses the distinct non-null native languages: one -> ``monolingual``, two ->
    ``bilingual``, three or more -> ``multilingual``. Normalised keys
    (``pq_native_language_1..3``) are preferred; raw keys are used as a fallback.
    Returns ``"unknown"`` when no native language is recorded.
    """
    if not isinstance(pq, dict):
        return "unknown"

    normalized = (
        "pq_native_language_1",
        "pq_native_language_2",
        "pq_native_language_3",
    )
    raw = ("native_language_1", "native_language_2", "native_language_3")
    keys = normalized if any(key in pq for key in normalized) else raw

    languages: set[str] = set()
    for key in keys:
        value = pq.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text.lower() in _PQ_NULL_VALUES:
            continue
        languages.add(text.lower())

    if not languages:
        return "unknown"
    if len(languages) == 1:
        return "monolingual"
    if len(languages) == 2:
        return "bilingual"
    return "multilingual"


__all__ = [
    "PSYCHOMETRIC_KEY_SCORES",
    "_bi_monolingualism_from_pq",
    "_parse_iso_date",
    "_psychometric_dates",
    "_psychometric_tests_in_folder",
    "_session_date_from_logfile",
]
