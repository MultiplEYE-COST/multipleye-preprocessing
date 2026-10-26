"""Tests for participant questionnaire normalisation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml
from openpyxl import Workbook

from preprocessing.checks.preflight import _check_pq_assets
from preprocessing.config import settings
from preprocessing.utils.pq_normalisation import (
    build_mapping,
    find_pq_data,
    find_questionnaire_files,
    normalise_pq,
    write_pq_assets,
)

_LEVELS_DE = [
    "Grundschule",
    "Primarstufe",
    "Sekundarstufe I",
    "Sekundarstufe II",
    "Postsekundar",
    "Kurzstudium",
    "Bachelor",
    "Master",
    "Doktorat",
]
_READING_DE = [
    "0 Stunden",
    "weniger als 1 Stunde",
    "1 bis 3 Stunden",
    "3 bis 5 Stunden",
    "mehr als 5 Stunden",
]

_QUESTIONNAIRE_DE = {
    "gender": ("dropdown", ["männlich", "weiblich", "anderes", "keine Angabe"]),
    "years_education": ("interval", ["1;20", ">20 Jahre"]),
    "level_education": ("dropdown", _LEVELS_DE),
    "age": ("interval", ["18;120"]),
    "socio_economic_status": (
        "dropdown",
        [
            "unterdurchschnittlich",
            "durchschnittlich",
            "überdurchschnittlich",
            "keine Angabe",
        ],
    ),
    "childhood_languages": (
        "dropdown",
        ["eine Sprache", "zwei Sprachen", "drei Sprachen"],
    ),
    "native_language_1": ("dropdown_file", ["language_iso639_1_de.xlsx"]),
    "academic_reading_time": ("dropdown", _READING_DE),
    "tiredness": ("dropdown", [f"{i} - Stufe {i}" for i in range(1, 10)]),
    "eyewear": ("dropdown", ["Brille", "Kontaktlinsen", "Nein"]),
    "alcohol_yesterday": ("dropdown", ["Nein", "Ja", "keine Angabe"]),
}


def _write_questionnaire(path: Path, rows: dict) -> Path:
    wb = Workbook()
    ws = wb.active
    headers = [
        "pq_question_identifier",
        "pq_answer_type",
        *[f"pq_answer_option_{i}" for i in range(1, 11)],
    ]
    ws.append(headers)
    for identifier, (answer_type, options) in rows.items():
        ws.append([identifier, answer_type, *options])
    wb.save(path)
    return path


def _write_language_file(path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["", "language_code", "language_name"])
    ws.append([0, "de", "Deutsch"])
    ws.append([1, "en", "Englisch"])
    wb.save(path)
    return path


@pytest.fixture
def questionnaire_de(tmp_path: Path) -> Path:
    return _write_questionnaire(tmp_path / "questions_de.xlsx", _QUESTIONNAIRE_DE)


@pytest.fixture
def language_file(tmp_path: Path) -> Path:
    return _write_language_file(tmp_path / "language_iso639_1_de.xlsx")


@pytest.fixture
def mapping_de(questionnaire_de: Path, language_file: Path) -> dict:
    return build_mapping(questionnaire_de, language_file)


def test_build_mapping_maps_labels_by_position(mapping_de: dict) -> None:
    assert mapping_de["labels"]["gender"]["weiblich"] == "female"
    assert mapping_de["labels"]["reading_time_bin"]["1 bis 3 stunden"] == "1_to_3_hours"
    assert mapping_de["ordinal_positions"]["tiredness"]["7 - stufe 7"] == 7
    assert mapping_de["languages"]["deutsch"] == "de"
    assert mapping_de["issues"] == []


def test_normalise_pq_maps_values(mapping_de: dict) -> None:
    pq = {
        "gender": "weiblich",
        "years_education": 16,
        "level_education": "Bachelor",
        "age": 23,
        "socio_economic_status": "durchschnittlich",
        "childhood_languages": "zwei Sprachen",
        "native_language_1": "Deutsch",
        "native_language_1_academic_reading_time": "1 bis 3 Stunden",
        "tiredness": "7 - Stufe 7",
        "eyewear": "Brille",
        "alcohol_yesterday": "Nein",
        "native_language_1_dialect": True,
        "confirm_answer": True,
    }

    result = normalise_pq(pq, mapping_de)
    values = result["values"]

    assert values["pq_gender"] == "female"
    assert values["pq_years_education"] == 16
    assert values["pq_level_education"] == "bachelor"
    assert values["pq_age"] == 23
    assert values["pq_socio_economic_status"] == "average"
    assert values["pq_childhood_languages"] == "two_languages"
    assert values["pq_native_language_1"] == "de"
    assert values["pq_native_language_1_academic_reading_time"] == "1_to_3_hours"
    assert values["pq_tiredness"] == 7
    assert values["pq_eyewear"] == "glasses"
    assert values["pq_alcohol_yesterday"] == "no"
    assert values["pq_raw_native_language_1_dialect"] is True
    assert values["pq_raw_confirm_answer"] is True
    assert result["issues"] == []


def test_normalise_pq_open_ended_years_education(mapping_de: dict) -> None:
    result = normalise_pq({"years_education": ">20 Jahre"}, mapping_de)
    values = result["values"]

    assert values["pq_years_education_open_ended"] is True
    assert "pq_years_education" not in values
    assert values["pq_raw_years_education"] == ">20 Jahre"


def test_normalise_pq_without_language_file(questionnaire_de: Path) -> None:
    mapping = build_mapping(questionnaire_de, None)
    result = normalise_pq({"native_language_1": "Deutsch"}, mapping)
    values = result["values"]

    assert "pq_native_language_1" not in values
    assert values["pq_raw_native_language_1"] == "Deutsch"
    assert any("Language code file" in issue for issue in result["issues"])


def test_find_questionnaire_files_case_insensitive(tmp_path: Path) -> None:
    folder = tmp_path / "participant_questionnaire_DE_DE_1"
    folder.mkdir()
    question = folder / "multipleye_questionnaire_questions_DE.xlsx"
    language = folder / "language_iso639_1_DE.xlsx"
    question.write_text("x", encoding="utf-8")
    language.write_text("x", encoding="utf-8")

    found_question, found_language = find_questionnaire_files(tmp_path, "de")

    assert found_question == question
    assert found_language == language


def test_write_pq_assets_copies_files_and_writes_mapping(
    tmp_path: Path, questionnaire_de: Path, language_file: Path
) -> None:
    dataset_dir = tmp_path / "data"
    folder = dataset_dir / "participant_questionnaire_DE_DE_1"
    folder.mkdir(parents=True)
    questionnaire = folder / "multipleye_questionnaire_questions_DE.xlsx"
    language = folder / "language_iso639_1_DE.xlsx"
    questionnaire.write_bytes(questionnaire_de.read_bytes())
    language.write_bytes(language_file.read_bytes())

    result = write_pq_assets(dataset_dir, tmp_path / "out", "DE")

    destination = tmp_path / "out" / "documentation" / "questionnaire"
    assert result["codebook"] == destination / "pq_codebook.yaml"
    assert result["mapping"] == destination / "pq_mapping_de.yaml"
    assert (destination / questionnaire.name).exists()
    assert (destination / language.name).exists()
    mapping = yaml.safe_load(result["mapping"].read_text(encoding="utf-8"))
    assert mapping["fallback"] is False
    assert mapping["labels"]["gender"]["weiblich"] == "female"


def test_write_pq_assets_fallback(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "data"
    (dataset_dir / "documentation").mkdir(parents=True)

    result = write_pq_assets(dataset_dir, tmp_path / "out", "DE", allow_fallback=True)

    text = result["mapping"].read_text(encoding="utf-8")
    assert text.startswith("# FALLBACK")
    mapping = yaml.safe_load(text)
    assert mapping["fallback"] is True
    assert mapping["labels"] == {}

    with pytest.raises(FileNotFoundError, match="ALLOW_PQ_FALLBACK"):
        write_pq_assets(dataset_dir, tmp_path / "out2", "DE", allow_fallback=False)


def test_check_pq_assets_error_and_warning(tmp_path: Path, monkeypatch) -> None:
    dataset_dir = tmp_path / "data"
    (dataset_dir / "documentation").mkdir(parents=True)
    monkeypatch.setattr(settings, "DATASET_DIR", dataset_dir)
    monkeypatch.setattr(settings, "EXPERIMENT_TYPE", "MultiplEYE")
    dc = SimpleNamespace(
        data_collection_name="MultiplEYE_DE_DE_Test_1_2026",
        language="DE",
        stimulus_dir=tmp_path / "stimuli",
    )

    monkeypatch.setattr(settings, "ALLOW_PQ_FALLBACK", False)
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}
    _check_pq_assets(dc, errors, warnings)
    assert "Participant questionnaire" in errors
    assert warnings == {}

    monkeypatch.setattr(settings, "ALLOW_PQ_FALLBACK", True)
    errors = {}
    warnings = {}
    _check_pq_assets(dc, errors, warnings)
    assert errors == {}
    assert "Participant questionnaire" in warnings

    folder = dataset_dir / "participant_questionnaire_DE_DE_1"
    folder.mkdir()
    (folder / "multipleye_questionnaire_questions_DE.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (folder / "language_iso639_1_DE.xlsx").write_text("x", encoding="utf-8")
    errors = {}
    warnings = {}
    _check_pq_assets(dc, errors, warnings)
    assert errors == {}
    assert warnings == {}


def test_normalise_pq_handles_missing_values(mapping_de: dict) -> None:
    result = normalise_pq(
        {"gender": pd.NA, "native_language_1_fiction_reading_time": pd.NA},
        mapping_de,
    )
    values = result["values"]

    assert values["pq_raw_gender"] is pd.NA
    assert "pq_gender" not in values
    assert "pq_native_language_1_fiction_reading_time" not in values


def test_find_pq_data_prefers_session_dir(tmp_path: Path) -> None:
    session_dir = tmp_path / "sessions" / "068_RO_RO_1_ET1"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "068_RO_RO_1_pq_data.json"
    session_file.write_text("{}", encoding="utf-8")
    questionnaire_dir = tmp_path / "participant_questionnaire_RO_RO_1"
    questionnaire_dir.mkdir()
    (questionnaire_dir / "068_RO_RO_1_pq_data.json").write_text("{}", encoding="utf-8")

    found = find_pq_data(68, [session_dir], [questionnaire_dir])

    assert found == session_file


def test_find_pq_data_in_questionnaire_dir_short_pid(tmp_path: Path) -> None:
    questionnaire_dir = tmp_path / "participant_questionnaire_KL_DK_1"
    questionnaire_dir.mkdir()
    expected = questionnaire_dir / "6_KL_DK_1_pq_data.json"
    expected.write_text("{}", encoding="utf-8")

    assert find_pq_data("006", [], [questionnaire_dir]) == expected
    assert find_pq_data("6", [], [questionnaire_dir]) == expected


def test_find_pq_data_returns_none(tmp_path: Path) -> None:
    assert find_pq_data(1, [tmp_path], [tmp_path]) is None
    assert find_pq_data("6->7", [tmp_path], [tmp_path]) is None


def test_find_questionnaire_files_uses_referenced_language_file(tmp_path: Path) -> None:
    folder = tmp_path / "participant_questionnaire_FR_FR_1"
    folder.mkdir()
    questionnaire = folder / "multipleye_questionnaire_questions_FR.xlsx"
    _write_questionnaire(
        questionnaire,
        {"native_language_1": ("dropdown_file", ["language_iso639_1_en.xlsx"])},
    )
    language = folder / "language_iso639_1_en.xlsx"
    _write_language_file(language)
    (folder / "language_iso639_1_de.xlsx").write_text("x", encoding="utf-8")

    found_question, found_language = find_questionnaire_files(tmp_path, "fr")

    assert found_question == questionnaire
    assert found_language == language
