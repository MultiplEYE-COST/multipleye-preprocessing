"""Load the five review views from a processed data collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .codebook import Codebook, CodebookField, MISSING, resolve_yaml_path


@dataclass
class ViewRow:
    view: str
    key: str
    parents: dict[str, str] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    raw: Any = None
    source: Path | None = None
    source_key: str = ""

    def value(self, variable_id: str) -> Any:
        return self.values.get(variable_id)


@lru_cache(maxsize=2048)
def _read_yaml_cached(path: str, mtime_ns: int, size: int) -> Any:
    del mtime_ns, size
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    stat = path.stat()
    try:
        return _read_yaml_cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, yaml.YAMLError):
        return None


def processed_dcn_paths(preprocessed_dir: Path) -> list[Path]:
    if not preprocessed_dir.exists():
        return []
    result = []
    for entry in sorted(preprocessed_dir.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / f"{entry.name}_overview.yaml").exists() or (entry / "metadata").exists():
            result.append(entry)
    return result


def raw_dcn_paths(raw_dir: Path) -> list[Path]:
    if not raw_dir.exists():
        return []
    return [entry for entry in sorted(raw_dir.iterdir()) if entry.is_dir()]


def dataset_overview_path(dcn_path: Path) -> Path:
    return dcn_path / f"{dcn_path.name}_overview.yaml"


def session_overview_paths(dcn_path: Path) -> list[Path]:
    metadata = dcn_path / "metadata"
    if not metadata.exists():
        return []
    paths = []
    for entry in sorted(metadata.iterdir()):
        if not entry.is_dir():
            continue
        path = entry / f"{entry.name}_overview.yaml"
        if path.exists():
            paths.append(path)
    return paths


def load_dataset_overview(dcn_path: Path) -> dict[str, Any]:
    data = read_yaml(dataset_overview_path(dcn_path))
    return data if isinstance(data, dict) else {}


def load_session_overviews(dcn_path: Path) -> list[tuple[str, dict[str, Any]]]:
    sessions = []
    for path in session_overview_paths(dcn_path):
        data = read_yaml(path)
        if isinstance(data, dict):
            sessions.append((path.parent.name, data))
    return sessions


def load_participants(dcn_path: Path) -> list[dict[str, Any]]:
    data = read_yaml(dcn_path / "metadata" / "participants.yaml")
    if not isinstance(data, dict):
        return []
    rows = data.get("participants")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def load_items(dcn_path: Path) -> list[dict[str, Any]]:
    data = read_yaml(dcn_path / "metadata" / "items.yaml")
    if not isinstance(data, dict):
        return []
    rows = data.get("items")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _key_field(codebook: Codebook, view_id: str) -> CodebookField | None:
    view = codebook.views.get(view_id)
    if view is None:
        return None
    return next(
        (
            field_obj
            for field_obj in codebook.fields_for_view(view_id)
            if field_obj.variable_name == view.key
        ),
        None,
    )


def _key_value(
    codebook: Codebook,
    view_id: str,
    document: dict[str, Any],
    fallback: str,
) -> str:
    field_obj = _key_field(codebook, view_id)
    if field_obj is None:
        return fallback
    value = resolve_yaml_path(document, field_obj.relative_path())
    if value is None or value is MISSING or value == "":
        return fallback
    return str(value)


def _values_for(
    codebook: Codebook,
    view_id: str,
    document: dict[str, Any],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field_obj in codebook.fields_for_view(view_id):
        values[field_obj.variable_id] = resolve_yaml_path(
            document, field_obj.relative_path()
        )
    return values


def _dataset_key(dcn_path: Path, codebook: Codebook) -> str:
    overview = load_dataset_overview(dcn_path)
    if not overview:
        return dcn_path.name
    return _key_value(codebook, "dataset", overview, dcn_path.name)


def _participant_keys(
    dcn_path: Path,
    codebook: Codebook,
) -> tuple[dict[str, str], dict[str, str]]:
    by_session: dict[str, str] = {}
    by_pid: dict[str, str] = {}
    for index, participant in enumerate(load_participants(dcn_path), start=1):
        key = _key_value(codebook, "participant", participant, f"participant_{index}")
        pid = str(participant.get("participant_id", "")).strip()
        if pid:
            by_pid[pid] = key
            by_pid[pid.lstrip("0") or "0"] = key
        session_ids = participant.get("session_ids")
        if isinstance(session_ids, list):
            for session_id in session_ids:
                by_session[str(session_id)] = key
    return by_session, by_pid


def _participant_key(
    pid: Any,
    session_key: str,
    by_session: dict[str, str],
    by_pid: dict[str, str],
) -> str:
    if session_key in by_session:
        return by_session[session_key]
    text = str(pid or "").strip()
    if text in by_pid:
        return by_pid[text]
    stripped = text.lstrip("0") or "0"
    if stripped in by_pid:
        return by_pid[stripped]
    return text


def _fingerprint(dcn_path: Path) -> tuple[tuple[str, int, int], ...]:
    candidates = [dataset_overview_path(dcn_path)]
    candidates.extend(session_overview_paths(dcn_path))
    candidates.extend(
        [
            dcn_path / "metadata" / "participants.yaml",
            dcn_path / "metadata" / "items.yaml",
            dcn_path / "codebook" / "availability.csv",
            dcn_path / "codebook" / "generated" / "codebook_bundle.json",
        ]
    )
    entries: list[tuple[str, int, int]] = []
    for path in candidates:
        if path.exists():
            stat = path.stat()
            entries.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(entries)


_VIEW_CACHE: dict[tuple[str, str, str], tuple[tuple, list[ViewRow]]] = {}


def load_view_rows(
    dcn_path: Path,
    view_id: str,
    codebook: Codebook,
) -> list[ViewRow]:
    fingerprint = _fingerprint(dcn_path)
    cache_key = (str(dcn_path), view_id, codebook.hash)
    cached = _VIEW_CACHE.get(cache_key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]
    rows = _load_view_rows(dcn_path, view_id, codebook)
    _VIEW_CACHE[cache_key] = (fingerprint, rows)
    return rows


def _load_view_rows(
    dcn_path: Path,
    view_id: str,
    codebook: Codebook,
) -> list[ViewRow]:
    dcn_name = _dataset_key(dcn_path, codebook)

    if view_id == "dataset":
        overview = load_dataset_overview(dcn_path)
        if not overview:
            return []
        return [
            ViewRow(
                view="dataset",
                key=dcn_name,
                parents={},
                values=_values_for(codebook, "dataset", overview),
                raw=overview,
                source=dataset_overview_path(dcn_path),
            )
        ]

    if view_id == "session":
        by_session, by_pid = _participant_keys(dcn_path, codebook)
        rows = []
        for sid, overview in load_session_overviews(dcn_path):
            key = _key_value(codebook, "session", overview, sid)
            admin = overview.get("administrative", {})
            participant = _participant_key(
                admin.get("participant_id") if isinstance(admin, dict) else None,
                key,
                by_session,
                by_pid,
            )
            rows.append(
                ViewRow(
                    view="session",
                    key=key,
                    parents={"dataset": dcn_name, "participant": participant},
                    values=_values_for(codebook, "session", overview),
                    raw=overview,
                    source=dcn_path / "metadata" / sid / f"{sid}_overview.yaml",
                    source_key=sid,
                )
            )
        return rows

    if view_id == "trial":
        by_session, by_pid = _participant_keys(dcn_path, codebook)
        rows = []
        for sid, overview in load_session_overviews(dcn_path):
            trials = overview.get("trials")
            if not isinstance(trials, list):
                continue
            session_key = _key_value(codebook, "session", overview, sid)
            admin = overview.get("administrative", {})
            participant = _participant_key(
                admin.get("participant_id") if isinstance(admin, dict) else None,
                session_key,
                by_session,
                by_pid,
            )
            for index, trial in enumerate(trials, start=1):
                if not isinstance(trial, dict):
                    continue
                key = _key_value(
                    codebook,
                    "trial",
                    trial,
                    f"{session_key}:trial_{index}",
                )
                rows.append(
                    ViewRow(
                        view="trial",
                        key=key,
                        parents={
                            "dataset": dcn_name,
                            "session": session_key,
                            "participant": participant,
                        },
                        values=_values_for(codebook, "trial", trial),
                        raw=trial,
                        source=dcn_path
                        / "metadata"
                        / sid
                        / f"{sid}_overview.yaml",
                        source_key=session_key,
                    )
                )
        return rows

    if view_id == "participant":
        rows = []
        for index, participant in enumerate(load_participants(dcn_path), start=1):
            key = _key_value(
                codebook,
                "participant",
                participant,
                f"participant_{index}",
            )
            rows.append(
                ViewRow(
                    view="participant",
                    key=key,
                    parents={"dataset": dcn_name},
                    values=_values_for(codebook, "participant", participant),
                    raw=participant,
                    source=dcn_path / "metadata" / "participants.yaml",
                )
            )
        return rows

    if view_id == "item":
        rows = []
        for index, item in enumerate(load_items(dcn_path), start=1):
            key = _key_value(codebook, "item", item, f"item_{index}")
            rows.append(
                ViewRow(
                    view="item",
                    key=key,
                    parents={"dataset": dcn_name},
                    values=_values_for(codebook, "item", item),
                    raw=item,
                    source=dcn_path / "metadata" / "items.yaml",
                )
            )
        return rows

    return []


def find_row(
    dcn_path: Path,
    view_id: str,
    key: str,
    codebook: Codebook,
    session_key: str | None = None,
) -> ViewRow | None:
    for row in load_view_rows(dcn_path, view_id, codebook):
        if view_id == "trial" and session_key is not None:
            if row.parents.get("session") != session_key and row.source_key != session_key:
                continue
        if row.key == key:
            return row
    return None


def resolve_session_folder(dcn_path: Path, key: str, codebook: Codebook) -> str:
    for row in load_view_rows(dcn_path, "session", codebook):
        if row.key == key:
            return row.source_key or row.key
    return key


def resolve_participant_key(
    dcn_path: Path,
    pid: str,
    session_key: str | None,
    codebook: Codebook,
) -> str:
    by_session, by_pid = _participant_keys(dcn_path, codebook)
    return _participant_key(pid, session_key or "", by_session, by_pid)


def related_rows(
    dcn_path: Path,
    source_row: ViewRow,
    target_view: str,
    codebook: Codebook,
) -> list[ViewRow]:
    rows = load_view_rows(dcn_path, target_view, codebook)
    if source_row.view == target_view:
        return [source_row]
    if target_view in source_row.parents:
        return [row for row in rows if row.key == source_row.parents[target_view]]
    if source_row.view == "dataset":
        return [row for row in rows if row.parents.get("dataset") == source_row.key]
    if source_row.view == "session":
        if target_view == "trial":
            return [row for row in rows if row.parents.get("session") == source_row.key]
        if target_view == "participant":
            return [row for row in rows if row.key == source_row.parents.get("participant")]
        if target_view == "item":
            text_ids = {
                row.value("trial.text_id")
                for row in load_view_rows(dcn_path, "trial", codebook)
                if row.parents.get("session") == source_row.key
            }
            return [row for row in rows if row.key in text_ids]
    if source_row.view == "participant":
        session_ids = source_row.value("participant.session_ids") or []
        if target_view == "session":
            return [
                row
                for row in rows
                if row.key in session_ids
                or row.parents.get("participant") == source_row.key
            ]
        if target_view == "trial":
            return [row for row in rows if row.parents.get("participant") == source_row.key]
        if target_view == "item":
            text_ids = {
                row.value("trial.text_id")
                for row in load_view_rows(dcn_path, "trial", codebook)
                if row.parents.get("participant") == source_row.key
            }
            return [row for row in rows if row.key in text_ids]
    if source_row.view == "trial":
        if target_view == "item":
            return [row for row in rows if row.key == source_row.value("trial.text_id")]
    if source_row.view == "item":
        if target_view == "trial":
            return [
                row for row in rows if row.value("trial.text_id") == source_row.key
            ]
        if target_view == "participant":
            participant_keys = {
                row.parents.get("participant")
                for row in load_view_rows(dcn_path, "trial", codebook)
                if row.value("trial.text_id") == source_row.key
            }
            return [row for row in rows if row.key in participant_keys]
        if target_view == "session":
            session_keys = {
                row.parents.get("session")
                for row in load_view_rows(dcn_path, "trial", codebook)
                if row.value("trial.text_id") == source_row.key
            }
            return [row for row in rows if row.key in session_keys]
    return []


def all_view_rows(
    dcn_path: Path,
    codebook: Codebook,
) -> dict[str, list[ViewRow]]:
    return {
        view_id: load_view_rows(dcn_path, view_id, codebook)
        for view_id in ("dataset", "session", "trial", "participant", "item")
    }
