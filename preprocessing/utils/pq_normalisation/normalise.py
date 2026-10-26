"""Normalise participant questionnaire answers to the canonical codebook."""

from __future__ import annotations

import re

import pandas as pd

from .codebook import CODEBOOK, DIRECT_FIELDS, READING_TIME_QUESTIONS
from .mapping import _as_int, normalize_label

_READING_TIME_KEY = re.compile(
    r"^(?:(?P<prefix>.+)_)?(?P<question>" + "|".join(READING_TIME_QUESTIONS) + r")$"
)
_LANGUAGE_KEY = re.compile(
    r"^(native_language(?:_\d+)?|use_language|dominant_language|"
    r"additional_read_language_\d+)$"
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


def normalise_pq(pq: dict, mapping: dict) -> dict:
    """Normalise one participant questionnaire.

    Parameters
    ----------
    pq : dict
        Raw ``*_pq_data.json`` content.
    mapping : dict
        Output of :func:`build_mapping`.

    Returns
    -------
    dict
        ``{"values": {column: value}, "issues": [str, ...]}``. ``values``
        contains ``pq_*`` columns and ``pq_raw_*`` columns for every raw key.
    """
    values: dict = {}
    issues: list[str] = list(mapping.get("issues", []))
    labels = mapping.get("labels", {})
    ordinal = mapping.get("ordinal_positions", {})
    languages = mapping.get("languages", {})
    handled: set[str] = set()

    def raw(key: str, value: object) -> None:
        values[f"pq_raw_{key}"] = value

    def mapped(key: str, value: object, field: str) -> None:
        raw(key, value)
        normalized = labels.get(field, {}).get(normalize_label(value))
        if normalized is not None:
            values[f"pq_{key}"] = normalized
        elif not _is_missing(value):
            issues.append(f"Could not map {key}={value!r}")

    for key, field in DIRECT_FIELDS.items():
        if key in pq:
            handled.add(key)
            mapped(key, pq[key], field)

    if "years_education" in pq:
        handled.add("years_education")
        value = pq["years_education"]
        raw("years_education", value)
        number = _as_int(value)
        if number is not None:
            if 1 <= number <= 20:
                values["pq_years_education"] = number
            else:
                issues.append(f"years_education={value!r} is outside 1-20")
        else:
            code = labels.get("years_education", {}).get(normalize_label(value))
            if code is not None:
                values["pq_years_education_open_ended"] = True
            elif not _is_missing(value):
                issues.append(f"Could not map years_education={value!r}")

    if "age" in pq:
        handled.add("age")
        value = pq["age"]
        raw("age", value)
        number = _as_int(value)
        if number is not None and 18 <= number <= 120:
            values["pq_age"] = number
        elif not _is_missing(value):
            issues.append(f"age={value!r} is not an integer in 18-120")

    if "tiredness" in pq:
        handled.add("tiredness")
        value = pq["tiredness"]
        raw("tiredness", value)
        number = _as_int(value)
        if number is None:
            number = ordinal.get("tiredness", {}).get(normalize_label(value))
        if number is not None and 1 <= number <= 9:
            values["pq_tiredness"] = number
        elif not _is_missing(value):
            issues.append(f"Could not map tiredness={value!r}")

    for key, value in pq.items():
        if key in handled:
            continue
        if _READING_TIME_KEY.match(key):
            handled.add(key)
            raw(key, value)
            code = labels.get("reading_time_bin", {}).get(normalize_label(value))
            if code is not None:
                values[f"pq_{key}"] = code
            elif not _is_missing(value):
                issues.append(f"Could not map {key}={value!r}")
        elif _LANGUAGE_KEY.match(key):
            handled.add(key)
            raw(key, value)
            if _is_missing(value):
                continue
            iso = languages.get(normalize_label(value))
            if iso is not None:
                values[f"pq_{key}"] = iso
            else:
                issues.append(f"Could not map language {key}={value!r}")

    if not languages:
        issues.append(
            "Language code file missing or empty; language fields are kept raw "
            "in the language of the data collection."
        )

    for key, value in pq.items():
        if key not in handled:
            raw(key, value)

    return {"values": values, "issues": issues}


__all__ = ["CODEBOOK", "normalise_pq"]
