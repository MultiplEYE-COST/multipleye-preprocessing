import os
import re
import subprocess
import warnings
from abc import ABCMeta
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yaml

from preprocessing import settings
from preprocessing.data_collection.experimenter_doc import ExperimenterDoc
from preprocessing.data_collection.multipleye_data_collection import (
    _compute_session_completeness,
)
from preprocessing.data_collection.session import Session
from preprocessing.data_collection.stimulus import LabConfig
from preprocessing.metadata.codebook import load_codebook_identity
from preprocessing.metadata.language_tree import language_node_overview
from preprocessing.utils import get_logger, logging
from preprocessing.utils.data_path_utils import _ci_resolve, load_metadata_form
from preprocessing.utils.eye_tracker import (
    CANONICAL_EYE_TRACKERS,
    eye_tracker_brand,
    normalize_eye_tracker_name,
    suggest_eye_tracker_names,
)
from preprocessing.utils.logging import get_pipeline_info


class DataCollection(metaclass=ABCMeta):
    def __init__(
        self,
        data_collection_name: str,
        stimulus_language: str,
        country: str,
        year: int,
        eye_tracker: str,
        config_file: Path,
        stimulus_dir: Path,
        lab_number: int,
        city: str,
        data_root: Path,
        lab_configuration: LabConfig,
        session_folder_regex: str,
        experimenter_doc: ExperimenterDoc | None = None,
        included_sessions: list[str] | None = None,
        excluded_sessions: list[str] | None = None,
        **kwargs,
    ):
        self.sessions: dict[str, Session] = {}
        self.skipped_sessions: dict[str, Session] = {}
        self.experimenter_doc = experimenter_doc
        self.preflight_errors: dict[str, list[str]] = {}
        self.preflight_warnings: dict[str, list[str]] = {}
        # TODO: in theory this can be multiple languages for the stimuli..
        self.language = stimulus_language
        self.country = country
        self.year = year
        self.data_collection_name = data_collection_name

        self.include_pilots = kwargs.get("include_pilots", False)
        self.output_dir = kwargs.get("output_dir", "")
        self.pilot_folder = kwargs.get("pilot_folder", "")
        self.reports_folder = "reports"

        canonical_eye_tracker = normalize_eye_tracker_name(eye_tracker)
        if canonical_eye_tracker is None:
            suggestions = suggest_eye_tracker_names(eye_tracker)
            supported = ", ".join(CANONICAL_EYE_TRACKERS)
            message = (
                f"Eye tracker {eye_tracker!r} is not supported. "
                f"Supported models are: {supported}."
            )
            if suggestions:
                message += f" Did you mean: {', '.join(suggestions)}?"
            raise ValueError(message)

        self.eye_tracker_name_raw = str(eye_tracker)
        self.eye_tracker_name = canonical_eye_tracker
        self.eye_tracker = eye_tracker_brand(canonical_eye_tracker)
        self.config_file = config_file
        self.stimulus_dir = stimulus_dir
        self.lab_number = lab_number
        self.city = city
        self.lab_configuration = lab_configuration
        self.data_root = data_root
        self.session_folder_regex = session_folder_regex
        self.psychometric_tests = kwargs.get("psychometric_tests", [])
        self.excluded_sessions = excluded_sessions
        self.included_sessions = included_sessions
        self.pid_stimulus_dirs = kwargs.get("pid_stimulus_dirs", None)
        self.logger = get_logger()

        # MultipleyeDataCollection/MeridDataCollection hardcode the number of
        # ET sessions per participant as a class attribute (1 and 2
        # respectively). A generic data collection has no such hardcoded
        # value, so it is read from the metadata form instead.
        if not hasattr(type(self), "num_sessions"):
            administrative_form = self._load_metadata_form().get("administrative") or {}
            self.num_sessions = (
                administrative_form.get("number_of_et_sessions_per_participant", 1) or 1
            )

        self.logger.info(
            f"MultipleyeDataCollection initialized. data_root: {self.data_root}"
        )
        self.logger.info(f"Main config loaded from {self.config_file}")

        self.add_recorded_sessions(self.data_root, self.session_folder_regex)

        if len(self.sessions) == 0 and len(self.skipped_sessions) == 0:
            msg = f"No sessions found in {self.data_root}. "
            if self.included_sessions:
                msg += (
                    f"Check if 'include_sessions' {self.included_sessions} is correct. "
                )
            if self.excluded_sessions:
                msg += (
                    f"Check if 'exclude_sessions' {self.excluded_sessions} "
                    "is filtering all available data. "
                )

            msg += "Please check the session_folder_regex and the data_root."
            raise ValueError(msg)

        # load stimulus order versions to know what stimulus randomization was used for
        # each participant
        stim_order_versions = _ci_resolve(
            self.stimulus_dir / "config" / f"stimulus_order_versions_"
            f"{self.language}_{self.country}_{self.lab_number}.csv"
        )
        stim_order_versions = pd.read_csv(stim_order_versions)
        self.stim_order_versions = stim_order_versions

        if self.stim_order_versions.empty:
            warnings.warn(
                "Stimulus order version is not updated with participants numbers.\n"
                "Please ask the team to upload the correct stimulus folder that "
                "has been used and changed during the experiment.\n"
                "Version will be extracted from the asc files."
            )
            self.stim_order_versions = stim_order_versions

        self.overview = self.create_dataset_overview()

    @classmethod
    def create_from_data_folder(cls) -> "DataCollection":
        """
        Should work with the new general data folder structure analogous to the multipleye one.
        :return:
        """

    def add_recorded_sessions(
        self,
        data_root: Path,
        session_folder_regex: str = "",
        session_file_suffix: str = "",
    ) -> None:
        """
        Checks what sessions there exist for this data collection and adds them to the sessions dict. No preprocessing or anything happends in here.
        :param data_root: Specifies the root folder where the data is stored
        :param session_folder_regex: The pattern for the session folder names. It is possible to include infomration in
        regex groups. Those will be parsed directly and stored in the session object.
        Those folders should be in the root folder. If '' then the root folder is assumed to contain all files
        from the sessions.
        :param session_file_suffix: The pattern for the session file names. If no pattern is given, all files in the
        session folder are assumed to be the data files depending on the eye tracker.
        """

        self.data_root = data_root
        self.session_folder_regex = session_folder_regex

        found_sessions = []

        if not session_file_suffix and self.eye_tracker == "eyelink":
            # TODO: add configs for each eye tracker such that we don't always have to loop through all eye trackers
            #  but can write generic code. E.g. self.eye_tracker.session_file_regex
            session_file_suffix = r".edf"

        # get a list of all folders in the data folder
        if session_folder_regex:
            items = list(os.scandir(self.data_root))
            pilots = []
            if self.include_pilots:
                pilots = list(os.scandir(self.data_root / self.pilot_folder))
                items = items + pilots

            for item in items:
                if item.is_dir():
                    if re.match(session_folder_regex, item.name, re.IGNORECASE):
                        found_sessions.append(item.name)
                        # Determine if the session should be included based on filters
                        keep = True
                        if self.included_sessions:
                            keep = item.name in self.included_sessions
                        elif self.excluded_sessions:
                            keep = item.name not in self.excluded_sessions

                        if keep:
                            is_pilot = self.include_pilots and (item in pilots)
                            session_file = list(
                                Path(item.path).glob("*" + session_file_suffix)
                            )

                            if len(session_file) == 0:
                                self.logger.warning(
                                    f"No EDF file found for {item.name}, only parsing comprehension answers."
                                )
                                self.skipped_sessions[item.name] = Session(
                                    participant_id=int(item.name.split("_")[0]),
                                    session_identifier=item.name,
                                    session_folder_path=Path(item.path),
                                    session_file_path="unknown",
                                    session_file_name="unknown",
                                    is_pilot=is_pilot,
                                    tested_language=getattr(self, "language", None)
                                    or "unknown",
                                )
                                continue

                            elif len(session_file) > 1:
                                raise ValueError(
                                    f"More than one file found in folder {item.name} that match the pattern "
                                    f"{session_file_suffix}. Please specify a more specific pattern and check "
                                    f"your data."
                                )
                            else:
                                session_file = session_file[0]

                            # When a core and pilot session share the same identifier,
                            # keep the core one (added first) and skip the pilot duplicate.
                            if is_pilot and item.name in self.sessions:
                                self.logger.warning(
                                    f"Skipping pilot session '{item.name}' — "
                                    f"a core session with the same identifier already exists."
                                )
                                continue

                            ses = Session(
                                participant_id=int(item.name.split("_")[0]),
                                session_identifier=item.name,
                                session_folder_path=Path(item.path),
                                session_file_path=session_file,
                                session_file_name=session_file.name,
                                is_pilot=is_pilot,
                                tested_language=getattr(self, "language", None)
                                or "unknown",
                            )

                            self.sessions[item.name] = ses

                    else:
                        if item.name not in settings.IGNORED_SESSION_FOLDERS:
                            self.logger.warning(
                                f"Folder in eye-tracking-sessions '{item.name}' does not match the eye-tracking session regex pattern "
                                f"{session_folder_regex}. Not considered an eye-tracking session."
                            )

        if not found_sessions:
            raise ValueError(
                f"No sessions found (or none matching the ex-/inclusion criteria) in data folder {self.data_root}"
            )

        unique_sessions = set(found_sessions)

        if len(unique_sessions) != len(found_sessions):
            # Duplicate names (e.g. pilot + core sharing the same identifier).
            # Keep the first occurrence (core) and skip pilot duplicates.
            seen = set()
            deduped = []
            skipped = []
            for name in found_sessions:
                if name not in seen:
                    seen.add(name)
                    deduped.append(name)
                else:
                    skipped.append(name)
            found_sessions[:] = deduped
            self.logger.warning(
                f"Removed duplicate session identifiers: {', '.join(skipped)}. "
                "Pilot sessions with the same name as core sessions were skipped. "
                "Check your pilot_sessions folder to resolve naming conflicts."
            )

        if self.included_sessions:
            missing_included = set(self.included_sessions) - unique_sessions
            if missing_included:
                self.logger.warning(
                    f"The following sessions were specified in 'include_sessions' but "
                    f"were not found in the data folder: {sorted(missing_included)}"
                )

        if self.excluded_sessions:
            missing_excluded = set(self.excluded_sessions) - unique_sessions
            if missing_excluded:
                self.logger.warning(
                    f"The following sessions were specified in 'exclude_sessions' but "
                    f"were not found in the data folder: {sorted(missing_excluded)}"
                )

    def create_dataset_overview(self, path: str | Path = "") -> dict:
        """
        Create an overview of the dataset and save it as a yaml file in the top data folder.
        :return: overview dict
        """

        if not path:
            overview_path = (
                self.data_root.parent / f"{self.data_collection_name}_overview.yaml"
            )

        else:
            overview_path = path / f"{self.data_collection_name}_overview.yaml"

        num_sessions = len(
            [
                session
                for session in self.sessions
                if not self.sessions[session].is_pilot
            ]
        )
        num_pilots = len(
            [session for session in self.sessions if self.sessions[session].is_pilot]
        )

        session_completeness = _compute_session_completeness(self)

        metadata_form = self._load_metadata_form()
        metadata_form_exists = bool(metadata_form)

        administrative_form = metadata_form.get("administrative") or {}
        language_form = metadata_form.get("language_details") or {}
        technical_form = metadata_form.get("technical_setup") or {}

        institution = administrative_form.get("institution")
        contact_name = administrative_form.get("contact_name")
        contact_email = administrative_form.get("contact_email")
        estimated_end_year = administrative_form.get("estimated_end_year")
        dataset_description = administrative_form.get("dataset_description")

        script_direction = language_form.get("script_direction")
        if script_direction:
            script_direction = script_direction.lower()
        language_script = language_form.get("language_script")
        language_family = language_form.get("language_family")
        start_date = language_form.get("start_date_of_data_collection")
        end_date = language_form.get("end_date_of_data_collection")

        eye_tracker_manufacturer = technical_form.get("eye_tracker_manufacturer")
        camera_system = technical_form.get("camera_system")
        operating_system = technical_form.get("operating_system")
        monitor_resolution = technical_form.get("monitor_resolution")
        monitor_name = technical_form.get("monitor_name")

        def _lab_pair(attr: str) -> tuple[object, object]:
            value = getattr(self.lab_configuration, attr, None)
            if isinstance(value, (tuple, list)) and len(value) == 2:
                return value[0], value[1]
            return None, None

        screen_res_w, screen_res_h = _lab_pair("screen_resolution")
        screen_size_w, screen_size_h = _lab_pair("screen_size_cm")
        image_res_w, image_res_h = _lab_pair("image_resolution")
        image_size_w, image_size_h = _lab_pair("image_size_cm")
        screen_distance_cm = getattr(self.lab_configuration, "screen_distance_cm", None)
        codebook_info = load_codebook_identity()

        overview = {
            "administrative": {
                "title": self.data_collection_name,
                "dataset_type": self.type,
                "dataset_description": dataset_description,
                "number_of_sessions": num_sessions,
                "number_of_pilots": num_pilots,
                "number_of_et_sessions_per_participant": self.num_sessions,
                "session_completeness": session_completeness,
                "city": self.city,
                "lab_number": self.lab_number,
                "country": self.country,
                "tested_language": self.language,
                "institution": institution,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "script_direction": script_direction,
                "estimated_end_year": estimated_end_year,
            },
            "language_details": {
                "metadata_form_exists": metadata_form_exists,
                "language_script": language_script,
                "language_family": language_family,
                "start_date_of_data_collection": start_date,
                "end_date_of_data_collection": end_date,
            },
            "data_availability": {
                "raw_data_available": True,
                "fixations_available": True,
                "saccades_available": True,
                "reading_measures_available": True,
            },
            "psychometric_tests": {
                "tests_available": getattr(
                    self.lab_configuration, "psychometric_tests", None
                ),
            },
            "technical_setup": {
                "eye_tracker_name_raw": self.eye_tracker_name_raw,
                "eye_tracker_name": self.eye_tracker_name,
                "eye_tracker_manufacturer": eye_tracker_manufacturer,
                "sampling_frequency_hz": getattr(
                    self.lab_configuration, "sampling_frequency_hz", None
                ),
                "camera_system": camera_system,
                "operating_system": operating_system,
                "monitor_name": monitor_name,
                "monitor_resolution": monitor_resolution,
                "screen_resolution_width_px": screen_res_w,
                "screen_resolution_height_px": screen_res_h,
                "screen_size_width_cm": screen_size_w,
                "screen_size_height_cm": screen_size_h,
                "screen_distance_cm": screen_distance_cm,
                "image_resolution_width_px": image_res_w,
                "image_resolution_height_px": image_res_h,
                "image_size_width_cm": image_size_w,
                "image_size_height_cm": image_size_h,
            },
            "processing": {
                "preprocessing_date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
                "pipeline_version": self._get_pipeline_version(),
                "number_of_stimulus_versions": len(
                    self.stim_order_versions["version_number"].unique()
                )
                if hasattr(self, "stim_order_versions")
                and len(self.stim_order_versions) > 0
                else 0,
                # Flags from metadata_form.json
                "required_pq_fixing": metadata_form.get("Required_pq_fixing"),
                "psychotests_restructuring": metadata_form.get(
                    "Psychotests_restructuring"
                ),
                "custom_units_of_analysis": metadata_form.get(
                    "Custom_units_of_analysis"
                ),
                "answer_option_shuffling": self._compute_answer_option_shuffling(),
            },
            "processing_environment": self._get_processing_environment(),
            "processing_config": {
                "fixation_method": settings.FIXATION_METHOD,
                "fixation_minimum_duration_ms": settings.FIXATION_MINIMUM_DURATION_MS,
                "fixation_velocity_threshold": settings.FIXATION_VELOCITY_THRESHOLD,
                "saccade_method": settings.SACCADE_METHOD,
                "saccade_minimum_duration": settings.SACCADE_MINIMUM_DURATION,
                "saccade_threshold_factor": settings.SACCADE_THRESHOLD_FACTOR,
                "velocity_estimation_method": settings.VELOCITY_ESTIMATION_METHOD,
                "velocity_smoothing_window_ms": settings.VELOCITY_SMOOTHING_WINDOW_MS,
                "velocity_polynomial_degree": settings.VELOCITY_POLYNOMIAL_DEGREE,
                "psym_wikivocab_min_rt": settings.PSYM_WIKIVOCAB_MIN_RT,
                "psym_wikivocab_max_rt": settings.PSYM_WIKIVOCAB_MAX_RT,
                "psym_stroop_min_rt": settings.PSYM_STROOP_MIN_RT,
                "psym_stroop_max_rt": settings.PSYM_STROOP_MAX_RT,
                "psym_flanker_min_rt": settings.PSYM_FLANKER_MIN_RT,
                "psym_flanker_max_rt": settings.PSYM_FLANKER_MAX_RT,
                "tracked_eye": settings.TRACKED_EYE,
                "trial_cols": settings.TRIAL_COLS,
                "trial_col": settings.TRIAL_COL,
                "page_col": settings.PAGE_COL,
                "stimulus_col": settings.STIMULUS_COL,
                "word_idx_col": settings.WORD_IDX_COL,
                "char_idx_col": settings.CHAR_IDX_COL,
                "fixation_correction": settings.RUN_FIXATION_CORRECTION,
                "fixation_correction_algorithm": settings.FIXATION_CORRECTION_ALGORITHM,
                "fixation_correction_kwargs": settings.FIXATION_CORRECTION_KWARGS,
                "aoi_enlargement": "half_line_spacing"
                if getattr(self, "enlarge_aois", False)
                else "none",
                "reading_measures_null_fill": 0,
                "scanpath_drop_unmapped": True,
                "data_loss_missingness_column": "pixel",
                "per_trial_loss_weighting": "equal",
            },
            "data_quality": {
                "attrition_rate": self._compute_attrition_rate(),
                **self._compute_dcn_averages(),
            },
            "codebook": {
                "version": codebook_info.get("codebook_version"),
                "credit": codebook_info.get("credit"),
                "hash": codebook_info.get("hash"),
            },
        }

        # Add the configured language node. Kept separate from the ISO language,
        # country and session identifier fields.
        language_node = language_node_overview(
            settings.LANGUAGE_NODE_ID,
            settings.LANGUAGE_TREE_PATH,
            settings.LANGUAGE_TREE_VERSION,
            settings.LANGUAGE_NODE_LABEL,
            settings.LANGUAGE_TREE_HASH,
        )
        if language_node:
            overview["language_node"] = language_node

        # Add warnings to overview
        if hasattr(logging, "_captured_warnings") and logging._captured_warnings:
            overview["warnings"] = list(set(logging._captured_warnings))

        with open(overview_path, "w", encoding="utf8") as f:
            yaml.dump(overview, f, sort_keys=False)

        return overview

    @staticmethod
    def _get_pipeline_version() -> str | None:
        """
        Return the installed pipeline version, or None if it cannot be determined.

        Returns
        -------
        str | None
            Version string from package metadata, or None on failure.
        """
        try:
            version, _ = get_pipeline_info()
            return version
        except (ImportError, KeyError, subprocess.SubprocessError):
            return None

    def _load_metadata_form(self) -> dict:
        """
        Load the final metadata form YAML for this data collection, if present.

        The file must be named "metadata_form.yaml" and be located in the "documentation"
        folder next to the data collection root.
        An empty mapping is returned when no single file can be matched.

        Returns
        -------
        dict
            Parsed metadata form contents, or an empty dict if the file is
            missing or cannot be matched unambiguously.
        """
        documentation_dir = self.data_root.parent / "documentation"
        metadata_path = documentation_dir / "metadata_form.yaml"
        if not metadata_path.exists():
            return {}
        return load_metadata_form(metadata_path)

    def _load_lab_config_form(self) -> dict:
        """
        Load the lab configuration YAML for this data collection, if present.

        The lab configuration file must be named "lab_config.yaml" and be located in the "documentation"
        folder next to the data collection root.
        An empty mapping is returned when no single file can be matched.

        Returns
        -------
        dict
            Parsed lab configuration, or an empty dict.
        """
        documentation_dir = self.data_root.parent / "documentation"
        config_path = documentation_dir / "lab_config.yaml"

        if not config_path.exists():
            return {}
        return load_metadata_form(config_path)
