"""Simple view filters that survive view switching through the URL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .codebook import Codebook
from .view_data import ViewRow, related_rows

_OPERATORS = ("eq", "ne", "contains", "gt", "ge", "lt", "le")
_NUMERIC_TYPES = {"number", "integer"}
_OPERATOR_LABELS = {
    "eq": "equals",
    "ne": "not equals",
    "contains": "contains",
    "gt": "greater than",
    "ge": "at least",
    "lt": "less than",
    "le": "at most",
}


def operators_for_field(field: Any) -> tuple[str, ...]:
    data_type = getattr(field, "data_type", "")
    allowed = getattr(field, "allowed_values", ())
    if allowed:
        return ("eq", "ne")
    if data_type in _NUMERIC_TYPES:
        return ("eq", "ne", "gt", "ge", "lt", "le")
    if data_type == "boolean":
        return ("eq", "ne")
    if data_type.startswith("list"):
        return ("contains", "eq", "ne")
    if data_type == "object":
        return ("eq", "ne")
    return ("eq", "ne", "contains")


def operator_allowed(field: Any, operator: str) -> bool:
    return operator in operators_for_field(field)


def operator_label(operator: str) -> str:
    return _OPERATOR_LABELS.get(operator, operator)


def value_options(field: Any) -> list[dict[str, str]]:
    labels = getattr(field, "value_labels", {}) or {}
    return [
        {
            "value": value,
            "label": labels.get(value, value),
        }
        for value in getattr(field, "allowed_values", ()) or ()
    ]


@dataclass(frozen=True)
class ViewFilter:
    view: str
    variable_id: str
    operator: str
    value: str

    def to_query(self) -> str:
        return f"{self.variable_id}:{self.operator}:{self.value}"


def parse_filters(values: list[str]) -> list[ViewFilter]:
    filters: list[ViewFilter] = []
    for raw in values:
        parts = raw.split(":", 2)
        if len(parts) != 3:
            continue
        variable_id, operator, value = parts
        if not variable_id or operator not in _OPERATORS:
            continue
        filters.append(
            ViewFilter(
                view=variable_id.split(".", 1)[0],
                variable_id=variable_id,
                operator=operator,
                value=value,
            )
        )
    return filters


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_as_text(item) for item in value)
    return str(value)


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _equal(actual: Any, expected: str) -> bool:
    if isinstance(actual, (list, tuple)):
        return any(_as_text(item).lower() == expected.lower() for item in actual)
    left = _as_text(actual)
    if left.lower() == expected.lower():
        return True
    left_number = _as_number(left)
    right_number = _as_number(expected)
    return (
        left_number is not None
        and right_number is not None
        and left_number == right_number
    )


def matches(row: ViewRow, view_filter: ViewFilter) -> bool:
    actual = row.value(view_filter.variable_id)
    expected = view_filter.value
    operator = view_filter.operator
    if operator == "contains":
        return expected.lower() in _as_text(actual).lower()
    if operator in {"gt", "ge", "lt", "le"}:
        values = actual if isinstance(actual, (list, tuple)) else [actual]
        numbers = [_as_number(value) for value in values]
        right = _as_number(expected)
        if right is None or not any(number is not None for number in numbers):
            return False
        if operator == "gt":
            return any(number is not None and number > right for number in numbers)
        if operator == "ge":
            return any(number is not None and number >= right for number in numbers)
        if operator == "lt":
            return any(number is not None and number < right for number in numbers)
        return any(number is not None and number <= right for number in numbers)
    equal = _equal(actual, expected)
    return equal if operator == "eq" else not equal


def _connected(codebook: Codebook, first: str, second: str) -> bool:
    if first == second:
        return True
    neighbours: dict[str, set[str]] = {}
    for relation in codebook.relations:
        neighbours.setdefault(relation.from_view, set()).add(relation.to_view)
        neighbours.setdefault(relation.to_view, set()).add(relation.from_view)
    seen = {first}
    queue = [first]
    while queue:
        current = queue.pop()
        for neighbour in neighbours.get(current, set()):
            if neighbour == second:
                return True
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return False


def apply_filters(
    rows: list[ViewRow],
    filters: list[ViewFilter],
    codebook: Codebook,
    dcn_path: Path,
) -> list[ViewRow]:
    if not filters:
        return rows
    result = rows
    for view_filter in filters:
        field_obj = codebook.field(view_filter.variable_id)
        if field_obj is None:
            continue
        if not operator_allowed(field_obj, view_filter.operator):
            continue
        if not _connected(codebook, result[0].view if result else "", view_filter.view):
            continue
        selected = []
        for row in result:
            row_path = row.dcn_path or dcn_path
            candidates = related_rows(row_path, row, view_filter.view, codebook)
            if any(matches(candidate, view_filter) for candidate in candidates):
                selected.append(row)
        result = selected
    return result


def search_rows(rows: list[ViewRow], query: str, codebook: Codebook) -> list[ViewRow]:
    query = query.strip().lower()
    if not query:
        return rows
    result = []
    for row in rows:
        if query in row.key.lower():
            result.append(row)
            continue
        found = False
        for variable_id, value in row.values.items():
            if codebook.field(variable_id) is None:
                continue
            if query in _as_text(value).lower():
                found = True
                break
        if found:
            result.append(row)
    return result
