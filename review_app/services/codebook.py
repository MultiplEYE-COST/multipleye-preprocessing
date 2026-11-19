"""Read codebook packages and resolve YAML paths for the five review views."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_CODEBOOK_DIR = Path(__file__).resolve().parents[2] / "codebook"

VIEW_IDS = ("dataset", "session", "trial", "participant", "item")

AVAILABILITY_TRUE = "true"
AVAILABILITY_FALSE = "false"
AVAILABILITY_NOT_APPLICABLE = "not_applicable"
AVAILABILITY_REASONS = (
    "missing_source",
    "optional_test_not_collected",
    "annotation_pending",
    "external",
)

_VIEW_ARRAY_PREFIX = {
    "trial": "trials[].",
    "participant": "participants[].",
    "item": "items[].",
}


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()


@dataclass(frozen=True)
class CodebookField:
    variable_id: str
    view_level: str
    variable_name: str
    feature_label: str
    description: str
    data_type: str
    unit: str
    allowed_values: tuple[str, ...]
    value_labels: dict[str, str]
    yaml_path: str
    semantic_category: str
    aggregation_base_level: str = ""
    aggregation_method: str = ""
    aggregation_input: str = ""
    aggregation_weight: str = ""
    aggregation_denominator: str = ""
    aggregation_behavior: str = ""
    aggregation_notes: str = ""
    dynamic_equivalent: str = ""
    notes: str = ""

    def relative_path(self) -> str:
        prefix = _VIEW_ARRAY_PREFIX.get(self.view_level)
        if prefix and self.yaml_path.startswith(prefix):
            return self.yaml_path[len(prefix) :]
        return self.yaml_path


@dataclass(frozen=True)
class CodebookView:
    view_id: str
    key: str
    parent_view: str
    parent_key: str
    description: str


@dataclass(frozen=True)
class CodebookRelation:
    relation_id: str
    from_view: str
    from_key: str
    to_view: str
    to_key: str
    description: str


@dataclass(frozen=True)
class DisplayGroup:
    group_id: str
    label: str
    description: str
    order: int
    default: bool
    members: tuple[str, ...] = ()


@dataclass(frozen=True)
class Availability:
    variable_id: str
    available: str
    reason: str = ""

    @property
    def is_available(self) -> bool:
        return self.available == AVAILABILITY_TRUE


@dataclass
class Codebook:
    version: str = ""
    credit: str = ""
    hash: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    fields: dict[str, CodebookField] = field(default_factory=dict)
    views: dict[str, CodebookView] = field(default_factory=dict)
    relations: list[CodebookRelation] = field(default_factory=list)
    groups: dict[str, DisplayGroup] = field(default_factory=dict)
    categories: dict[str, dict[str, str]] = field(default_factory=dict)
    source: str = ""

    def fields_for_view(self, view_id: str) -> list[CodebookField]:
        return [f for f in self.fields.values() if f.view_level == view_id]

    def group_ids_for_view(self, view_id: str) -> list[str]:
        ids = []
        for group in self.groups.values():
            if any(
                self.fields.get(member) is not None
                and self.fields[member].view_level == view_id
                for member in group.members
            ):
                ids.append(group.group_id)
        return sorted(ids, key=lambda gid: self.groups[gid].order)

    def default_group_for_view(self, view_id: str) -> str:
        candidates = [self.groups[gid] for gid in self.group_ids_for_view(view_id)]
        explicit = [g for g in candidates if g.default]
        if explicit:
            return explicit[0].group_id
        if not candidates:
            return ""
        return max(
            candidates,
            key=lambda g: sum(
                1
                for member in g.members
                if self.fields.get(member) is not None
                and self.fields[member].view_level == view_id
            ),
        ).group_id

    def best_group_for_view(self, view_id: str) -> str:
        candidate_ids = [
            gid for gid in self.group_ids_for_view(view_id) if gid != "default"
        ]
        if not candidate_ids:
            return self.default_group_for_view(view_id)
        return max(
            (self.groups[gid] for gid in candidate_ids),
            key=lambda group: sum(
                1
                for member in group.members
                if self.fields.get(member) is not None
                and self.fields[member].view_level == view_id
            ),
        ).group_id

    def columns_for(self, view_id: str, group_id: str | None = None) -> list[CodebookField]:
        view = self.views.get(view_id)
        key_field = None
        if view is not None:
            key_field = next(
                (
                    f
                    for f in self.fields_for_view(view_id)
                    if f.variable_name == view.key
                ),
                None,
            )
        group = self.groups.get(group_id or self.default_group_for_view(view_id))
        fields: list[CodebookField] = []
        if group is not None:
            for member in group.members:
                field = self.fields.get(member)
                if field is not None and field.view_level == view_id:
                    fields.append(field)
        if key_field is not None and key_field not in fields:
            fields.insert(0, key_field)
        if not fields:
            fields = self.fields_for_view(view_id)
            if key_field is not None:
                fields = [key_field] + [f for f in fields if f is not key_field]
        return fields

    def related_views(self, view_id: str) -> list[CodebookRelation]:
        return [
            r
            for r in self.relations
            if r.from_view == view_id or r.to_view == view_id
        ]

    def resolve(self, document: Any, yaml_path: str) -> Any:
        return resolve_yaml_path(document, yaml_path)

    def field(self, variable_id: str) -> CodebookField | None:
        return self.fields.get(variable_id)


def parse_allowed_values(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def parse_value_labels(value: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for part in value.split("|"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        code, label = part.split("=", 1)
        labels[code.strip()] = label.strip()
    return labels


def _field_from_row(row: dict[str, str]) -> CodebookField:
    return CodebookField(
        variable_id=row.get("variable_id", ""),
        view_level=row.get("view_level", ""),
        variable_name=row.get("variable_name", ""),
        feature_label=row.get("feature_label", "") or row.get("variable_name", ""),
        description=row.get("description", ""),
        data_type=row.get("data_type", ""),
        unit=row.get("unit", ""),
        allowed_values=parse_allowed_values(row.get("allowed_values", "")),
        value_labels=parse_value_labels(row.get("value_labels", "")),
        yaml_path=row.get("yaml_path", ""),
        semantic_category=row.get("semantic_category", ""),
        aggregation_base_level=row.get("aggregation_base_level", ""),
        aggregation_method=row.get("aggregation_method", ""),
        aggregation_input=row.get("aggregation_input", ""),
        aggregation_weight=row.get("aggregation_weight", ""),
        aggregation_denominator=row.get("aggregation_denominator", ""),
        aggregation_behavior=row.get("aggregation_behavior", ""),
        aggregation_notes=row.get("aggregation_notes", ""),
        dynamic_equivalent=row.get("dynamic_equivalent", ""),
        notes=row.get("notes", ""),
    )


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _bundle_to_codebook(data: dict[str, Any], source: str) -> Codebook:
    fields = {
        f.variable_id: f
        for f in (_field_from_row(row) for row in data.get("fields", []))
        if f.variable_id
    }
    views = {
        v["view_id"]: CodebookView(
            view_id=_str(v.get("view_id")),
            key=_str(v.get("key")),
            parent_view=_str(v.get("parent_view")),
            parent_key=_str(v.get("parent_key")),
            description=_str(v.get("description")),
        )
        for v in data.get("views", [])
        if v.get("view_id")
    }
    relations = [
        CodebookRelation(
            relation_id=_str(r.get("relation_id")),
            from_view=_str(r.get("from_view")),
            from_key=_str(r.get("from_key")),
            to_view=_str(r.get("to_view")),
            to_key=_str(r.get("to_key")),
            description=_str(r.get("description")),
        )
        for r in data.get("relations", [])
    ]
    members: dict[str, list[str]] = {}
    for row in data.get("display_group_members", []):
        group_id = _str(row.get("group_id"))
        variable_id = _str(row.get("variable_id"))
        if group_id and variable_id:
            members.setdefault(group_id, []).append(variable_id)
    groups = {}
    for row in data.get("display_groups", []):
        group_id = _str(row.get("group_id"))
        if not group_id:
            continue
        groups[group_id] = DisplayGroup(
            group_id=group_id,
            label=_str(row.get("label")),
            description=_str(row.get("description")),
            order=_int(row.get("order"), 0),
            default=_bool(row.get("default")),
            members=tuple(members.get(group_id, ())),
        )
    categories = {
        _str(row.get("category_id")): {
            "label": _str(row.get("label")),
            "description": _str(row.get("description")),
        }
        for row in data.get("semantic_categories", [])
        if row.get("category_id")
    }
    info = data.get("codebook", {})
    return Codebook(
        version=_str(info.get("codebook_version")),
        credit=_str(info.get("credit")),
        hash=_str(info.get("hash")),
        environment=dict(data.get("environment") or {}),
        fields=fields,
        views=views,
        relations=relations,
        groups=groups,
        categories=categories,
        source=source,
    )


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return _str(value).strip().lower() in {"true", "1", "yes"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return []


def _codebook_from_csv_dir(codebook_dir: Path, source: str) -> Codebook:
    fields = {
        f.variable_id: f
        for f in (
            _field_from_row(row)
            for row in _read_csv(codebook_dir / "fields.csv")
        )
        if f.variable_id
    }
    views = {
        row["view_id"]: CodebookView(
            view_id=row.get("view_id", ""),
            key=row.get("key", ""),
            parent_view=row.get("parent_view", ""),
            parent_key=row.get("parent_key", ""),
            description=row.get("description", ""),
        )
        for row in _read_csv(codebook_dir / "views.csv")
        if row.get("view_id")
    }
    relations = [
        CodebookRelation(
            relation_id=row.get("relation_id", ""),
            from_view=row.get("from_view", ""),
            from_key=row.get("from_key", ""),
            to_view=row.get("to_view", ""),
            to_key=row.get("to_key", ""),
            description=row.get("description", ""),
        )
        for row in _read_csv(codebook_dir / "relations.csv")
    ]
    members: dict[str, list[str]] = {}
    for row in _read_csv(codebook_dir / "display_group_members.csv"):
        group_id = row.get("group_id", "")
        variable_id = row.get("variable_id", "")
        if group_id and variable_id:
            members.setdefault(group_id, []).append(variable_id)
    groups = {}
    for row in _read_csv(codebook_dir / "display_groups.csv"):
        group_id = row.get("group_id", "")
        if not group_id:
            continue
        groups[group_id] = DisplayGroup(
            group_id=group_id,
            label=row.get("label", ""),
            description=row.get("description", ""),
            order=_int(row.get("order"), 0),
            default=_bool(row.get("default")),
            members=tuple(members.get(group_id, ())),
        )
    categories = {
        row.get("category_id", ""): {
            "label": row.get("label", ""),
            "description": row.get("description", ""),
        }
        for row in _read_csv(codebook_dir / "semantic_categories.csv")
        if row.get("category_id")
    }
    info_rows = _read_csv(codebook_dir / "codebook_info.csv")
    info = info_rows[0] if info_rows else {}
    return Codebook(
        version=info.get("codebook_version", ""),
        credit=info.get("credit", ""),
        hash=codebook_hash(codebook_dir),
        fields=fields,
        views=views,
        relations=relations,
        groups=groups,
        categories=categories,
        source=source,
    )


def codebook_hash(codebook_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in (
        "fields.csv",
        "views.csv",
        "relations.csv",
        "display_groups.csv",
        "display_group_members.csv",
        "semantic_categories.csv",
        "codebook_info.csv",
    ):
        path = codebook_dir / name
        if path.exists():
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def load_repo_codebook(codebook_dir: Path | None = None) -> Codebook:
    directory = codebook_dir or REPO_CODEBOOK_DIR
    return _codebook_from_csv_dir(directory, "repo")


def load_dcn_codebook(dcn_path: Path) -> Codebook | None:
    bundle_path = dcn_path / "codebook" / "generated" / "codebook_bundle.json"
    if not bundle_path.exists():
        return None
    try:
        with open(bundle_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return _bundle_to_codebook(data, f"dcn:{dcn_path.name}")


def overlay_codebook(base: Codebook, incoming: Codebook) -> Codebook:
    fields = dict(base.fields)
    fields.update(incoming.fields)
    views = dict(base.views)
    views.update(incoming.views)

    relations: list[CodebookRelation] = []
    by_id: dict[str, CodebookRelation] = {}
    for relation in list(base.relations) + list(incoming.relations):
        by_id[relation.relation_id] = relation
    relations = list(by_id.values())

    groups = dict(base.groups)
    groups.update(incoming.groups)
    categories = dict(base.categories)
    categories.update(incoming.categories)

    return Codebook(
        version=incoming.version or base.version,
        credit=incoming.credit or base.credit,
        hash=incoming.hash or base.hash,
        environment={**base.environment, **incoming.environment},
        fields=fields,
        views=views,
        relations=relations,
        groups=groups,
        categories=categories,
        source=incoming.source,
    )


def load_union_codebook(
    preprocessed_dir: Path,
    repo_dir: Path | None = None,
) -> Codebook:
    base = load_repo_codebook(repo_dir)
    if not preprocessed_dir.exists():
        return base

    for dcn_path in sorted(p for p in preprocessed_dir.iterdir() if p.is_dir()):
        dcn_codebook = load_dcn_codebook(dcn_path)
        if dcn_codebook is None:
            continue
        _merge_codebook(base, dcn_codebook)
    return base


def _merge_codebook(base: Codebook, incoming: Codebook) -> None:
    for variable_id, field_obj in incoming.fields.items():
        base.fields.setdefault(variable_id, field_obj)
    for view_id, view in incoming.views.items():
        base.views.setdefault(view_id, view)
    known_relations = {relation.relation_id for relation in base.relations}
    for relation in incoming.relations:
        if relation.relation_id not in known_relations:
            base.relations.append(relation)
            known_relations.add(relation.relation_id)
    for group_id, group in incoming.groups.items():
        existing = base.groups.get(group_id)
        if existing is None:
            base.groups[group_id] = group
        else:
            members = tuple(dict.fromkeys((*existing.members, *group.members)))
            base.groups[group_id] = DisplayGroup(
                group_id=existing.group_id,
                label=existing.label,
                description=existing.description,
                order=existing.order,
                default=existing.default,
                members=members,
            )
    for category_id, category in incoming.categories.items():
        base.categories.setdefault(category_id, category)


def load_availability(dcn_path: Path) -> dict[str, Availability]:
    path = dcn_path / "codebook" / "availability.csv"
    if not path.exists():
        return {}
    rows = _read_csv(path)
    return {
        row.get("variable_id", ""): Availability(
            variable_id=row.get("variable_id", ""),
            available=row.get("available", AVAILABILITY_TRUE),
            reason=row.get("reason", ""),
        )
        for row in rows
        if row.get("variable_id")
    }


def availability_for(
    dcn_path: Path,
    codebook: Codebook,
) -> dict[str, Availability]:
    if not dcn_path.exists():
        return {
            variable_id: Availability(
                variable_id,
                AVAILABILITY_NOT_APPLICABLE,
                "missing_source",
            )
            for variable_id in codebook.fields
        }
    own = load_dcn_codebook(dcn_path)
    own_ids = set(own.fields) if own is not None else set(codebook.fields)
    overlay = load_availability(dcn_path)
    result: dict[str, Availability] = {}
    for variable_id in codebook.fields:
        if variable_id in overlay:
            result[variable_id] = overlay[variable_id]
        elif variable_id in own_ids:
            result[variable_id] = Availability(variable_id, AVAILABILITY_TRUE)
        else:
            result[variable_id] = Availability(
                variable_id,
                AVAILABILITY_FALSE,
                "missing_source",
            )
    return result


def _parse_path(path: str) -> list[str]:
    if not path:
        return []
    return [part for part in path.split(".") if part]


def _iter_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def resolve_yaml_path(document: Any, path: str) -> Any:
    parts = _parse_path(path)
    result = _resolve_parts(document, parts)
    if result is MISSING:
        return None
    return result


def _resolve_parts(document: Any, parts: list[str]) -> Any:
    if not parts:
        return document
    part = parts[0]
    rest = parts[1:]
    has_array = part.endswith("[]")
    name = part[:-2] if has_array else part

    if name:
        if not isinstance(document, dict) or name not in document:
            return MISSING
        node = document[name]
    else:
        if not isinstance(document, (list, tuple, dict)):
            return MISSING
        node = document

    if has_array:
        values = []
        for item in _iter_values(node):
            resolved = _resolve_parts(item, rest)
            values.append(None if resolved is MISSING else resolved)
        return values

    return _resolve_parts(node, rest)


def relation_key(codebook: Codebook, view_id: str, key_name: str) -> str | None:
    for field_obj in codebook.fields_for_view(view_id):
        if field_obj.variable_name == key_name:
            return field_obj.variable_id
    return None
