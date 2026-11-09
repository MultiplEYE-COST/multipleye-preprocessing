"""Build the item-level metadata view (``items.yaml`` and ``items.csv``).

One item is one language specific stimulus text. The view key is ``text_id``,
built with the same convention as the trial view:
``<stimulus_name>_<lowercase tested language>``.

The item view carries the stimulus information that is available in the
pipeline output, the comprehension questions and options from the stimulus
workbook, and basic aggregates over the matching trials. Values without a
source stay ``None`` (or ``"unknown"`` for text fields); they are never
inferred. Linguistic annotation layers are not implemented yet, so
``annotation_layers`` is always empty and ``annotation_package`` is
``"unknown"`` in this version.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml

from ..answers.parser import construct_question_id
from ..config import settings
from ..metadata.language_tree import language_node_overview
from .multipleye_data_collection import _metadata_form_value

__all__ = [
    "ITEM_COLUMNS",
    "build_item_records",
    "build_items_yaml",
    "write_item_outputs",
    "write_items_table",
    "write_items_yaml",
]

ITEM_COLUMNS = (
    "data_collection_name",
    "text_id",
    "stimulus_id",
    "stimulus_name",
    "tested_language",
    "language_node_id",
    "language_node_path",
    "language_node_label",
    "language_tree_version",
    "language_tree_hash",
    "language_script",
    "stimulus_role",
    "stimulus_genre",
    "stimulus_structure",
    "num_words",
    "num_chars",
    "num_screens",
    "annotation_layers",
    "annotation_package",
    "familiarity_mean",
    "familiarity_mode",
    "difficulty_mean",
    "difficulty_mode",
    "comprehension_accuracy_mean",
    "num_participants",
    "num_trials",
    "questions",
)

_CONDITION_NAMES = {1: "local", 2: "bridging", 3: "global"}
_STIMULUS_ROLES = {
    "experiment": "experiment",
    "practice": "practice",
    "test_practice": "test",
    "test_experiment": "test",
}
_UNKNOWN = "unknown"


def _language_code(session: object) -> str:
    """Return the lowercase tested-language code used for ``text_id``."""
    value = getattr(session, "tested_language", None)
    if not isinstance(value, str):
        return _UNKNOWN
    language = value.strip().lower()
    return language if language else _UNKNOWN


def _iter_sessions(data_collection: object) -> Iterator[object]:
    """Yield processed sessions first, then skipped sessions, without duplicates."""
    seen: set[str] = set()
    for attr in ("sessions", "skipped_sessions"):
        sessions = getattr(data_collection, attr, None)
        if not isinstance(sessions, dict):
            continue
        for session_identifier in sorted(sessions):
            if session_identifier in seen:
                continue
            seen.add(session_identifier)
            yield sessions[session_identifier]


def _stimulus_type_value(stimulus: object) -> str:
    """Return the source ``stimulus_type`` as a non-empty string."""
    value = getattr(stimulus, "type", None)
    return str(value) if value not in (None, "") else _UNKNOWN


def _stimulus_role(stimulus: object) -> str:
    """Map the source ``stimulus_type`` to the item-level role."""
    stimulus_type = _stimulus_type_value(stimulus)
    return _STIMULUS_ROLES.get(stimulus_type, stimulus_type)


def _page_texts(stimulus: object) -> list[str]:
    """Return the non-missing page texts of a stimulus."""
    pages = getattr(stimulus, "pages", None)
    if not isinstance(pages, list | tuple):
        return []
    texts = []
    for page in pages:
        text = getattr(page, "text", None)
        if text is None:
            continue
        text = str(text)
        if text:
            texts.append(text)
    return texts


def _text_counts(stimulus: object) -> tuple[int, int, int]:
    """Return ``(num_words, num_chars, num_screens)`` for a stimulus."""
    texts = _page_texts(stimulus)
    num_words = sum(len(text.split()) for text in texts)
    num_chars = sum(len(text) for text in texts)
    return num_words, num_chars, len(texts)


def _number(value: object) -> float | None:
    """Return a finite-looking number from a scalar, or ``None``."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _clean_mode(value: float) -> float | int:
    """Return a rounded mode, using an integer for integral values."""
    rounded = round(value, 3)
    return int(rounded) if float(rounded).is_integer() else rounded


def _mean(values: list[float]) -> float | None:
    """Return the rounded mean of ``values``, or ``None`` when empty."""
    return round(sum(values) / len(values), 3) if values else None


def _mode(values: list[float]) -> float | int | None:
    """Return the rounded mode of ``values``, or ``None`` when empty."""
    if not values:
        return None
    value = Counter(values).most_common(1)[0][0]
    return _clean_mode(value)


def _condition_number(question: object) -> int | None:
    """Return the question condition number from the source or question id."""
    raw = getattr(question, "condition_no", None)
    try:
        if raw is not None:
            return int(raw)
    except (TypeError, ValueError):
        pass
    question_id = getattr(question, "id", None)
    if question_id is None:
        return None
    match = re.search(r"(\d{2})$", str(question_id))
    if match is None:
        return None
    return int(match.group(1)) // 10


def _question_identifier(stimulus: object, question: object) -> str | None:
    """Return the canonical question id used by the trial answer view."""
    raw_id = getattr(question, "id", None)
    if raw_id is None:
        return None
    match = re.search(r"(\d{2})$", str(raw_id))
    if match is None:
        return str(raw_id)
    snippet_no = getattr(question, "snippet_no", 1)
    try:
        return construct_question_id(
            str(getattr(stimulus, "name", "")),
            int(match.group(1)),
            stimulus_id=getattr(stimulus, "id", None),
            snippet_no=int(snippet_no),
        )
    except (TypeError, ValueError):
        return str(raw_id)


def _question_options(question: object) -> dict[str, str]:
    """Return the available option texts keyed by item option name."""
    options: dict[str, str] = {}
    for key in ("target", "distractor_a", "distractor_b", "distractor_c"):
        value = getattr(question, key, None)
        if value not in (None, ""):
            options[key] = str(value)
    return options


def _question_record(stimulus: object, question: object) -> dict[str, Any] | None:
    """Convert one source comprehension question into an item question record."""
    question_text = getattr(question, "question", None)
    question_id = _question_identifier(stimulus, question)
    if question_text is None and question_id is None:
        return None

    condition_number = _condition_number(question)
    condition = _CONDITION_NAMES.get(condition_number, _UNKNOWN)
    record: dict[str, Any] = {
        "question_id": question_id,
        "condition": condition,
        "condition_number": condition_number,
        "question_text": None if question_text is None else str(question_text),
    }

    item_id = getattr(question, "name", None)
    if item_id not in (None, ""):
        record["item_id"] = str(item_id)
    question_type = getattr(question, "question_type", None)
    if question_type not in (None, ""):
        record["question_type"] = str(question_type)

    options = _question_options(question)
    if options:
        record["options"] = options
    return record


def _item_questions(stimulus: object) -> list[dict[str, Any]]:
    """Return the item questions for a stimulus, dropping unusable entries."""
    questions = getattr(stimulus, "questions", None)
    if not isinstance(questions, list | tuple):
        return []
    records = []
    for question in questions:
        record = _question_record(stimulus, question)
        if record is not None:
            records.append(record)
    return records


def _item_from_stimulus(
    stimulus: object,
    *,
    data_collection_name: str,
    tested_language: str,
    language_code: str,
) -> dict[str, Any]:
    """Build one item record from a loaded stimulus."""
    stimulus_name = getattr(stimulus, "name", None)
    if stimulus_name in (None, ""):
        stimulus_name = _UNKNOWN
    text_id = f"{stimulus_name}_{language_code}"
    num_words, num_chars, num_screens = _text_counts(stimulus)
    return {
        "data_collection_name": data_collection_name,
        "text_id": text_id,
        "stimulus_id": getattr(stimulus, "id", None),
        "stimulus_name": stimulus_name,
        "tested_language": tested_language,
        "language_script": _UNKNOWN,
        "stimulus_role": _stimulus_role(stimulus),
        "stimulus_genre": _UNKNOWN,
        "stimulus_structure": _UNKNOWN,
        "num_words": num_words,
        "num_chars": num_chars,
        "num_screens": num_screens,
        "annotation_layers": [],
        "annotation_package": _UNKNOWN,
        "familiarity_mean": None,
        "familiarity_mode": None,
        "difficulty_mean": None,
        "difficulty_mode": None,
        "comprehension_accuracy_mean": None,
        "num_participants": None,
        "num_trials": None,
        "questions": _item_questions(stimulus),
    }


def _merge_item(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Fill missing target fields from a duplicate item record."""
    for key, value in source.items():
        current = target.get(key)
        if key == "questions":
            if not current and value:
                target[key] = value
            continue
        if current in (None, "", _UNKNOWN) and value not in (None, "", _UNKNOWN):
            target[key] = value


def _item_records(data_collection: object) -> dict[str, dict[str, Any]]:
    """Collect one merged item record per ``text_id`` from all sessions."""
    data_collection_name = (
        getattr(data_collection, "data_collection_name", None)
        or getattr(settings, "DATA_COLLECTION_NAME", None)
        or _UNKNOWN
    )
    items: dict[str, dict[str, Any]] = {}
    for session in _iter_sessions(data_collection):
        stimuli = getattr(session, "stimuli", None)
        if not isinstance(stimuli, list | tuple):
            continue
        tested_language = getattr(session, "tested_language", _UNKNOWN)
        language_code = _language_code(session)
        for stimulus in stimuli:
            record = _item_from_stimulus(
                stimulus,
                data_collection_name=str(data_collection_name),
                tested_language=(
                    tested_language if isinstance(tested_language, str) else _UNKNOWN
                ),
                language_code=language_code,
            )
            text_id = record["text_id"]
            if text_id in items:
                _merge_item(items[text_id], record)
            else:
                items[text_id] = record
    return items


def _trial_source_exists(data_collection: object) -> bool:
    """Return whether any session provides a trial list."""
    return any(
        isinstance(getattr(session, "trials", None), list)
        for session in _iter_sessions(data_collection)
    )


def _trial_index(data_collection: object) -> dict[str, list[tuple[object, object]]]:
    """Index trials by ``text_id`` with their session."""
    index: dict[str, list[tuple[object, object]]] = {}
    for session in _iter_sessions(data_collection):
        trials = getattr(session, "trials", None)
        if not isinstance(trials, list):
            continue
        language = _language_code(session)
        for trial in trials:
            text_id = getattr(trial, "text_id", None)
            if not text_id:
                stimulus_name = getattr(trial, "stimulus_name", None)
                if stimulus_name is None:
                    continue
                text_id = f"{stimulus_name}_{language}"
            index.setdefault(str(text_id), []).append((session, trial))
    return index


def _apply_trial_aggregates(
    records: dict[str, dict[str, Any]],
    trial_index: dict[str, list[tuple[object, object]]],
    *,
    has_trial_source: bool,
) -> None:
    """Fill the item aggregates from the matching trials."""
    if not has_trial_source:
        return

    for text_id, record in records.items():
        matches = trial_index.get(text_id, [])
        record["num_trials"] = len(matches)
        record["num_participants"] = len(
            {
                getattr(session, "participant_id", None)
                for session, _ in matches
                if getattr(session, "participant_id", None) is not None
            }
        )

        familiarity = []
        difficulty = []
        comprehension = []
        for _, trial in matches:
            for key in ("familiarity_1", "familiarity_2"):
                value = _number(getattr(trial, key, None))
                if value is not None:
                    familiarity.append(value)
            value = _number(getattr(trial, "subjective_difficulty", None))
            if value is not None:
                difficulty.append(value)
            value = _number(getattr(trial, "comprehension_score", None))
            if value is not None:
                comprehension.append(value)

        record["familiarity_mean"] = _mean(familiarity)
        record["familiarity_mode"] = _mode(familiarity)
        record["difficulty_mean"] = _mean(difficulty)
        record["difficulty_mode"] = _mode(difficulty)
        record["comprehension_accuracy_mean"] = _mean(comprehension)


def _metadata_form(data_collection: object) -> dict:
    """Return the data-collection metadata form when a loader is available."""
    loader = getattr(data_collection, "_load_metadata_form", None)
    if not callable(loader):
        return {}
    try:
        form = loader()
    except (KeyError, OSError, TypeError, ValueError):
        return {}
    return form if isinstance(form, dict) else {}


def _language_script(data_collection: object) -> object:
    """Return the tested-language script from the metadata form."""
    form = _metadata_form(data_collection)
    if not form:
        return _UNKNOWN
    value = _metadata_form_value(form, "Tested_language", "Language_script", "Script")
    return _UNKNOWN if value in (None, "") else value


def _language_node() -> dict[str, str | None] | None:
    """Return the configured language node block, or ``None``."""
    return language_node_overview(
        getattr(settings, "LANGUAGE_NODE_ID", None),
        getattr(settings, "LANGUAGE_TREE_PATH", None),
        getattr(settings, "LANGUAGE_TREE_VERSION", None),
        getattr(settings, "LANGUAGE_NODE_LABEL", None),
        getattr(settings, "LANGUAGE_TREE_HASH", None),
    )


def build_item_records(data_collection: object) -> list[dict[str, Any]]:
    """Build the item records for the data collection.

    Parameters
    ----------
    data_collection : object
        Data collection exposing ``sessions`` and, optionally, ``skipped_sessions``.
        Sessions may provide loaded ``stimuli`` and ``trials``.

    Returns
    -------
    list[dict]
        One record per ``text_id``, sorted by ``text_id``. Missing aggregates
        are ``None`` and missing annotation data is empty or ``"unknown"``.
    """
    records_by_id = _item_records(data_collection)
    trial_index = _trial_index(data_collection)
    _apply_trial_aggregates(
        records_by_id,
        trial_index,
        has_trial_source=_trial_source_exists(data_collection),
    )

    script = _language_script(data_collection)
    node = _language_node()
    for record in records_by_id.values():
        record["language_script"] = script
        if node is not None:
            record.update(node)

    return [records_by_id[text_id] for text_id in sorted(records_by_id)]


def build_items_yaml(
    data_collection: object,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build the nested item view for ``items.yaml``."""
    return {
        "items": records if records is not None else build_item_records(data_collection)
    }


def _csv_value(value: object) -> str:
    """Convert an item value into a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=False)
    return str(value)


def write_items_table(
    data_collection: object,
    path: Path | str,
    records: Iterable[dict[str, Any]] | None = None,
) -> Path:
    """Write ``items.csv`` and return its path."""
    rows = list(records) if records is not None else build_item_records(data_collection)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(ITEM_COLUMNS),
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(
            {column: _csv_value(row.get(column)) for column in ITEM_COLUMNS}
            for row in rows
        )
    return destination


def write_items_yaml(
    data_collection: object,
    path: Path | str,
    records: Iterable[dict[str, Any]] | None = None,
) -> Path:
    """Write ``items.yaml`` and return its path."""
    payload = build_items_yaml(
        data_collection,
        records=list(records) if records is not None else None,
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
    return destination


def write_item_outputs(
    data_collection: object,
    metadata_dir: Path | str,
    records: Iterable[dict[str, Any]] | None = None,
) -> tuple[Path, Path]:
    """Write both item files into one metadata directory.

    Parameters
    ----------
    data_collection : object
        Data collection used to build the item records.
    metadata_dir : Path or str
        Destination ``metadata`` directory.
    records : Iterable[dict], optional
        Prebuilt item records, so both files share one build.

    Returns
    -------
    tuple[Path, Path]
        The written ``items.yaml`` and ``items.csv`` paths.
    """
    rows = list(records) if records is not None else build_item_records(data_collection)
    directory = Path(metadata_dir)
    yaml_path = write_items_yaml(
        data_collection, directory / "items.yaml", records=rows
    )
    csv_path = write_items_table(data_collection, directory / "items.csv", records=rows)
    return yaml_path, csv_path
