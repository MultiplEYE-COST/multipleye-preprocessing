"""Tests for the item view metadata files."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from preprocessing import settings
from preprocessing.data_collection.item_table import (
    ITEM_COLUMNS,
    build_item_records,
    build_items_yaml,
    write_item_outputs,
)
from preprocessing.data_collection.stimulus import (
    ComprehensionQuestion,
    Stimulus,
    StimulusPage,
)
from preprocessing.data_collection.trial import Trial

DCN = "MultiplEYE_EN_UK_Test_1_2026"


class FakeSession:
    def __init__(
        self,
        session_identifier: str,
        participant_id: int,
        tested_language: str,
        stimuli: object,
        trials: object,
    ):
        self.session_identifier = session_identifier
        self.participant_id = participant_id
        self.tested_language = tested_language
        self.stimuli = stimuli
        self.trials = trials


class FakeCollection:
    def __init__(
        self,
        sessions: dict[str, FakeSession],
        metadata_form: dict | None = None,
    ):
        self.sessions = sessions
        self.skipped_sessions = {}
        self.data_collection_name = DCN
        self.language = "EN"
        self._metadata_form = metadata_form if metadata_form is not None else {}

    def _load_metadata_form(self) -> dict:
        return self._metadata_form


def _page(number: int, text: str) -> StimulusPage:
    return StimulusPage(
        number=number,
        text=text,
        image_path=Path(f"page_{number}.png"),
        aoi_image_path=Path(f"page_{number}_aoi.png"),
    )


def _question() -> ComprehensionQuestion:
    return ComprehensionQuestion(
        name="Lit_MagicMountain_6_6111",
        id="6111",
        snippet_no=1,
        question="What did the mountain do?",
        target="It was quiet.",
        distractor_a="It was loud.",
        distractor_b="It was cold.",
        distractor_c="It was green.",
        image_path=Path("question.png"),
        aoi_image_path=Path("question_aoi.png"),
        condition_no=1,
        question_type="local",
    )


def _mountain() -> Stimulus:
    return Stimulus(
        id=6,
        name="Lit_MagicMountain",
        type="experiment",
        pages=[
            _page(1, "The mountain was quiet."),
            _page(2, "It was cold today."),
        ],
        text_stimulus=None,
        questions=[_question()],
        instructions=[],
        ratings=[],
        trial_id="trial_1",
    )


def _wiki_moon() -> Stimulus:
    return Stimulus(
        id=13,
        name="Enc_WikiMoon",
        type="practice",
        pages=[_page(1, "The moon is bright.")],
        text_stimulus=None,
        questions=[],
        instructions=[],
        ratings=[],
        trial_id="PRACTICE_trial_1",
    )


def _trial(
    trial_id: str,
    trial_number: int,
    stimulus_id: int,
    stimulus_name: str,
    text_id: str,
    *,
    is_practice: bool = False,
    familiarity_1: float | str = 2.0,
    familiarity_2: float | str = 2.0,
    subjective_difficulty: float | str = 3.0,
    comprehension_score: float = 1.0,
) -> Trial:
    return Trial(
        trial_id=trial_id,
        trial_number=trial_number,
        stimulus_id=stimulus_id,
        stimulus_name=stimulus_name,
        text_id=text_id,
        is_practice=is_practice,
        num_questions=1,
        num_questions_local=1,
        num_questions_global=0,
        num_questions_bridging=0,
        comprehension_score=comprehension_score,
        comprehension_score_local=comprehension_score,
        comprehension_score_global="unknown",
        comprehension_score_bridging="unknown",
        comprehension_question_time_ms=1000.0,
        reading_time_ms=2000.0,
        familiarity_1=familiarity_1,
        familiarity_2=familiarity_2,
        subjective_difficulty=subjective_difficulty,
    )


@pytest.fixture(autouse=True)
def no_language_node(monkeypatch) -> None:
    """Keep the item view free of a language node unless a test configures one."""
    for name in (
        "LANGUAGE_NODE_ID",
        "LANGUAGE_TREE_PATH",
        "LANGUAGE_NODE_LABEL",
        "LANGUAGE_TREE_VERSION",
        "LANGUAGE_TREE_HASH",
        "LANGUAGE_TREE_SNAPSHOT",
    ):
        monkeypatch.setattr(settings, name, None, raising=False)


@pytest.fixture
def collection() -> FakeCollection:
    sessions = {
        "001_EN_UK_1_ET1": FakeSession(
            "001_EN_UK_1_ET1",
            participant_id=1,
            tested_language="EN",
            stimuli=[_mountain(), _wiki_moon()],
            trials=[
                _trial(
                    "trial_1",
                    1,
                    6,
                    "Lit_MagicMountain",
                    "Lit_MagicMountain_en",
                    familiarity_1=2.0,
                    familiarity_2=2.0,
                    subjective_difficulty=3.0,
                    comprehension_score=1.0,
                ),
                _trial(
                    "PRACTICE_trial_1",
                    1,
                    13,
                    "Enc_WikiMoon",
                    "Enc_WikiMoon_en",
                    is_practice=True,
                    familiarity_1="unknown",
                    familiarity_2="unknown",
                    subjective_difficulty="unknown",
                    comprehension_score=1.0,
                ),
            ],
        ),
        "002_EN_UK_1_ET1": FakeSession(
            "002_EN_UK_1_ET1",
            participant_id=2,
            tested_language="EN",
            stimuli=[_mountain()],
            trials=[
                _trial(
                    "trial_1",
                    1,
                    6,
                    "Lit_MagicMountain",
                    "Lit_MagicMountain_en",
                    familiarity_1=2.0,
                    familiarity_2=3.0,
                    subjective_difficulty=3.0,
                    comprehension_score=0.5,
                )
            ],
        ),
    }
    return FakeCollection(
        sessions,
        metadata_form={"Tested_language": {"Language_script": ["Latin"]}},
    )


@pytest.fixture
def written(collection: FakeCollection, tmp_path: Path) -> tuple[dict, Path, Path]:
    metadata_dir = tmp_path / "metadata"
    yaml_path, csv_path = write_item_outputs(collection, metadata_dir)
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return payload, yaml_path, csv_path


def _items_by_id(payload: dict) -> dict[str, dict]:
    return {item["text_id"]: item for item in payload["items"]}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_items_yaml_contains_one_record_per_text_id(written) -> None:
    payload, yaml_path, _ = written

    assert yaml_path == yaml_path.parent / "items.yaml"
    assert [item["text_id"] for item in payload["items"]] == [
        "Enc_WikiMoon_en",
        "Lit_MagicMountain_en",
    ]


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("data_collection_name", DCN),
        ("stimulus_id", 6),
        ("stimulus_name", "Lit_MagicMountain"),
        ("tested_language", "EN"),
        ("language_script", ["Latin"]),
        ("stimulus_role", "experiment"),
        ("stimulus_genre", "unknown"),
        ("stimulus_structure", "unknown"),
        ("num_words", 8),
        ("num_chars", 41),
        ("num_screens", 2),
        ("annotation_layers", []),
        ("annotation_package", "unknown"),
    ],
)
def test_item_metadata_fields(written, field: str, expected: object) -> None:
    item = _items_by_id(written[0])["Lit_MagicMountain_en"]

    assert item[field] == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("familiarity_mean", 2.25),
        ("familiarity_mode", 2),
        ("difficulty_mean", 3.0),
        ("difficulty_mode", 3),
        ("comprehension_accuracy_mean", 0.75),
        ("num_participants", 2),
        ("num_trials", 2),
    ],
)
def test_item_aggregates_from_matching_trials(
    written, field: str, expected: object
) -> None:
    item = _items_by_id(written[0])["Lit_MagicMountain_en"]

    assert item[field] == expected


def test_practice_item_keeps_missing_ratings_empty(written) -> None:
    item = _items_by_id(written[0])["Enc_WikiMoon_en"]

    assert item["stimulus_role"] == "practice"
    assert item["familiarity_mean"] is None
    assert item["familiarity_mode"] is None
    assert item["difficulty_mean"] is None
    assert item["difficulty_mode"] is None
    assert item["comprehension_accuracy_mean"] == 1.0
    assert item["num_trials"] == 1
    assert item["num_participants"] == 1
    assert item["questions"] == []


def test_item_questions_and_options(written) -> None:
    item = _items_by_id(written[0])["Lit_MagicMountain_en"]

    assert item["questions"] == [
        {
            "question_id": "6111",
            "item_id": "Lit_MagicMountain_6_6111",
            "condition": "local",
            "condition_number": 1,
            "question_type": "local",
            "question_text": "What did the mountain do?",
            "options": {
                "target": "It was quiet.",
                "distractor_a": "It was loud.",
                "distractor_b": "It was cold.",
                "distractor_c": "It was green.",
            },
        }
    ]


def test_item_text_ids_match_trial_text_ids(collection: FakeCollection) -> None:
    item_ids = {item["text_id"] for item in build_item_records(collection)}
    trial_ids = {
        trial.text_id
        for session in collection.sessions.values()
        for trial in session.trials
    }

    assert item_ids == trial_ids


def test_yaml_and_csv_are_consistent(written) -> None:
    payload, _, csv_path = written
    csv_rows = {row["text_id"]: row for row in _csv_rows(csv_path)}

    assert set(csv_rows) == set(_items_by_id(payload))

    for text_id, item in _items_by_id(payload).items():
        row = csv_rows[text_id]
        assert list(row) == list(ITEM_COLUMNS)
        for column in ITEM_COLUMNS:
            value = item.get(column)
            if column == "questions":
                assert json.loads(row[column]) == value
            elif value is None:
                assert row[column] == ""
            elif isinstance(value, list | dict):
                assert json.loads(row[column]) == value
            else:
                assert row[column] == str(value)


def test_missing_source_values_stay_empty(tmp_path: Path) -> None:
    stimulus = Stimulus(
        id=6,
        name="Lit_MagicMountain",
        type="experiment",
        pages=[],
        text_stimulus=None,
        questions=[],
        instructions=[],
        ratings=[],
        trial_id="trial_1",
    )
    collection = FakeCollection(
        {
            "001_EN_UK_1_ET1": FakeSession(
                "001_EN_UK_1_ET1",
                participant_id=1,
                tested_language="EN",
                stimuli=[stimulus],
                trials="unknown",
            )
        }
    )

    item = build_items_yaml(collection)["items"][0]

    assert item["familiarity_mean"] is None
    assert item["familiarity_mode"] is None
    assert item["difficulty_mean"] is None
    assert item["difficulty_mode"] is None
    assert item["comprehension_accuracy_mean"] is None
    assert item["num_participants"] is None
    assert item["num_trials"] is None
    assert item["language_script"] == "unknown"
    assert item["stimulus_genre"] == "unknown"
    assert item["stimulus_structure"] == "unknown"
    assert item["annotation_layers"] == []
    assert item["annotation_package"] == "unknown"
    assert item["questions"] == []
    assert item["num_words"] == 0
    assert item["num_chars"] == 0
    assert item["num_screens"] == 0
    assert "language_node_id" not in item


def test_empty_collection_writes_header_only(tmp_path: Path) -> None:
    yaml_path, csv_path = write_item_outputs(FakeCollection({}), tmp_path)
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    assert payload == {"items": []}
    assert csv_path.read_text(encoding="utf-8").splitlines() == [",".join(ITEM_COLUMNS)]


@pytest.mark.parametrize("stimuli", ["unknown", None])
def test_unloaded_stimuli_produce_no_items(tmp_path: Path, stimuli: object) -> None:
    collection = FakeCollection(
        {
            "001_EN_UK_1_ET1": FakeSession(
                "001_EN_UK_1_ET1",
                participant_id=1,
                tested_language="EN",
                stimuli=stimuli,
                trials=[],
            )
        }
    )

    assert build_items_yaml(collection) == {"items": []}


def test_language_node_fields_when_configured(
    collection: FakeCollection, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "LANGUAGE_NODE_ID", "german", raising=False)
    monkeypatch.setattr(
        settings,
        "LANGUAGE_TREE_PATH",
        "indo_european/germanic/german",
        raising=False,
    )
    monkeypatch.setattr(settings, "LANGUAGE_TREE_VERSION", "v1", raising=False)

    item = build_items_yaml(collection)["items"][0]

    assert item["language_node_id"] == "german"
    assert item["language_node_path"] == "indo_european/germanic/german"
    assert item["language_node_label"] is None
    assert item["language_tree_version"] == "v1"
    assert item["language_tree_hash"] is None


def test_language_node_fields_without_snapshot(
    collection: FakeCollection, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "LANGUAGE_NODE_ID", "german", raising=False)
    monkeypatch.setattr(
        settings,
        "LANGUAGE_TREE_PATH",
        "indo_european/germanic/german",
        raising=False,
    )
    monkeypatch.setattr(settings, "LANGUAGE_NODE_LABEL", "German", raising=False)
    monkeypatch.setattr(settings, "LANGUAGE_TREE_VERSION", "2026.10", raising=False)
    monkeypatch.setattr(
        settings, "LANGUAGE_TREE_HASH", "sha256:configured", raising=False
    )
    monkeypatch.setattr(settings, "LANGUAGE_TREE_SNAPSHOT", None, raising=False)

    item = build_items_yaml(collection)["items"][0]

    assert item["language_node_id"] == "german"
    assert item["language_node_path"] == "indo_european/germanic/german"
    assert item["language_node_label"] == "German"
    assert item["language_tree_version"] == "2026.10"
    assert item["language_tree_hash"] == "sha256:configured"


def test_item_records_are_sorted_by_text_id(collection: FakeCollection) -> None:
    records = build_item_records(collection)

    assert [record["text_id"] for record in records] == sorted(
        record["text_id"] for record in records
    )
