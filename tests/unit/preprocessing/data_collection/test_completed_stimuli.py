import logging
from pathlib import Path
from types import SimpleNamespace

import polars as pl

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)

SESSION_ID = "001_EN_UK_1_ET1"


def _load_completed_stimuli(
    tmp_path: Path, rows: list[dict]
) -> tuple[list, list, dict, MultipleyeDataCollection]:
    log_dir = tmp_path / "logfiles"
    log_dir.mkdir(parents=True)
    pl.DataFrame(rows).write_csv(log_dir / "completed_stimuli.csv")

    collection = object.__new__(MultipleyeDataCollection)
    collection.sessions = {
        SESSION_ID: SimpleNamespace(session_folder_path=tmp_path),
    }
    collection.skipped_sessions = {}
    collection.crashed_session_ids = []
    collection.logger = logging.getLogger("test")

    ids, names, mapping = collection._load_session_completed_stimuli(SESSION_ID)
    return ids, names, mapping, collection


def test_mapping_only_includes_completed_trials(tmp_path: Path) -> None:
    rows = [
        {"trial_id": 1, "stimulus_name": "StimA", "stimulus_id": 1, "completed": 1},
        {"trial_id": 2, "stimulus_name": "StimB", "stimulus_id": 2, "completed": 1},
        {"trial_id": 3, "stimulus_name": "StimC", "stimulus_id": 3, "completed": 0},
    ]

    ids, names, mapping, _ = _load_completed_stimuli(tmp_path, rows)

    assert ids == [1, 2]
    assert mapping == {"trial_1": "StimA", "trial_2": "StimB"}
    assert names == ["StimA_1", "StimB_2"]
    assert len(mapping) == len(ids)


def test_mapping_skips_none_trial_id_without_shifting(tmp_path: Path) -> None:
    rows = [
        {"trial_id": None, "stimulus_name": "StimB", "stimulus_id": 2, "completed": 1},
        {"trial_id": 3, "stimulus_name": "StimC", "stimulus_id": 3, "completed": 1},
    ]

    ids, names, mapping, _ = _load_completed_stimuli(tmp_path, rows)

    assert ids == [2, 3]
    assert mapping == {"trial_3": "StimC"}
    assert names == ["StimB_2", "StimC_3"]


def test_practice_trial_key_is_normalized(tmp_path: Path) -> None:
    rows = [
        {
            "trial_id": "PRACTICE_1",
            "stimulus_name": "StimP",
            "stimulus_id": 10,
            "completed": 1,
        },
    ]

    _, _, mapping, _ = _load_completed_stimuli(tmp_path, rows)

    assert mapping == {"PRACTICE_trial_1": "StimP"}


def test_restart_row_is_excluded(tmp_path: Path) -> None:
    rows = [
        {"trial_id": 1, "stimulus_name": "StimA", "stimulus_id": 1, "completed": 1},
        {
            "trial_id": 2,
            "stimulus_name": "StimB",
            "stimulus_id": 2,
            "completed": "restart",
        },
    ]

    ids, _, mapping, collection = _load_completed_stimuli(tmp_path, rows)

    assert ids == [1]
    assert mapping == {"trial_1": "StimA"}
    assert collection.crashed_session_ids == ["001"]
