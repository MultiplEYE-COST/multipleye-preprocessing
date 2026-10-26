"""Build per-language label maps from a questionnaire workbook."""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from .codebook import CODEBOOK, READING_TIME_QUESTIONS

_WHITESPACE = re.compile(r"\s+")
_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_label(value: object) -> str:
    """Return a matching-friendly label (whitespace, case, digits, dashes)."""
    text = _WHITESPACE.sub(" ", str(value)).strip().lower()
    text = text.translate(_DIGITS)
    text = text.replace("–", "-").replace("—", "-").replace("’", "'")
    return text


def _as_int(value: object) -> int | None:
    try:
        number = float(str(value).strip().translate(_DIGITS))
    except (TypeError, ValueError):
        return None
    if not number.is_integer():
        return None
    return int(number)


def _is_range(value: object) -> bool:
    parts = str(value).split(";")
    return len(parts) == 2 and all(_as_int(part) is not None for part in parts)


def _read_questionnaire(path: Path) -> dict[str, dict]:
    sheets = pl.read_excel(path, sheet_id=0, has_header=True)
    frame = next(iter(sheets.values()))
    rows: dict[str, dict] = {}
    for row in frame.iter_rows(named=True):
        identifier = row.get("pq_question_identifier")
        if not identifier:
            continue
        options = []
        for index in range(1, 20):
            option = row.get(f"pq_answer_option_{index}")
            if option is None:
                break
            if str(option).strip():
                options.append(str(option))
        rows[str(identifier)] = {
            "answer_type": row.get("pq_answer_type"),
            "options": options,
        }
    return rows


def read_language_file(path: Path) -> dict[str, str]:
    """Return ``{normalized language name: iso639_1 code}``."""
    sheets = pl.read_excel(path, sheet_id=0, has_header=True)
    frame = next(iter(sheets.values()))
    mapping: dict[str, str] = {}
    for row in frame.iter_rows(named=True):
        code = row.get("language_code")
        name = row.get("language_name")
        if code and name:
            mapping[normalize_label(name)] = str(code).strip().lower()
    return mapping


def _find_case_insensitive(directory: Path, filename: str) -> Path | None:
    if not directory.exists():
        return None
    wanted = filename.lower()
    for candidate in directory.rglob("*"):
        if candidate.is_file() and candidate.name.lower() == wanted:
            return candidate
    return None


def _find_glob(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    for candidate in sorted(directory.rglob(pattern)):
        if candidate.is_file():
            return candidate
    return None


def _referenced_language_file(questionnaire_path: Path) -> str | None:
    """Return the language workbook referenced by a ``dropdown_file`` question."""
    for row in _read_questionnaire(questionnaire_path).values():
        if row["answer_type"] != "dropdown_file":
            continue
        for option in row["options"]:
            if "language_iso639_1_" in option:
                return option
    return None


def find_questionnaire_files(
    dataset_dir: Path | str, language: str
) -> tuple[Path | None, Path | None]:
    """Locate the questionnaire questions and language-code workbook.

    Searches the dataset root, ``participant_questionnaire_*`` folders and
    ``documentation/`` (including subfolders), case-insensitively. For the
    language workbook, the exact ``language_iso639_1_<lang>.xlsx`` is preferred,
    then the file referenced by the questionnaire, then any language workbook.
    """
    dataset_dir = Path(dataset_dir)
    lang = str(language).lower()
    question_name = f"multipleye_questionnaire_questions_{lang}.xlsx"
    language_name = f"language_iso639_1_{lang}.xlsx"

    roots = [dataset_dir]
    roots.extend(
        path
        for path in sorted(dataset_dir.glob("participant_questionnaire*"))
        if path.is_dir()
    )
    documentation = dataset_dir / "documentation"
    if documentation.is_dir():
        roots.append(documentation)

    question_path = None
    language_path = None
    for root in roots:
        if question_path is None:
            question_path = _find_case_insensitive(root, question_name)
        if language_path is None:
            language_path = _find_case_insensitive(root, language_name)

    if language_path is None and question_path is not None:
        referenced = _referenced_language_file(question_path)
        if referenced:
            for root in roots:
                language_path = _find_case_insensitive(root, referenced)
                if language_path is not None:
                    break

    if language_path is None:
        for root in roots:
            language_path = _find_glob(root, "language_iso639_1_*.xlsx")
            if language_path is not None:
                break

    return question_path, language_path


def build_mapping(
    questionnaire_path: Path | str,
    language_file_path: Path | str | None = None,
) -> dict:
    """Build a label mapping for one language from its questionnaire workbook.

    The canonical codes come from the codebook; localized labels are aligned by
    option order. Mismatches are reported in ``issues`` instead of failing.
    """
    rows = _read_questionnaire(Path(questionnaire_path))
    labels: dict[str, dict[str, str]] = {}
    ordinal_positions: dict[str, dict[str, int]] = {}
    issues: list[str] = []

    for field, spec in CODEBOOK["fields"].items():
        if spec["type"] == "iso639_1":
            continue

        question = spec.get("question")
        row = rows.get(question)
        if row is None:
            issues.append(f"Question '{question}' not found in the questionnaire.")
            continue

        options = row["options"]

        if field == "years_education":
            open_ended = spec["open_ended"]["code"]
            for option in options:
                if not _is_range(option):
                    labels.setdefault(field, {})[normalize_label(option)] = open_ended
            continue

        if field == "age":
            continue

        if "codes" in spec:
            codes = [
                code["code"] if isinstance(code, dict) else code
                for code in spec["codes"]
            ]
            if len(options) != len(codes):
                issues.append(
                    f"Question '{question}' has {len(options)} options, "
                    f"expected {len(codes)}."
                )
            for option, code in zip(options, codes):
                labels.setdefault(field, {})[normalize_label(option)] = code
            continue

        if "min" in spec and "max" in spec:
            for offset, option in enumerate(options):
                ordinal_positions.setdefault(field, {})[normalize_label(option)] = (
                    int(spec["min"]) + offset
                )

    reading_row = None
    for question in READING_TIME_QUESTIONS:
        if question in rows:
            reading_row = rows[question]
            break
    if reading_row is not None:
        codes = [
            code["code"] for code in CODEBOOK["fields"]["reading_time_bin"]["codes"]
        ]
        if len(reading_row["options"]) != len(codes):
            issues.append(
                f"Reading-time question has {len(reading_row['options'])} options, "
                f"expected {len(codes)}."
            )
        for option, code in zip(reading_row["options"], codes):
            labels.setdefault("reading_time_bin", {})[normalize_label(option)] = code
    else:
        issues.append("No reading-time question found in the questionnaire.")

    language_map: dict[str, str] = {}
    if language_file_path is not None:
        language_map = read_language_file(Path(language_file_path))

    return {
        "labels": labels,
        "ordinal_positions": ordinal_positions,
        "languages": language_map,
        "issues": issues,
    }
