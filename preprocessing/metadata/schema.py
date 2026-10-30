"""Codebook field schema and package validation."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path

__all__ = [
    "AGGREGATION_BEHAVIORS",
    "AGGREGATION_METHODS",
    "FIELD_COLUMNS",
    "VIEW_LEVELS",
    "CodebookField",
    "CodebookValidationError",
    "read_fields",
    "validate_codebook_package",
    "validate_fields",
    "write_fields",
]

FIELD_COLUMNS = (
    "variable_id",
    "view_level",
    "variable_name",
    "feature_label",
    "description",
    "data_type",
    "unit",
    "allowed_values",
    "value_labels",
    "source_form",
    "source_section",
    "pipeline_field",
    "yaml_path",
    "semantic_category",
    "aggregation_base_level",
    "aggregation_method",
    "aggregation_input",
    "aggregation_weight",
    "aggregation_denominator",
    "aggregation_behavior",
    "aggregation_notes",
    "dynamic_equivalent",
    "notes",
)

VIEW_LEVELS = ("dataset", "session", "trial", "participant", "item")

AGGREGATION_METHODS = (
    "mean",
    "sum",
    "weighted_mean",
    "ratio",
    "count",
    "mode",
    "minimum",
    "maximum",
)

AGGREGATION_BEHAVIORS = (
    "recompute_from_filtered_rows",
    "precomputed_only",
    "static",
    "not_applicable",
)

_VIEW_COLUMNS = ("view_id", "key", "parent_view", "parent_key", "description")
_RELATION_COLUMNS = (
    "relation_id",
    "from_view",
    "from_key",
    "to_view",
    "to_key",
    "description",
)
_GROUP_COLUMNS = ("group_id", "label", "description", "order", "default")
_MEMBER_COLUMNS = ("group_id", "variable_id")
_CATEGORY_COLUMNS = ("category_id", "label", "description")

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_YAML_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\[\])?$")


class CodebookValidationError(ValueError):
    """Raised when a codebook package violates the schema."""

    def __init__(self, issues: Sequence[str]):
        self.issues = tuple(issues)
        message = "Codebook validation failed:\n" + "\n".join(
            f"* {issue}" for issue in self.issues
        )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CodebookField:
    """One row in ``fields.csv``."""

    variable_id: str
    view_level: str
    variable_name: str
    feature_label: str
    description: str
    data_type: str
    unit: str = ""
    allowed_values: str = ""
    value_labels: str = ""
    source_form: str = ""
    source_section: str = ""
    pipeline_field: str = ""
    yaml_path: str = ""
    semantic_category: str = ""
    aggregation_base_level: str = ""
    aggregation_method: str = ""
    aggregation_input: str = ""
    aggregation_weight: str = ""
    aggregation_denominator: str = ""
    aggregation_behavior: str = ""
    aggregation_notes: str = ""
    dynamic_equivalent: str = ""
    notes: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> CodebookField:
        """Create a field from a CSV row."""
        values = {item.name: row.get(item.name, "") or "" for item in fields(cls)}
        return cls(**values)

    def to_row(self) -> dict[str, str]:
        """Return the field as a CSV row."""
        return {
            column: "" if getattr(self, column) is None else str(getattr(self, column))
            for column in FIELD_COLUMNS
        }


def _read_rows(path: Path, required_columns: Sequence[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise CodebookValidationError([f"Missing codebook file: {path}"])
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [
            column
            for column in required_columns
            if column not in (reader.fieldnames or [])
        ]
        if missing:
            raise CodebookValidationError(
                [f"{path.name} is missing columns: {', '.join(missing)}"]
            )
        return list(reader)


def read_fields(path: Path | str) -> list[CodebookField]:
    """Read a field table from CSV."""
    rows = _read_rows(Path(path), FIELD_COLUMNS)
    return [CodebookField.from_row(row) for row in rows]


def write_fields(path: Path | str, fields_to_write: Iterable[CodebookField]) -> None:
    """Write a field table to CSV."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(FIELD_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(field.to_row() for field in fields_to_write)


def _split_references(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _validate_yaml_path(path: str) -> str | None:
    if not path:
        return None
    if path.startswith(".") or path.endswith("."):
        return f"yaml_path must not start or end with a dot: {path!r}"
    for segment in path.split("."):
        if not _YAML_SEGMENT.fullmatch(segment):
            return f"Invalid yaml_path segment {segment!r} in {path!r}"
    return None


def validate_fields(
    fields_to_validate: Sequence[CodebookField],
    semantic_categories: Iterable[str],
) -> list[str]:
    """Return validation issues for the field table."""
    issues: list[str] = []
    categories = set(semantic_categories)
    field_ids = [field.variable_id for field in fields_to_validate]
    known_ids = set(field_ids)

    for variable_id in sorted(
        {value for value in field_ids if field_ids.count(value) > 1}
    ):
        issues.append(f"Duplicate variable_id: {variable_id}")

    for field in fields_to_validate:
        label = field.variable_id or "<empty variable_id>"
        if not field.variable_id:
            issues.append("Field has an empty variable_id")
            continue
        if field.view_level not in VIEW_LEVELS:
            issues.append(f"{label}: unknown view_level {field.view_level!r}")
        if not field.variable_id.startswith(f"{field.view_level}."):
            issues.append(
                f"{label}: variable_id must start with {field.view_level!r} and a dot"
            )
        if not _IDENTIFIER.fullmatch(field.variable_name):
            issues.append(f"{label}: invalid variable_name {field.variable_name!r}")
        for column in ("feature_label", "description", "data_type"):
            if not getattr(field, column):
                issues.append(f"{label}: {column} is required")
        if not field.semantic_category:
            issues.append(f"{label}: semantic_category is required")
        elif field.semantic_category not in categories:
            issues.append(
                f"{label}: unknown semantic_category {field.semantic_category!r}"
            )
        path_issue = _validate_yaml_path(field.yaml_path)
        if path_issue:
            issues.append(f"{label}: {path_issue}")
        if (
            field.aggregation_base_level
            and field.aggregation_base_level not in VIEW_LEVELS
        ):
            issues.append(
                f"{label}: unknown aggregation_base_level "
                f"{field.aggregation_base_level!r}"
            )
        if (
            field.aggregation_method
            and field.aggregation_method not in AGGREGATION_METHODS
        ):
            issues.append(
                f"{label}: unknown aggregation_method {field.aggregation_method!r}"
            )
        if (
            field.aggregation_behavior
            and field.aggregation_behavior not in AGGREGATION_BEHAVIORS
        ):
            issues.append(
                f"{label}: unknown aggregation_behavior {field.aggregation_behavior!r}"
            )
        for column in (
            "aggregation_input",
            "aggregation_weight",
            "aggregation_denominator",
        ):
            value = getattr(field, column)
            if not value:
                continue
            for reference in _split_references(value):
                if reference not in known_ids:
                    issues.append(
                        f"{label}: {column} references unknown field {reference!r}"
                    )
        if field.dynamic_equivalent and field.dynamic_equivalent not in known_ids:
            issues.append(
                f"{label}: dynamic_equivalent references unknown field "
                f"{field.dynamic_equivalent!r}"
            )

    return issues


def _validate_views(
    views: Sequence[Mapping[str, str]], fields_to_validate: Sequence[CodebookField]
) -> list[str]:
    issues: list[str] = []
    view_ids = [view.get("view_id", "") for view in views]
    for view_id in sorted({value for value in view_ids if view_ids.count(value) > 1}):
        issues.append(f"Duplicate view_id: {view_id}")

    fields_by_view: dict[str, set[str]] = {}
    for field in fields_to_validate:
        fields_by_view.setdefault(field.view_level, set()).add(field.variable_name)

    known_views = set(view_ids)
    for view_id in VIEW_LEVELS:
        if view_id not in known_views:
            issues.append(f"Missing view: {view_id}")

    for view in views:
        view_id = view.get("view_id", "")
        key = view.get("key", "")
        parent_view = view.get("parent_view", "")
        parent_key = view.get("parent_key", "")
        if view_id not in VIEW_LEVELS:
            issues.append(f"View {view_id!r}: unknown view_id")
        if not key:
            issues.append(f"View {view_id!r}: key is required")
        elif key not in fields_by_view.get(view_id, set()):
            issues.append(f"View {view_id!r}: key {key!r} has no field in that view")
        if parent_view:
            if parent_view not in known_views:
                issues.append(f"View {view_id!r}: unknown parent_view {parent_view!r}")
            if not parent_key:
                issues.append(f"View {view_id!r}: parent_key is required")
            elif parent_key not in fields_by_view.get(parent_view, set()):
                issues.append(
                    f"View {view_id!r}: parent_key {parent_key!r} has no field "
                    f"in view {parent_view!r}"
                )
        elif parent_key:
            issues.append(f"View {view_id!r}: parent_key set without parent_view")
    return issues


def _validate_relations(
    relations: Sequence[Mapping[str, str]],
    views: Sequence[Mapping[str, str]],
    fields_to_validate: Sequence[CodebookField],
) -> list[str]:
    issues: list[str] = []
    relation_ids = [relation.get("relation_id", "") for relation in relations]
    for relation_id in sorted(
        {value for value in relation_ids if relation_ids.count(value) > 1}
    ):
        issues.append(f"Duplicate relation_id: {relation_id}")

    view_ids = {view.get("view_id", "") for view in views}
    known_keys = {view.get("key", "") for view in views}
    known_keys.update(view.get("parent_key", "") for view in views)
    known_keys.update(field.variable_name for field in fields_to_validate)
    known_keys.discard("")

    for relation in relations:
        relation_id = relation.get("relation_id", "")
        from_view = relation.get("from_view", "")
        to_view = relation.get("to_view", "")
        if from_view not in view_ids:
            issues.append(f"Relation {relation_id!r}: unknown from_view {from_view!r}")
        if to_view not in view_ids:
            issues.append(f"Relation {relation_id!r}: unknown to_view {to_view!r}")
        for column in ("from_key", "to_key"):
            key = relation.get(column, "")
            if not key:
                issues.append(f"Relation {relation_id!r}: {column} is required")
            elif key not in known_keys:
                issues.append(
                    f"Relation {relation_id!r}: {column} {key!r} is not a known key"
                )
    return issues


def _validate_display_groups(
    groups: Sequence[Mapping[str, str]],
    members: Sequence[Mapping[str, str]],
    fields_to_validate: Sequence[CodebookField],
) -> list[str]:
    issues: list[str] = []
    group_ids = [group.get("group_id", "") for group in groups]
    for group_id in sorted(
        {value for value in group_ids if group_ids.count(value) > 1}
    ):
        issues.append(f"Duplicate group_id: {group_id}")

    for group in groups:
        group_id = group.get("group_id", "")
        if not group.get("label"):
            issues.append(f"Display group {group_id!r}: label is required")
        if not group.get("description"):
            issues.append(f"Display group {group_id!r}: description is required")
        try:
            int(group.get("order", ""))
        except ValueError:
            issues.append(f"Display group {group_id!r}: order must be an integer")
        if group.get("default", "").lower() not in {"true", "false", "1", "0"}:
            issues.append(f"Display group {group_id!r}: default must be boolean")

    field_ids = {field.variable_id for field in fields_to_validate}
    group_id_set = set(group_ids)
    seen_pairs: set[tuple[str, str]] = set()
    for member in members:
        group_id = member.get("group_id", "")
        variable_id = member.get("variable_id", "")
        pair = (group_id, variable_id)
        if pair in seen_pairs:
            issues.append(
                f"Duplicate display group member: {group_id!r}/{variable_id!r}"
            )
        seen_pairs.add(pair)
        if group_id not in group_id_set:
            issues.append(f"Display group member references unknown group {group_id!r}")
        if variable_id not in field_ids:
            issues.append(
                f"Display group member references unknown field {variable_id!r}"
            )
    return issues


def _validate_categories(
    categories: Sequence[Mapping[str, str]],
) -> list[str]:
    issues: list[str] = []
    category_ids = [category.get("category_id", "") for category in categories]
    for category_id in sorted(
        {value for value in category_ids if category_ids.count(value) > 1}
    ):
        issues.append(f"Duplicate category_id: {category_id}")
    for category in categories:
        category_id = category.get("category_id", "")
        if not category.get("label"):
            issues.append(f"Category {category_id!r}: label is required")
        if not category.get("description"):
            issues.append(f"Category {category_id!r}: description is required")
    return issues


def validate_codebook_package(codebook_dir: Path | str) -> None:
    """Validate the CSV package and raise ``CodebookValidationError`` on failure."""
    source = Path(codebook_dir)
    fields = read_fields(source / "fields.csv")
    views = _read_rows(source / "views.csv", _VIEW_COLUMNS)
    relations = _read_rows(source / "relations.csv", _RELATION_COLUMNS)
    groups = _read_rows(source / "display_groups.csv", _GROUP_COLUMNS)
    members = _read_rows(source / "display_group_members.csv", _MEMBER_COLUMNS)
    categories = _read_rows(source / "semantic_categories.csv", _CATEGORY_COLUMNS)

    issues = [
        *_validate_categories(categories),
        *validate_fields(
            fields,
            [category.get("category_id", "") for category in categories],
        ),
        *_validate_views(views, fields),
        *_validate_relations(relations, views, fields),
        *_validate_display_groups(groups, members, fields),
    ]
    if issues:
        raise CodebookValidationError(issues)
