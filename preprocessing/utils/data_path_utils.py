"""Utilities for working with paths, session identifiers, and further data locations."""

import fnmatch
import json
import os
from pathlib import Path

import yaml

from preprocessing.config import settings

from ..models.sid import Sid

__all__ = [
    "check_data_collection_exists",
    "find_metadata_form",
    "find_psychometric_config_files",
    "legacy_metadata_form_path",
    "load_metadata_form",
    "validate_psychometric_data",
]


def _ci_exists(path: Path) -> bool:
    """Check if a path exists, falling back to case-insensitive comparison."""
    if path.exists():
        return True
    parent = path.parent
    if not parent.exists():
        return False
    try:
        entries = os.listdir(parent)
    except OSError:
        return False
    target = path.name.casefold()
    return any(entry.casefold() == target for entry in entries)


def _ci_resolve(path: Path) -> Path:
    """Resolve a path to its actual on-disk spelling (case correction)."""
    if path.exists():
        return path
    parent = path.parent
    if not parent.exists():
        return path
    try:
        entries = os.listdir(parent)
    except OSError:
        return path
    target = path.name.casefold()
    for entry in entries:
        if entry.casefold() == target:
            return parent / entry
    return path


def _ci_glob(directory: Path, pattern: str) -> list[Path]:
    """Case-insensitive glob, returning actual on-disk paths."""
    if not directory.exists():
        return []
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    pattern_cf = pattern.casefold()
    return [
        directory / entry
        for entry in entries
        if fnmatch.fnmatch(entry.casefold(), pattern_cf)
    ]


def _metadata_form_stem(path: Path) -> str:
    """Return a metadata-form filename without its extension or trailing spaces."""
    name = path.name
    if name.casefold().endswith(".json"):
        name = name[:-5]
    return name.rstrip()


def legacy_metadata_form_path(
    documentation_dir: Path,
    language: str | None,
    country: str | None,
    city: str | None,
    lab_number: int | str | None,
    year: int | str | None,
) -> Path | None:
    """
    Return the legacy ``MultiplEYE_<...>_metadata_form.json`` path, if derivable.

    Parameters
    ----------
    documentation_dir : Path
        The data collection's ``documentation`` folder.
    language, country, city : str | None
        Components of the legacy file name.
    lab_number, year : int | str | None
        Components of the legacy file name.

    Returns
    -------
    Path | None
        The expected legacy path, or None if any name component is missing.
    """
    components = (language, country, city, lab_number, year)
    if any(value is None or value == "" for value in components):
        return None
    return (
        documentation_dir
        / f"MultiplEYE_{language}_{country}_{city}_{lab_number}_{year}_metadata_form.json"
    )


def find_metadata_form(
    documentation_dir: Path,
    data_collection_name: str | None = None,
    *,
    language: str | None = None,
    country: str | None = None,
    city: str | None = None,
    lab_number: int | str | None = None,
    year: int | str | None = None,
) -> Path | None:
    """
    Locate the metadata form JSON in a data collection's ``documentation`` folder.

    Uploads use either ``metadataForm_<name>.json`` or
    ``metadataform_<name>.json``, sometimes with a trailing space before the
    extension. Matching is case-insensitive. A file matching the data
    collection name is preferred; if exactly one candidate exists it is used
    even when its name does not match. The legacy
    ``MultiplEYE_<...>_metadata_form.json`` naming is used as a fallback.

    Parameters
    ----------
    documentation_dir : Path
        The data collection's ``documentation`` folder.
    data_collection_name : str | None
        Name of the data collection, used to pick the matching form.
    language, country, city : str | None
        Components of the legacy file name.
    lab_number, year : int | str | None
        Components of the legacy file name.

    Returns
    -------
    Path | None
        The metadata form path, or None if no form could be found unambiguously.
    """
    candidates = sorted(
        set(_ci_glob(documentation_dir, "metadataForm_*.json"))
        | set(_ci_glob(documentation_dir, "metadataform_*.json"))
    )

    if data_collection_name:
        expected_stem = f"metadataform_{data_collection_name}".casefold()
        matching = [
            path
            for path in candidates
            if _metadata_form_stem(path).casefold() == expected_stem
        ]
        if matching:
            return matching[0]

    if len(candidates) == 1:
        return candidates[0]

    legacy_path = legacy_metadata_form_path(
        documentation_dir, language, country, city, lab_number, year
    )
    if legacy_path is not None:
        resolved = _ci_resolve(legacy_path)
        if resolved.exists():
            return resolved
    return None


def _parse_metadata_form(text: str, strict: bool) -> dict:
    """Parse metadata-form JSON and require a top-level object."""
    data = json.loads(text, strict=strict)
    if not isinstance(data, dict):
        raise ValueError(  # noqa: TRY004
            f"Metadata form must contain a JSON object at the top level, "
            f"got {type(data).__name__}."
        )
    return data


def _strip_trailing_commas(text: str) -> str:
    """
    Remove trailing commas before ``]`` or ``}``, ignoring string contents.

    The scan tracks JSON string state and escapes, so commas inside string
    values (for example ``"a,}b"``) are never altered.

    Parameters
    ----------
    text : str
        Raw JSON-ish text.

    Returns
    -------
    str
        The text with only structural trailing commas removed.
    """
    result: list[str] = []
    in_string = False
    escaped = False
    index = 0
    length = len(text)

    while index < length:
        char = text[index]

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == ",":
            lookahead = index + 1
            while lookahead < length and text[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead < length and text[lookahead] in "]}":
                index += 1
                continue

        result.append(char)
        index += 1

    return "".join(result)


def load_metadata_form(path: Path) -> dict:
    """
    Load a metadata form JSON file tolerantly.

    Real uploads are not always strict JSON: they may contain raw control
    characters (for example newlines inside strings) or trailing commas. This
    function tries strict JSON first, then lenient JSON that allows raw control
    characters, and finally removes structural trailing commas (ignoring string
    contents) before ``]``/``}`` and retries.

    Parameters
    ----------
    path : Path
        Path to the metadata form JSON file.

    Returns
    -------
    dict
        The parsed metadata form.

    Raises
    ------
    ValueError
        If the file cannot be parsed as a JSON object even after the tolerant
        attempts, or if it does not contain an object at the top level.
    """
    text = path.read_text(encoding="utf-8-sig")

    try:
        return _parse_metadata_form(text, strict=True)
    except json.JSONDecodeError:
        pass
    except ValueError as exc:
        raise ValueError(f"Invalid metadata form '{path}': {exc}") from exc

    try:
        return _parse_metadata_form(text, strict=False)
    except json.JSONDecodeError:
        pass
    except ValueError as exc:
        raise ValueError(f"Invalid metadata form '{path}': {exc}") from exc

    relaxed = _strip_trailing_commas(text)
    try:
        return _parse_metadata_form(relaxed, strict=False)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Could not parse metadata form '{path}': {exc}. "
            "The file is not valid JSON, even after tolerating raw control "
            "characters and trailing commas. Please fix the metadata form and "
            "re-run the preprocessing."
        ) from exc
    except ValueError as exc:
        raise ValueError(f"Invalid metadata form '{path}': {exc}") from exc


def find_psychometric_config_files(
    config_folder: Path,
    data_folder: Path,
    is_restructured: bool,
) -> list[Path]:
    """
    Locate the participant configuration YAML files for psychometric tests.

    In the restructured (session-first) layout, each session folder contains its own
    ``<sid>.yaml`` configuration, so configs are discovered inside ``data_folder``
    (i.e. ``data_folder/<session>/*.yaml``). For the task-first layout, configs live
    directly in ``config_folder``. If the restructured layout yields no config files,
    falls back to the legacy ``config_folder`` location.

    Parameters
    ----------
    config_folder : Path
        The legacy folder containing configuration files (.yaml).
    data_folder : Path
        The folder containing the session (or task) data.
    is_restructured : bool
        Whether the data is in the session-first (restructured) layout.

    Returns
    -------
    list[Path]
        The discovered config file paths, sorted by name.
    """
    if is_restructured and data_folder.exists():
        session_configs = sorted(
            config_file
            for session_folder in data_folder.iterdir()
            if session_folder.is_dir()
            for config_file in session_folder.glob("*.yaml")
        )
        if session_configs:
            return session_configs
    return sorted(config_folder.glob("*.yaml"))


def _resolve_raw_participant_folder(
    data_folder: Path, folder_name: str, name: str, config_sid: Sid | None
) -> Path:
    """Resolve a participant's raw (task-first) data folder, exact then soft match.

    Mirrors the restructure step so validation reports what the restructure would
    actually move. Falls back to the exact spelling when no match is found, which
    produces the standard MISSING DATA warning.
    """
    test_type_dir = data_folder / folder_name
    exact = test_type_dir / name
    if exact.exists():
        return exact
    if config_sid and test_type_dir.exists():
        for candidate in test_type_dir.iterdir():
            if candidate.is_dir():
                try:
                    if config_sid.equals_soft(Sid(candidate.name)):
                        return candidate
                except (ValueError, TypeError):
                    continue
    return exact


def validate_psychometric_data(
    config_folder: Path,
    data_folder: Path,
    is_restructured: bool = False,
) -> dict[str, list[str]]:
    """
    Validates psychometric data against participant configuration YAMLs.

    This function checks if the expected data folders exist based on the configuration flags
    in the participant YAML files. It logs warnings for missing or unexpected data.

    Parameters
    ----------
    config_folder : Path
        The folder containing configuration files (.yaml) for the psychometric tests.
    data_folder : Path
        The folder containing test data. If is_restructured is True, this should be
        the folder with per-participant subdirectories.
    is_restructured : bool
        Whether the data is already restructured into per-participant folders.

    Returns
    -------
    dict[str, list[str]]
        A dictionary mapping participant IDs to a list of identified issues.
    """
    from .logging import get_logger

    logger = get_logger()

    issues = {}

    # Find config files
    config_files = find_psychometric_config_files(
        config_folder, data_folder, is_restructured
    )
    if not config_files:
        logger.warning(f"No configuration files ('*.yaml') found in {config_folder}.")
        return issues

    for config_file in config_files:
        config_sid_str = config_file.stem
        participant_issues = []

        try:
            config_sid = Sid(config_sid_str)
        except (ValueError, TypeError):
            msg = f"Configuration file name is not SID-compliant: {config_file.name}."
            logger.warning(f"{msg} Attempting to process anyway.")
            participant_issues.append(msg)
            config_sid = None

        with open(config_file) as f:
            try:
                config_data = yaml.safe_load(f) or {}
            except yaml.YAMLError as exc:
                msg = f"Error reading configuration file {config_file}: {exc}"
                logger.error(msg)
                participant_issues.append(msg)
                issues[config_sid_str] = participant_issues
                continue

        # Find matching data folder
        matched_folder_name = config_sid_str
        if config_sid and is_restructured:
            # Try to find a folder that soft-matches the config SID
            actual_folders = [p.name for p in data_folder.iterdir() if p.is_dir()]
            for folder_name in actual_folders:
                try:
                    folder_sid = Sid(folder_name)
                    if config_sid.equals_soft(folder_sid):
                        matched_folder_name = folder_name
                        break
                except (ValueError, TypeError):
                    continue

        for yaml_flag, folder_name in settings.PSYCHOMETRIC_TEST_MAPPING.items():
            expected = config_data.get(yaml_flag, False)

            if is_restructured:
                test_path = data_folder / matched_folder_name / folder_name
            else:
                test_path = _resolve_raw_participant_folder(
                    data_folder, folder_name, config_sid_str, config_sid
                )

            if expected is True:
                if not test_path.exists():
                    msg = (
                        f"!!! MISSING DATA !!!: Participant {config_sid_str} is marked for {folder_name} "
                        f"in participant configuration ({config_file.name}), "
                        f"but the data folder does not exist at: {test_path}. "
                        "Please check the experimenter session documentation for any noteworthy points. "
                        "Note that if psychometric tests were restarted, the participant YAML configuration "
                        "might have been overwritten."
                    )
                    logger.warning(msg)
                    participant_issues.append(msg)
            else:
                if test_path.exists():
                    msg = (
                        f"Participant {config_sid_str} has data for {folder_name}, "
                        f"but it is marked as False (or missing) in participant config ({config_file.name})."
                    )
                    if not is_restructured:
                        msg += " Copying anyway."
                    logger.warning(msg)
                    participant_issues.append(msg)

        if participant_issues:
            issues[config_sid_str] = participant_issues

    return issues


def check_data_collection_exists(data_collection_name: str, data_root: Path) -> Path:
    """
    Checks if the data collection folder exists and contains meaningful data.

    Parameters
    ----------
    data_collection_name : str
        The name of the data collection subdirectory.
    data_root : Path
        The root directory where the data collection should be located.

    Returns
    -------
    Path
        The absolute path to the data collection folder.

    Raises
    ------
    FileNotFoundError
        If the folder does not exist or if it contains no meaningful files
        (excluding logs and hidden files).
    """
    data_folder_path = data_root / data_collection_name

    if not data_folder_path.exists():
        raise FileNotFoundError(
            f"The data collection folder '{data_collection_name}' was not found in '{data_root}'.\n"
            f"Please check if 'data_collection_name' is correctly set in the config file "
            "and that the folder exists and is unzipped."
        )

    # Check if the folder is essentially empty or only contains log files
    contents = list(data_folder_path.glob("*"))
    # Filter out log files and hidden files
    meaningful_contents = [
        c
        for c in contents
        if c.name != "preprocessing_logs.txt" and not c.name.startswith(".")
    ]

    if not meaningful_contents:
        raise FileNotFoundError(
            f"The data collection folder '{data_collection_name}' exists but appears to be empty "
            "(or only contains log files).\n"
            "Please ensure the data collection is correctly unzipped and structured."
        )

    return data_folder_path
