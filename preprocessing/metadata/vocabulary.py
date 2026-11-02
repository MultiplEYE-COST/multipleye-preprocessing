"""Canonical units and value domains for codebook fields.

The registry declares field structure. This module adds the metadata that is
derived from conventions or from the participant questionnaire codebook:

* boolean fields accept ``true`` and ``false``
* physical units follow the ``_ms``, ``_cm`` and similar name suffixes
* categorical participant questionnaire fields use the canonical codes
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING

from preprocessing.utils.pq_normalisation.codebook import CODEBOOK

if TYPE_CHECKING:
    from preprocessing.metadata.schema import CodebookField

__all__ = [
    "BOOLEAN_ALLOWED_VALUES",
    "apply_vocabulary",
    "parse_value_labels",
    "unit_for_name",
]

BOOLEAN_ALLOWED_VALUES = "true,false"
LABEL_SEPARATOR = " | "

_UNIT_SUFFIXES = {
    "cm": "cm",
    "chars": "chars",
    "days": "day",
    "dva": "dva",
    "hz": "Hz",
    "ms": "ms",
    "px": "px",
    "s": "s",
    "samples": "samples",
    "screens": "screens",
    "sec": "s",
    "words": "words",
    "wpm": "wpm",
    "year": "year",
}

_UNIT_OVERRIDES = {
    "session.administrative.year_of_data_collection": "year",
    "participant.pq_age": "year",
    "participant.pq_years_education": "year",
}

# PQ field names that map to a question group in the questionnaire codebook.
_PQ_CODEBOOK_FIELDS = {
    "pq_gender": "gender",
    "pq_level_education": "level_education",
    "pq_socio_economic_status": "socio_economic_status",
    "pq_childhood_languages": "childhood_languages",
    "pq_eyewear": "eyewear",
    "pq_alcohol_yesterday": "alcohol",
    "pq_alcohol_today": "alcohol",
}

_CATEGORIES: dict[str, dict[str, str]] = {
    "dataset.administrative.dataset_type": {
        "MultiplEYE": "MultiplEYE",
        "MeRID": "MeRID",
    },
    "dataset.administrative.script_direction": {
        "ltr": "Left to right",
        "rtl": "Right to left",
    },
    "participant.pq_bi_monolingualism": {
        "monolingual": "Monolingual",
        "bilingual": "Bilingual",
        "multilingual": "Multilingual",
    },
    "session.participant.gender": {
        "female": "Female",
        "male": "Male",
        "other": "Other",
        "prefer_not_to_say": "Prefer not to say",
        "unknown": "Unknown",
    },
    "session.participant.bi_monolingualism": {
        "monolingual": "Monolingual",
        "bilingual": "Bilingual",
        "multilingual": "Multilingual",
        "unknown": "Unknown",
    },
    "trial.answers.answer_source": {
        "asc": "ASC",
        "logfile": "Log file",
        "unknown": "Unknown",
    },
    "trial.answers.condition": {
        "local": "Local",
        "bridging": "Bridging",
        "global": "Global",
        "unknown": "Unknown",
    },
}


def _humanize(code: str) -> str:
    """Return a display label for a canonical code."""
    text = code.replace("_", " ").strip()
    if not text:
        return code
    if text.isupper():
        return text
    return text[:1].upper() + text[1:]


def _questionnaire_categories() -> dict[str, dict[str, str]]:
    """Return canonical codes and labels for the questionnaire fields."""
    categories: dict[str, dict[str, str]] = {}
    for pq_name, question in _PQ_CODEBOOK_FIELDS.items():
        spec = CODEBOOK["fields"][question]
        labels: dict[str, str] = {}
        for code in spec.get("codes", []):
            if isinstance(code, dict):
                labels[code["code"]] = code.get("label") or _humanize(code["code"])
            else:
                labels[code] = _humanize(code)
        categories[f"participant.{pq_name}"] = labels
    return categories


_CATEGORIES = {**_questionnaire_categories(), **_CATEGORIES}


def parse_value_labels(value: str) -> dict[str, str] | None:
    """Return ``{code: label}`` for a ``code=label | code=label`` string."""
    labels: dict[str, str] = {}
    for part in value.split("|"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            return None
        code, label = (item.strip() for item in part.split("=", 1))
        if not code or not label or code in labels:
            return None
        labels[code] = label
    return labels


def unit_for_name(variable_name: str) -> str:
    """Return the unit implied by a field-name suffix, or an empty string."""
    suffix = variable_name.rsplit("_", 1)[-1]
    return _UNIT_SUFFIXES.get(suffix, "")


def _unit_for(field: CodebookField) -> str:
    """Return the unit for a numeric field."""
    if field.variable_id in _UNIT_OVERRIDES:
        return _UNIT_OVERRIDES[field.variable_id]
    return unit_for_name(field.variable_name)


def _labels_for(allowed_values: str, categories: Mapping[str, str]) -> str:
    """Return ``code=label`` pairs for a comma-separated value list."""
    pairs = []
    for code in allowed_values.split(","):
        code = code.strip()
        if not code:
            continue
        pairs.append(f"{code}={categories.get(code) or _humanize(code)}")
    return LABEL_SEPARATOR.join(pairs)


def apply_vocabulary(field: CodebookField) -> CodebookField:
    """Return a field with its derived value domain, labels and unit filled."""
    categories = _CATEGORIES.get(field.variable_id, {})
    allowed_values = field.allowed_values

    if not allowed_values:
        if field.data_type == "boolean":
            allowed_values = BOOLEAN_ALLOWED_VALUES
        elif categories:
            allowed_values = ",".join(categories)

    value_labels = field.value_labels
    if not value_labels and allowed_values:
        value_labels = _labels_for(allowed_values, categories)

    unit = field.unit
    if not unit and field.data_type in ("number", "integer"):
        unit = _unit_for(field)

    updates: dict[str, str] = {}
    if allowed_values != field.allowed_values:
        updates["allowed_values"] = allowed_values
    if value_labels != field.value_labels:
        updates["value_labels"] = value_labels
    if unit != field.unit:
        updates["unit"] = unit
    return replace(field, **updates) if updates else field
