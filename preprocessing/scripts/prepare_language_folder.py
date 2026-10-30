import argparse
import hashlib
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from ..models.dcn import Dcn
from ..scripts.restructure_psychometric_tests import fix_psychometric_tests_structure
from ..utils.data_path_utils import check_data_collection_exists
from ..utils.file_utils import _copytree, _to_win_long_path
from ..utils.fix_multipleye_aoi_files import (
    fix_aoi_file,
)
from ..utils.logging import get_logger
from ..utils.stimulus_versions import (
    configured_version_suffixes,
    default_version_suffix,
    stimulus_folder_name,
    version_suffix_for_pid,
)

logger = get_logger()

_ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".7z", ".rar")


def _find_named_archives(directory: Path, name: str) -> list[Path]:
    """Return archives in ``directory`` whose name starts with ``name``."""
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name.startswith(name)
        and path.name.endswith(_ARCHIVE_SUFFIXES)
    )


def _session_is_selected(session_name: str) -> bool:
    """Return whether a session passes the configured include/exclude filters."""
    from preprocessing import settings

    include = settings.INCLUDE_SESSIONS or []
    exclude = settings.EXCLUDE_SESSIONS or []
    if include and session_name not in include:
        return False
    return session_name not in exclude


def _iter_selected_session_folders(
    eye_tracking_sessions_dir: Path,
) -> Iterator[Path]:
    """Yield session folders that pass the configured session filters.

    Respects ``INCLUDE_SESSIONS``, ``EXCLUDE_SESSIONS``,
    ``IGNORED_SESSION_FOLDERS`` and ``INCLUDE_PILOTS`` so that excluded sessions
    do not influence which stimulus versions are copied.
    """
    from preprocessing import settings

    ignored = set(settings.IGNORED_SESSION_FOLDERS or [])
    for session_folder in eye_tracking_sessions_dir.glob("*"):
        if not session_folder.is_dir():
            continue
        if session_folder.name in ignored:
            continue
        if _session_is_selected(session_folder.name):
            yield session_folder

    pilot_dir = eye_tracking_sessions_dir / "pilot_sessions"
    if settings.INCLUDE_PILOTS and pilot_dir.exists():
        for session_folder in pilot_dir.glob("*"):
            if session_folder.is_dir() and _session_is_selected(session_folder.name):
                yield session_folder


def _get_used_version_folder_suffixes(
    eye_tracking_sessions_dir: Path,
) -> list[str | None]:
    """Return the stimulus content version suffixes used by selected sessions.

    The default folder (``STIMULUS_VERSIONS_DEFAULT_VERSION``, ``None`` for the
    suffix-less folder) is always included because it holds the shared lab
    configuration. Versioned folders are only included when at least one selected
    session is mapped to them, so unused stimulus folders are not copied.
    """
    used: set[str | None] = {default_version_suffix()}
    for session_folder in _iter_selected_session_folders(eye_tracking_sessions_dir):
        pid = session_folder.name.split("_")[0]
        used.add(version_suffix_for_pid(pid))

    return [suffix for suffix in configured_version_suffixes() if suffix in used]


def prepare_language_folder(data_collection_name: str | None = None):
    from preprocessing import settings

    if data_collection_name is None:
        data_collection_name = settings.DATA_COLLECTION_NAME

    if data_collection_name is None:
        raise ValueError(
            "data_collection_name is None. Please provide a valid data collection name "
            "as an argument or load a configuration via settings.load()."
        )

    dcn = Dcn(data_collection_name)

    logger = get_logger(__name__)

    # Check if the data collection folder exists
    data_folder_path = check_data_collection_exists(
        data_collection_name, settings.THIS_REPO / "data"
    )

    # The 'eye-tracking-sessions' folder must be unpacked in the cleaning step.
    eye_tracking_sessions_path = data_folder_path / "eye-tracking-sessions"
    if not eye_tracking_sessions_path.exists():
        msg = (
            f"The 'eye-tracking-sessions' folder does not exist in '{data_folder_path}'. "
            "Please ensure the data collection is correctly structured and unpack any "
            "archives in the cleaning step."
        )
        archives = _find_named_archives(data_folder_path, "eye-tracking-sessions")
        if archives:
            msg += (
                " Found archive(s) with the same name: "
                + ", ".join(a.name for a in archives)
                + ". Unpack them in the cleaning step."
            )
        raise FileNotFoundError(msg)

    # Nested core session folders must be flattened in the cleaning step; the
    # pipeline expects session folders directly under 'eye-tracking-sessions'.
    for nested_name in ("core_sessions", "core_dataset"):
        if (eye_tracking_sessions_path / nested_name).exists():
            logger.warning(
                f"Found nested folder '{nested_name}' in 'eye-tracking-sessions'. "
                "Move its session folders up into 'eye-tracking-sessions' in the "
                "cleaning step before running the pipeline."
            )

    psychometric_tests_path = data_folder_path / "psychometric-tests-sessions"
    if not psychometric_tests_path.exists():
        msg = (
            f"The 'psychometric-tests-sessions' folder does not exist in '{data_folder_path}'. "
            "If this data collection includes psychometric tests, create the folder and unpack "
            "the data in the cleaning step.\n"
            "Expected structure after unpacking (task-first):\n"
            f"  psychometric-tests-sessions/\n"
            f"    psychometric_test_{dcn.lang}_{dcn.country}_{dcn.lab}/\n"
            "      PLAB/{sid}/...\n"
            "      RAN/{sid}/...\n"
            "      Stroop_Flanker/{sid}/...\n"
            "      WMC/{sid}/...\n"
            "      WikiVocab/{sid}/...\n"
            f"    participant_configs_{dcn.lang}_{dcn.country}_{dcn.lab}/\n"
            "      {sid}.yaml\n"
            "Skipping psychometric tests preparation."
        )
        archives = _find_named_archives(data_folder_path, "psychometric-tests")
        if archives:
            msg += (
                "\nFound archive(s) with the same name: "
                + ", ".join(a.name for a in archives)
                + ". Unpack them in the cleaning step."
            )
        logger.warning(msg)
        psychometric_tests_path = None

    # check if ps tests need to be prepared because they use the old structure
    if psychometric_tests_path is not None:
        config_path = (
            psychometric_tests_path
            / f"participant_configs_{dcn.lang}_{dcn.country}_{dcn.lab}"
        )
        data_path = (
            psychometric_tests_path
            / f"psychometric_test_{dcn.lang}_{dcn.country}_{dcn.lab}"
        )
        if config_path.exists() and data_path.exists():
            logger.info(
                f"Preparing psychometric tests structure for {data_collection_name}..."
            )
            fix_psychometric_tests_structure(config_path, data_path)

    # Session archives are unpacked in the cleaning step (see the cleaning
    # template), not here. Warn if they are still present so the missing
    # sessions do not fail silently.
    pilot_folder = eye_tracking_sessions_path / "pilot_sessions"
    leftover_archives = list(eye_tracking_sessions_path.glob("*.zip"))
    if pilot_folder.exists():
        leftover_archives += list(pilot_folder.glob("*.zip"))
    if leftover_archives:
        logger.warning(
            "Found unzipped session archives in 'eye-tracking-sessions': "
            + ", ".join(sorted(p.name for p in leftover_archives))
            + ". Unpack them in the cleaning step before running the pipeline."
        )

    for version_suffix in _get_used_version_folder_suffixes(eye_tracking_sessions_path):
        folder_name = stimulus_folder_name(data_collection_name, version_suffix)

        stimulus_folder_path = data_folder_path / folder_name

        preprocessed_stimulus_path = settings.OUTPUT_DIR / folder_name

        if not stimulus_folder_path.exists():
            logger.warning(
                f"The stimulus folder {folder_name} does not exist. Check and if necessary, ask team to upload."
            )
            continue
        else:
            config_path = stimulus_folder_path / "config"
            if not config_path.exists():
                raise FileNotFoundError(
                    f"The stimulus config folder not found in '{stimulus_folder_path}'. "
                    "Please check and restructure or possibly unzip the stimulus folder."
                )

        # if aoi files are not yet split into questions and texts, do it here:
        source_aoi_path = (
            stimulus_folder_path
            / f"aoi_stimuli_{dcn.lang.lower()}_{dcn.country.lower()}_{dcn.lab}"
        )

        destination_aoi_path = (
            preprocessed_stimulus_path
            / f"aoi_stimuli_{dcn.lang.lower()}_{dcn.country.lower()}_{dcn.lab}"
        )

        # Check if stimulus assets have changed since last copy
        checksum_path = preprocessed_stimulus_path / ".copy_checksum"
        source_checksum = _compute_stimulus_checksum(stimulus_folder_path)
        stored = checksum_path.read_text().strip() if checksum_path.exists() else None

        if source_checksum == stored:
            logger.info(f"Stimulus assets for {folder_name} unchanged. Skipping copy.")
        else:
            if stored is not None:
                logger.warning(
                    "Stimulus assets have changed and are being recopied. Note that some outputs may be based on a previous stimuli version. "
                    "To recalculate everything based on the new stimuli version please activate the 'Recalculate' flag in the settings."
                )
                shutil.rmtree(str(preprocessed_stimulus_path))
            _copy_stimulus_assets(
                stimulus_folder_path,
                preprocessed_stimulus_path,
                dcn,
            )
            checksum_path.write_text(source_checksum)

        # Always ensure the question-image versions used by the selected sessions
        # are present, even when the bulk copy was skipped by the checksum. The
        # set of used versions can change with the session selection.
        _copy_used_question_images(
            stimulus_folder_path,
            preprocessed_stimulus_path,
            eye_tracking_sessions_path,
            dcn,
        )

        if (  # check if it already contains 24 files and the fixed marker
            destination_aoi_path.exists()
            and len(list(destination_aoi_path.glob("[!.]*.csv"))) == 24
            and (destination_aoi_path / ".fixed").exists()
        ):
            logger.debug(
                f"AOI files already exist, are split and fixed in {destination_aoi_path}. Skipping."
            )
            continue

        if not destination_aoi_path.exists():
            if source_aoi_path.exists():
                logger.debug(f"Copying AOI files to {destination_aoi_path}...")
                _copytree(source_aoi_path, destination_aoi_path)
            else:
                logger.warning(f"Source AOI path {source_aoi_path} does not exist.")
                continue

        # get all aoi files in the preprocessed folder
        aoi_files = list(destination_aoi_path.glob("[!.]*.csv"))
        if len(aoi_files) == 12:
            logger.info("Splitting AOI files into text and question AOIs...")
            for aoi_file in aoi_files:
                aoi_df = pd.read_csv(aoi_file)
                # split the aoi_df into two parts, one for the stimulus and one for the questions
                aoi_df_texts = aoi_df[
                    ~aoi_df["page"].str.contains("question", na=False)
                ]
                aoi_df_texts.drop(
                    columns=["question_image_version"], inplace=True, errors="ignore"
                )
                aoi_df_questions = aoi_df[
                    aoi_df["page"].str.contains("question", na=False)
                ]

                aoi_df_texts.to_csv(aoi_file, sep=",", index=False, encoding="UTF-8")

                question_path = destination_aoi_path / (
                    aoi_file.stem + "_questions" + aoi_file.suffix
                )
                aoi_df_questions.to_csv(
                    question_path, sep=",", index=False, encoding="UTF-8"
                )

            # Re-get files to include the new _questions files
            aoi_files = list(destination_aoi_path.glob("*.csv"))

        if len(aoi_files) == 24:
            logger.info("Applying AOI fixes (remapping space and repairing labels)...")
            for aoi_file in aoi_files:
                fix_aoi_file(aoi_file)

            # Create a marker file to indicate that these files have been fixed
            (destination_aoi_path / ".fixed").touch()
        elif len(aoi_files) == 0:
            logger.warning(f"No AOI files found in '{destination_aoi_path}'.")
        else:
            raise ValueError(
                f"Unexpected number of AOI files ({len(aoi_files)}) found in '{destination_aoi_path}'. "
                "Expected 12 (not split) or 24 (already split into texts and questions)."
            )


def _copy_stimulus_assets(
    source_stimulus_dir: Path,
    dest_stimulus_dir: Path,
    dcn: Dcn,
) -> None:
    from preprocessing import settings

    logger.info(f"Copying stimulus assets to {dest_stimulus_dir}...")
    dest_stimulus_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"{dcn.lang.lower()}_{dcn.country.lower()}_{dcn.lab}"

    # 1. Copy Stimuli Images (all)
    stimuli_images_folder = f"stimuli_images_{suffix}"
    source_img = source_stimulus_dir / stimuli_images_folder
    dest_img = dest_stimulus_dir / stimuli_images_folder
    if source_img.exists() and not dest_img.exists():
        logger.debug(f"Copying {stimuli_images_folder}...")
        _copytree(source_img, dest_img)

    # 2. Copy Participant Instruction Images (all)
    instr_images_folder = f"participant_instructions_images_{suffix}"
    source_instr = source_stimulus_dir / instr_images_folder
    dest_instr = dest_stimulus_dir / instr_images_folder
    if source_instr.exists() and not dest_instr.exists():
        logger.debug(f"Copying {instr_images_folder}...")
        _copytree(source_instr, dest_instr)

    logger.debug("Copying remaining stimulus assets...")

    # 3. Copy AOI Stimuli Images Overlay (optional)
    if settings.COPY_AOI_IMAGES_OVERLAY:
        aoi_img_folder = f"aoi_stimuli_images_{suffix}"
        source_aoi_img = source_stimulus_dir / aoi_img_folder
        dest_aoi_img = dest_stimulus_dir / aoi_img_folder
        if source_aoi_img.exists() and not dest_aoi_img.exists():
            logger.debug(f"Copying {aoi_img_folder}...")
            _copytree(source_aoi_img, dest_aoi_img)

    # 4. Copy Config folder (includes stimulus order versions)
    source_config = source_stimulus_dir / "config"
    dest_config = dest_stimulus_dir / "config"
    if source_config.exists() and not dest_config.exists():
        logger.debug("Copying config folder...")
        _copytree(source_config, dest_config)

    # 5. Copy Excel files needed for loading
    for pattern in ["[!.]*.xlsx", "[!.]*.xls", "[!.]*.csv"]:
        for file in source_stimulus_dir.glob(pattern):
            dest_file = dest_stimulus_dir / file.name
            if not dest_file.exists():
                shutil.copy2(
                    _to_win_long_path(file) if os.name == "nt" else file,
                    _to_win_long_path(dest_file) if os.name == "nt" else dest_file,
                )

    # 6. Copy Custom units of analysis, if applicable
    uoa_folder = "custom_units_of_analysis"
    uoa_dir = source_stimulus_dir / uoa_folder
    dest_uoa = dest_stimulus_dir / "custom_units_of_analysis"
    if uoa_dir.exists():
        if not dest_uoa.exists():
            os.mkdir(dest_uoa)
        for file in uoa_dir.glob("*.csv"):
            dest_file = dest_uoa / file.name
            if not dest_file.exists():
                shutil.copy2(
                    _to_win_long_path(file) if os.name == "nt" else file,
                    _to_win_long_path(dest_file) if os.name == "nt" else dest_file,
                )





def _copy_used_question_images(
    source_stimulus_dir: Path,
    dest_stimulus_dir: Path,
    eye_tracking_sessions_dir: Path,
    dcn: Dcn,
) -> None:
    """Copy the question-image versions used by the selected sessions.

    Runs on every preparation, independent of the source ``.copy_checksum``,
    because the set of used order versions can change with the session selection
    (``include_sessions`` / ``exclude_sessions`` / ``include_pilots``) even when
    the source stimuli are unchanged. Existing version folders are skipped.
    """
    from preprocessing import settings

    suffix = f"{dcn.lang.lower()}_{dcn.country.lower()}_{dcn.lab}"
    used_versions = _get_used_stimulus_versions(eye_tracking_sessions_dir)
    logger.debug(f"Identified used stimulus versions: {used_versions}")

    dest_stimulus_dir.mkdir(parents=True, exist_ok=True)
    _copy_used_version_folders(
        source_stimulus_dir / f"question_images_{suffix}",
        dest_stimulus_dir / f"question_images_{suffix}",
        used_versions,
    )

    if settings.COPY_AOI_IMAGES_OVERLAY:
        _copy_used_version_folders(
            source_stimulus_dir / f"aoi_question_images_{suffix}",
            dest_stimulus_dir / f"aoi_question_images_{suffix}",
            used_versions,
        )


def _copy_used_version_folders(
    source_base: Path,
    dest_base: Path,
    used_versions: set[int],
) -> None:
    """Copy the ``question_images_version_<n>`` folders that are actually used.

    The stimulus package ships version folders for all randomisation versions;
    only the ones used by the sessions are copied to the output.
    """
    if not source_base.exists():
        return

    dest_base.mkdir(parents=True, exist_ok=True)
    for version in sorted(used_versions):
        version_folder = f"question_images_version_{version}"
        source_version = source_base / version_folder
        dest_version = dest_base / version_folder
        if source_version.exists() and not dest_version.exists():
            logger.info(f"Copying {version_folder}...")
            _copytree(source_version, dest_version)


def _get_used_stimulus_versions(eye_tracking_sessions_dir: Path) -> set[int]:
    """Return the stimulus order versions used by the selected sessions.

    Only sessions that pass the configured include/exclude/pilot filters are
    considered, so excluded sessions do not cause extra question images to be
    copied.
    """
    used_versions: set[int] = set()
    for session_folder in _iter_selected_session_folders(eye_tracking_sessions_dir):
        _extract_from_session(session_folder, used_versions)

    return used_versions


def _extract_from_session(session_folder: Path, used_versions: set[int]) -> None:
    # Prefer the session logfile: the stimulus order version is available there on
    # the first run, whereas a raw ASC is only produced later (and with
    # `edf2asc -p` it is never written next to the .edf at all).
    version = _extract_version_from_logfile(session_folder)
    if version is None:
        version = _extract_version_from_asc(session_folder)
    if version is None:
        version = _extract_version_from_output_asc(session_folder)
    if version is not None:
        used_versions.add(version)


def _extract_version_from_logfile(session_folder: Path) -> int | None:
    from preprocessing import settings

    for logfile in sorted((session_folder / "logfiles").glob("GENERAL_LOGFILE_*.txt")):
        match = settings.LOGFILE_ORDER_VERSION_REGEX.search(
            logfile.read_text(encoding="utf-8")
        )
        if match:
            return int(match.group("order_version"))
    return None


def _extract_version_from_asc(session_folder: Path) -> int | None:
    for asc_file in session_folder.glob("[!.]*.asc"):
        version = extract_stimulus_version_number_from_asc(asc_file)
        if version != -1:
            return version
    return None


def _extract_version_from_output_asc(session_folder: Path) -> int | None:
    from preprocessing import settings

    session_id = session_folder.name
    output_asc = (
        settings.OUTPUT_DIR / settings.ASC_FOLDER / session_id / f"{session_id}.asc"
    )
    if not output_asc.exists():
        return None
    version = extract_stimulus_version_number_from_asc(output_asc)
    return version if version != -1 else None


def extract_stimulus_version_number_from_asc(asc_file_path: Path) -> int:
    from preprocessing import settings

    pattern = settings.STIMULUS_ORDER_VERSION_REGEX

    with open(asc_file_path) as asc_file:
        for line in asc_file:
            if match := re.match(pattern, line):
                return int(match.group("version_num"))

        return -1


def _compute_stimulus_checksum(source_dir: Path) -> str:
    entries = []
    for f in sorted(source_dir.rglob("*")):
        if f.is_file():
            entries.append(f"{f.relative_to(source_dir)}:{f.stat().st_size}")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run multipleye preprocessing on an experiment file"
    )

    parser.add_argument(
        "data_collection_name",
        type=str,
        help='Name of the folder containing the data collection. E.g. "MultiplEYE_ET_EE_Tartu_1_2022". '
        'The folder should be located in the "data" directory of this repository.',
    )

    return parser.parse_args()


def main():
    args = parse_args()

    logger.info(f"Preparing language folder for {args.data_collection_name}...")

    prepare_language_folder(args.data_collection_name)
