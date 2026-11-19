"""Codebook-driven quality checks for session overviews."""

from __future__ import annotations

from typing import Any

from ..models import CheckResult
from .codebook import Codebook, CodebookField
from .thresholds import compare, load_thresholds


def _field_for_threshold(codebook: Codebook, key: str) -> CodebookField | None:
    if key in codebook.fields:
        return codebook.fields[key]
    candidates = [
        field_obj
        for field_obj in codebook.fields.values()
        if field_obj.variable_name == key
    ]
    if not candidates:
        return None
    for field_obj in candidates:
        if field_obj.view_level == "session":
            return field_obj
    return candidates[0]


def _is_checkable(value: Any) -> bool:
    return isinstance(value, (int, float, bool, str))


def _serialize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    return value


def _serialize_threshold(value: Any) -> Any:
    if isinstance(value, list):
        return [float(v) if isinstance(v, (int, float)) else v for v in value]
    if value is None:
        return None
    return str(value)


def compute_session_checks(
    overview: dict[str, Any],
    dcn_name: str,
    codebook: Codebook,
) -> list[CheckResult]:
    thresholds = load_thresholds(dcn_name)
    checks: list[CheckResult] = []
    seen: set[str] = set()

    if thresholds:
        for key, spec in thresholds.items():
            field_obj = _field_for_threshold(codebook, key)
            if field_obj is None or field_obj.view_level != "session":
                continue
            value = codebook.resolve(overview, field_obj.relative_path())
            if value is None or not _is_checkable(value):
                continue
            checks.append(
                CheckResult(
                    check_id=field_obj.variable_id,
                    label=field_obj.feature_label,
                    value=_serialize(value),
                    threshold=_serialize_threshold(spec),
                    status=compare(value, spec),
                )
            )
            seen.add(field_obj.variable_id)

    for field_obj in codebook.columns_for("session", "quality"):
        if field_obj.variable_id in seen:
            continue
        if field_obj.semantic_category == "administrative":
            continue
        value = codebook.resolve(overview, field_obj.relative_path())
        if value is None or not _is_checkable(value):
            continue
        checks.append(
            CheckResult(
                check_id=field_obj.variable_id,
                label=field_obj.feature_label,
                value=_serialize(value),
                threshold=None,
                status="pass",
            )
        )
    return checks


def failed_checks(checks: list[CheckResult]) -> list[CheckResult]:
    return [check for check in checks if check.status != "pass"]
