"""Write questionnaire assets and the generated codebook to the output folder."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .codebook import CODEBOOK
from .mapping import build_mapping, find_questionnaire_files


def write_pq_assets(
    dataset_dir: Path | str,
    output_dir: Path | str,
    language: str,
    allow_fallback: bool = False,
) -> dict:
    """Copy the questionnaire assets and write the codebook and label mapping.

    The source files are copied to ``<output>/documentation/questionnaire/``.
    ``pq_codebook.yaml`` is always written. ``pq_mapping_<lang>.yaml`` is
    generated from the questionnaire when available; otherwise a stub with a
    fallback header is written.

    Parameters
    ----------
    dataset_dir : Path | str
        Raw data collection folder.
    output_dir : Path | str
        Preprocessed data collection folder.
    language : str
        Language code of the data collection (for example ``"EN"``).
    allow_fallback : bool
        When ``False``, a missing questionnaire or language file raises. When
        ``True``, processing can continue with raw questionnaire values.

    Returns
    -------
    dict
        Paths to the written files and the resolved source files.
    """
    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir)
    lang = str(language).lower()
    destination = output_dir / "documentation" / "questionnaire"
    destination.mkdir(parents=True, exist_ok=True)

    question_path, language_path = find_questionnaire_files(dataset_dir, lang)

    codebook_path = destination / "pq_codebook.yaml"
    codebook_path.write_text(
        yaml.safe_dump(CODEBOOK, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    if question_path is not None:
        shutil.copy2(question_path, destination / question_path.name)
    if language_path is not None:
        shutil.copy2(language_path, destination / language_path.name)

    mapping_path = destination / f"pq_mapping_{lang}.yaml"
    header = ""

    if question_path is None:
        expected = (
            f"{dataset_dir}/participant_questionnaire_*/"
            f"multipleye_questionnaire_questions_{lang}.xlsx"
        )
        header += (
            f"# FALLBACK: questionnaire xlsx not found. Expected {expected}\n"
            "# or the file under documentation/questionnaire/.\n"
            "# Raw PQ values are kept in pq_raw_*. Place the file in the data\n"
            "# collection folder to enable normalisation.\n"
        )
        mapping = {
            "language": lang,
            "fallback": True,
            "labels": {},
            "ordinal_positions": {},
            "languages": {},
            "issues": [],
        }
        mapping_path.write_text(
            header + yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        if not allow_fallback:
            raise FileNotFoundError(
                "Participant questionnaire not found. Expected "
                f"{expected} or documentation/questionnaire/. Set "
                "ALLOW_PQ_FALLBACK: true to continue with raw values."
            )
    else:
        mapping = build_mapping(question_path, language_path)
        mapping["language"] = lang
        mapping["fallback"] = False
        if language_path is None:
            header += (
                "# FALLBACK: language code file not found. Language fields stay\n"
                "# in the language of the data collection (no ISO 639-1 mapping).\n"
            )
            mapping["fallback"] = True
            if not allow_fallback:
                mapping_path.write_text(
                    header
                    + yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                raise FileNotFoundError(
                    "Language code file not found (expected "
                    f"language_iso639_1_{lang}.xlsx). Set ALLOW_PQ_FALLBACK: true "
                    "to continue with localised language names."
                )
        mapping_path.write_text(
            header + yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    return {
        "codebook": codebook_path,
        "mapping": mapping_path,
        "questionnaire": question_path,
        "language_file": language_path,
    }


__all__ = ["write_pq_assets"]
