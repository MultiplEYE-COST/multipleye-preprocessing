from dataclasses import asdict, dataclass, field
from pathlib import Path
from pprint import pformat
from typing import TypeVar

import polars as pl
import yaml

from ..config import settings
from ..data_collection.stimulus import LabConfig, Stimulus
from ..data_collection.trial import Trial
from ..models import Sid
from ..utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class Session:
    # general info
    participant_id: int
    language: str
    country: str
    city: str
    lab_number: int
    session_identifier: str
    is_pilot: bool
    month_of_data_collection: str = field(default="unknown", init=True)
    year_of_data_collection: str = field(default="unknown", init=True)

    # paths and files
    session_folder_path_unprocessed: Path = field(default="not available", init=True)
    session_file_path_unprocessed: Path = field(default="not available", init=True)
    asc_path: Path = field(default="unknown", init=True)
    dataset_dir: Path = field(default="unknown", init=True)

    # stimuli
    # TODO: move stimuli, completed stimuli, stimuli trial mapping to one thing?
    stimuli: list[Stimulus] | str = field(default="unknown", init=True)
    randomization_version: int | str = field(default="unknown", init=True)
    stimulus_folder_name: str = field(default="unknown", init=True)
    completed_stimuli_ids: list[int] | str = field(default="unknown", init=True)
    completed_stimuli_names: list[str] | str = field(default="unknown", init=True)
    question_order: dict[str, list[str]] | str = field(default="unknown", init=True)
    stimulus_order_ids: list[int] | str = field(default="unknown", init=True)
    messages: pl.DataFrame | list[dict[str, str]] | str = field(
        default="unknown", init=True
    )
    uncategorized_messages: list[dict[str, str]] | str = field(
        default="unknown", init=True
    )
    stimulus_trial_mapping: dict[str, str] | str = field(default="unknown", init=True)
    stimulus_start_end_ts: list[dict[str, str | float]] | str = field(
        default="unknown", init=True
    )

    logfile: str = field(default="unknown", init=True)
    lab_config: LabConfig | str = field(default="unknown", init=True)

    # stats
    total_reading_time_s: float | str = field(default="unknown", init=True)
    total_session_duration_s: float | str = field(default="unknown", init=True)
    obligatory_break_made: bool | str = field(default="unknown", init=True)
    num_optional_breaks_made: int | str = field(default="unknown", init=True)
    total_break_time_s: float | str = field(default="unknown", init=True)

    # calibrations & validations
    calibrations: pl.DataFrame | str = field(default="unknown", init=True)
    validations: pl.DataFrame | str = field(default="unknown", init=True)
    avg_comprehension_score: float | str = field(default="unknown", init=True)
    avg_comprehension_score_local: float | str = field(default="unknown", init=True)
    avg_comprehension_score_global: float | str = field(default="unknown", init=True)
    avg_comprehension_score_bridging: float | str = field(default="unknown", init=True)
    avg_calibration_error: float | str = field(default="unknown", init=True)
    num_calibrations: int | str = field(default="unknown", init=True)
    num_validations: int | str = field(default="unknown", init=True)
    avg_validation_error: float | str = field(default="unknown", init=True)

    # eye tracking metadata
    tracked_eye: str = field(default="unknown", init=True)
    tracked_eye_consistent: bool = field(default=True, init=True)
    num_good_validations: int = field(default=0, init=True)
    num_moderate_validations: int = field(default=0, init=True)
    num_bad_validations: int = field(default=0, init=True)

    # completed trials
    num_completed_trials: int = field(default=0, init=True)
    was_session_interrupted: bool = field(default="unknown", init=True)

    # data quality & sanity report
    sanity_report_path: Path | str = field(default="unknown", init=True)
    session_blink_loss_ratio: float | str = field(default=None, init=True)
    session_total_data_loss_ratio: float | str = field(default=None, init=True)

    # preprocessing pm
    pm_gaze_path: Path | str = field(default="unknown", init=True)
    # parsed from pm metadata
    # recording details eyelink (if the eyelink settings are wrong, these will be too!)
    recording_start_time_eyelink_hh_mm_ss: str = field(default="unknown", init=True)
    recording_day_eyelink: str = field(default="unknown", init=True)
    recording_month_eyelink: str = field(default="unknown", init=True)
    recording_year_eyelink: str = field(default="unknown", init=True)
    pupil_data_type: str = field(default="unknown", init=True)
    total_recording_duration_ms: float = field(default="unknown", init=True)
    mount_type: str = field(default=None, init=True)
    head_stabilization: str = field(default=None, init=True)
    eyes_recorded: str = field(default=None, init=True)

    # psychometric tests
    psychometric_tests_session: str = field(default="unknown", init=True)

    # data formats
    # True by default: our pipeline produces all formats. Other pipelines may
    # set these to False when a format is not generated.
    raw_data: bool = field(default=True, init=True)
    fixations: bool = field(default=True, init=True)
    saccades: bool = field(default=True, init=True)
    reading_measures: bool = field(default=True, init=True)
    answers: bool = field(default=True, init=True)

    # per-trial metrics
    trials: list[Trial] | str = field(default="unknown", init=True)

    def __str__(self) -> str:
        return pformat(self.create_overview(), indent=4)

    @property
    def sid(self) -> "Sid":
        return Sid(self.session_identifier)

    def create_overview(self):
        """
        Create a topic-grouped overview of the session.

        Returns
        -------
        dict
            Overview with sections: administrative, technical_setup, tracking,
            calibration_validation, data_quality, experiment_procedure,
            comprehension, and data_formats.
        """
        self._create_stats()

        return {
            "administrative": {
                "participant_id": self.participant_id,
                "session_identifier": self.session_identifier,
                "is_pilot": self.is_pilot,
                # TODO: needs to be changed to be parsed from the logfile
                "year_of_data_collection": self.recording_year_eyelink,
                "month_of_data_collection": self.recording_month_eyelink,
                "language": self.language,
                "country": self.country,
                "city": self.city,
                "lab_number": self.lab_number,
            },
            "technical_setup": self._technical_setup(),
            "tracking": {
                "tracked_eye": self.tracked_eye,
                "tracked_eye_consistent": self.tracked_eye_consistent,
            },
            "calibration_validation": {
                "num_calibrations": self.num_calibrations,
                "num_validations": self.num_validations,
                "avg_calibration_error_dva": self.avg_calibration_error,
                "avg_validation_error_dva": self.avg_validation_error,
                "num_good_validations": self.num_good_validations,
                "num_moderate_validations": self.num_moderate_validations,
                "num_bad_validations": self.num_bad_validations,
            },
            "data_quality": {
                "session_total_data_loss_ratio": getattr(
                    self,
                    "_measure_total_data_loss_ratio",
                    None,
                ),
                "session_blink_loss_ratio": getattr(
                    self,
                    "_measure_blink_loss_ratio",
                    None,
                ),
            },
            "experiment_procedure": {
                "question_order": self.question_order,
                "stimulus_order_ids": self.stimulus_order_ids,
                "completed_stimuli_ids": self.completed_stimuli_ids,
                "num_completed_trials": len(self.stimulus_order_ids)
                if isinstance(self.stimulus_order_ids, list)
                else None,
                "was_session_interrupted": self.was_session_interrupted,
                "obligatory_break_made": self.obligatory_break_made,
                "num_optional_breaks_made": self.num_optional_breaks_made,
                "total_break_time_s": self.total_break_time_s,
                "total_reading_time_s": self.total_reading_time,
                "total_session_duration_s": self.total_session_duration_s,
                "randomization_version": self.randomization_version,
            },
            "Stimuli": {
                "stimulus_folder_name": self.stimulus_folder_name,
                "stimulus_trial_mapping": self.stimulus_trial_mapping,
            },
            "trials": (
                [asdict(t) for t in self.trials]
                if isinstance(self.trials, list)
                else self.trials
            ),
            "comprehension": {
                "avg_comprehension_score": self.avg_comprehension_score,
                "avg_comprehension_score_local": self.avg_comprehension_score_local,
                "avg_comprehension_score_global": self.avg_comprehension_score_global,
                "avg_comprehension_score_bridging": self.avg_comprehension_score_bridging,
            },
            "data_formats": {
                "raw_data": self.raw_data,
                "fixations": self.fixations,
                "saccades": self.saccades,
                "reading_measures": self.reading_measures,
                "answers": self.answers,
            },
        }

    @classmethod
    def from_yaml(cls, yaml_file: Path, dataset_dir: Path) -> "Session":
        with open(yaml_file, "r", encoding="utf8") as f:
            session_specs = yaml.safe_load(f)

        # Flatten nested overview sections while remaining compatible with already-flat files.
        flat_overview = {}

        for key, value in session_specs.items():
            if key == "Trials":
                trials = value
            elif isinstance(value, dict):
                if key == "Technical_setup":
                    tech_setup = value
                else:
                    flat_overview.update(value)
            else:
                flat_overview[key] = value

        # parse technical setup into lab config
        lab_config = LabConfig(
            screen_resolution=(
                tech_setup["screen_resolution_width_px"],
                tech_setup["screen_resolution_height_px"],
            ),
            screen_size_cm=(
                tech_setup["screen_size_width_cm"],
                tech_setup["screen_size_height_cm"],
            ),
            screen_distance_cm=tech_setup["screen_distance_cm"],
            image_resolution=(
                tech_setup["image_resolution_width_px"],
                tech_setup["image_resolution_height_px"],
            ),
            image_size_cm=(
                tech_setup["image_size_width_cm"],
                tech_setup["image_size_height_cm"],
            ),
            name_eye_tracker=tech_setup["eye_tracker_name"],
        )

        trials = [Trial(**data) for data in trials]

        flat_overview["mount_type"] = tech_setup["mount_type"]
        flat_overview["head_stabilization"] = tech_setup["head_stabilization"]
        flat_overview["eyes_recorded"] = tech_setup["eyes_recorded"]

        session = cls(
            **flat_overview,
            dataset_dir=Path(dataset_dir),
            lab_config=lab_config,
            trials=trials,
        )
        session.load_session_stimuli(
            Path(session.dataset_dir) / session.stimulus_folder_name
        )

        return session

    def load_session_stimuli(
        self,
        stimulus_dir: Path,
        stimulus_names: None | list = None,
    ) -> None:
        """
        Load the stimuli from the specified directory.
        :param stimulus_dir: The directory where the stimuli are stored.
        :param stimulus_names: The names of the stimuli to load.
        If None, the predefined stimuli names in the settings are used.
        """

        if self.stimulus_folder_name == "unknown":
            self.stimulus_folder_name = stimulus_dir.name

        stimuli = []
        if stimulus_names is None:
            stimulus_names = [
                name
                for name, num in settings.STIMULUS_NAME_MAPPING.items()
                if num in self.completed_stimuli_ids
            ]

        for stimulus_name in stimulus_names:
            trial_mapping = self.stimulus_trial_mapping
            # get the trial id from the mapping, keys are ids and values are strings
            trial_id = [
                key for key, value in trial_mapping.items() if value == stimulus_name
            ]
            if len(trial_id) == 0:
                raise KeyError(
                    f"Stimulus name {stimulus_name} not found in the trial mapping for session "
                    f"{self.session_identifier}. Please check the completed_stimuli.csv file."
                )

            stimulus = Stimulus.load(
                stimulus_dir,
                self.language,
                self.country,
                self.lab_number,
                stimulus_name,
                self.randomization_version,
                trial_id[0],
            )
            stimuli.append(stimulus)

        self.stimuli = stimuli

    def add_pm_metadata(self, metadata: dict) -> None:
        """Adds the metadata for a gaze object in pymovements to the session's metadata."""

        if isinstance(metadata, dict):
            self.recording_day_eyelink = metadata["day"]
            self.recording_month_eyelink = metadata["month"]
            self.recording_year_eyelink = metadata["year"]
            self.recording_start_time_eyelink_hh_mm_ss = metadata["time"]
            self.tracked_eye = metadata["tracked_eye"]
            self.pupil_data_type = metadata["pupil_data_type"]
            self.total_recording_duration_ms = float(
                metadata["total_recording_duration_ms"]
            )

            self.pm_blink_data_loss = metadata["data_loss_ratio_blinks"]
            self.pm_data_loss = metadata["data_loss_ratio"]

            if isinstance(metadata["mount_configuration"], dict):
                self.mount_type = metadata["mount_configuration"]["mount_type"]
                self.head_stabilization = metadata["mount_configuration"][
                    "head_stabilization"
                ]
                self.eyes_recorded = metadata["mount_configuration"]["eyes_recorded"]

    def get_pm_metadata(self) -> dict:

        metadata = {}

        metadata["day"] = self.recording_day_eyelink
        metadata["month"] = self.recording_month_eyelink
        metadata["year"] = self.recording_year_eyelink
        metadata["time"] = self.recording_start_time_eyelink_hh_mm_ss
        metadata["tracked_eye"] = self.tracked_eye
        metadata["total_recording_duration_ms"] = self.total_recording_duration_ms
        metadata["sampling_rate"] = self.lab_config.sampling_frequency_hz
        metadata["data_loss_ratio"] = self.pm_data_loss
        metadata["data_loss_ratio_blinks"] = self.pm_blink_data_loss

        return metadata

    def _technical_setup(self) -> dict:
        """Assemble the technical setup section from lab config and gaze metadata."""
        cfg = self.lab_config if isinstance(self.lab_config, LabConfig) else None

        def _resolve(attr: str, fallback: object = None) -> object:
            if cfg is not None:
                return getattr(cfg, attr, fallback)
            return fallback

        def _pair(tup: object) -> tuple[object, object]:
            if isinstance(tup, (tuple, list)) and len(tup) == 2:
                return tup[0], tup[1]
            return None, None

        screen_res_w, screen_res_h = _pair(_resolve("screen_resolution"))
        screen_size_w, screen_size_h = _pair(_resolve("screen_size_cm"))
        image_res_w, image_res_h = _pair(_resolve("image_resolution"))
        image_size_w, image_size_h = _pair(_resolve("image_size_cm"))

        return {
            "eye_tracker_name": _resolve("name_eye_tracker", None),
            "sampling_frequency_hz": _resolve("sampling_frequency_hz", None),
            "mount_type": self.mount_type,
            "head_stabilization": self.head_stabilization,
            "eyes_recorded": self.eyes_recorded,
            "pupil_data_type": self.pupil_data_type,
            "screen_resolution_width_px": screen_res_w,
            "screen_resolution_height_px": screen_res_h,
            "screen_size_width_cm": screen_size_w,
            "screen_size_height_cm": screen_size_h,
            "screen_distance_cm": _resolve("screen_distance_cm", None),
            "image_resolution_width_px": image_res_w,
            "image_resolution_height_px": image_res_h,
            "image_size_width_cm": image_size_w,
            "image_size_height_cm": image_size_h,
        }

    def _compute_comprehension_scores(self) -> None:
        """Load the session answers CSV and compute mean comprehension scores.

        Scores are computed over experiment trials only (practice trials are
        excluded). Type-specific scores use the condition_number column where
        1=local, 2=bridging, 3=global.
        """
        default = "unknown"
        self.avg_comprehension_score = default
        self.avg_comprehension_score_local = default
        self.avg_comprehension_score_global = default
        self.avg_comprehension_score_bridging = default

        answers_csv = self.sid.answers_dir / f"{self.sid}_answers.csv"
        if not answers_csv.exists():
            return

        try:
            answers = pl.read_csv(answers_csv)
        except Exception as exc:
            logger.warning(f"Could not read answers CSV {answers_csv}: {exc}")
            return

        if answers.is_empty() or "is_correct" not in answers.columns:
            return

        experiment = answers.filter(~pl.col("trial").str.starts_with("PRACTICE_"))
        if experiment.is_empty():
            return

        correct = [c for c in experiment["is_correct"].to_list() if c is not None]
        if correct:
            self.avg_comprehension_score = round(
                sum(1 for c in correct if c) / len(correct), 3
            )

        type_map = {1: "local", 2: "bridging", 3: "global"}
        if "condition_number" in experiment.columns:
            for condition, name in type_map.items():
                subset = [
                    c
                    for c in experiment.filter(pl.col("condition_number") == condition)[
                        "is_correct"
                    ].to_list()
                    if c is not None
                ]
                if subset:
                    setattr(
                        self,
                        f"avg_comprehension_score_{name}",
                        round(sum(1 for c in subset if c) / len(subset), 3),
                    )

    def _compute_session_duration(self) -> float | None:
        """Return session duration in seconds from message timestamps, if available."""
        if not isinstance(self.messages, pl.DataFrame) or self.messages.is_empty():
            return None
        if "time" not in self.messages.columns:
            return None
        times = self.messages["time"].cast(pl.Float64).drop_nulls().to_list()
        if not times:
            return None
        min_t = min(times)
        max_t = max(times)
        return round((max_t - min_t) / 1000, 3)

    def _create_stats(self):
        self.num_calibrations = len(self.calibrations)
        self.num_validations = len(self.validations)

        # Mean calibration and validation error (accuracy_avg column), if present.
        if (
            isinstance(self.validations, pl.DataFrame)
            and not self.validations.is_empty()
            and "accuracy_avg" in self.validations.columns
        ):
            vals = self.validations["accuracy_avg"].drop_nulls().to_list()
            if vals:
                self.avg_validation_error = round(sum(vals) / len(vals), 3)

        if (
            isinstance(self.calibrations, pl.DataFrame)
            and not self.calibrations.is_empty()
            and "accuracy_avg" in self.calibrations.columns
        ):
            vals = self.calibrations["accuracy_avg"].drop_nulls().to_list()
            if vals:
                self.avg_calibration_error = round(sum(vals) / len(vals), 3)

        if (
            not isinstance(self.validations, str)
            and not self.validations.is_empty()
            and {"accuracy_avg", "eye"}.issubset(self.validations.columns)
        ):
            scores = self.validations["accuracy_avg"].drop_nulls().to_list()
            eyes = self.validations["eye"].drop_nulls().to_list()
            self.num_good_validations = sum(
                1 for s in scores if s < settings.SINGLE_VALIDATION_GOOD_MAX
            )
            self.num_moderate_validations = sum(
                1
                for s in scores
                if settings.SINGLE_VALIDATION_GOOD_MAX
                <= s
                < settings.SINGLE_VALIDATION_MODERATE_MAX
            )
            self.num_bad_validations = sum(
                1 for s in scores if s >= settings.SINGLE_VALIDATION_MODERATE_MAX
            )

            non_standard = [
                e for e in eyes if e and e[0].lower() != self.tracked_eye.lower()
            ]
            self.tracked_eye_consistent = len(non_standard) == 0

        self._compute_comprehension_scores()

        self.trials = self._compute_trials()

        duration = self._compute_session_duration()
        if duration is not None:
            self.total_session_duration_s = duration

        if self.total_reading_time_s == "unknown":
            reading = self._compute_total_reading_time()
            if reading is not None:
                self.total_reading_time_s = reading

    def _compute_total_reading_time(self) -> float | None:
        """Return total reading time in seconds from stimulus start/end timestamps.

        The timestamps are stored on the session when reading times are
        documented (sanity checks). Falls back to None when unavailable.
        """
        if (
            not isinstance(self.stimulus_start_end_ts, list)
            or not self.stimulus_start_end_ts
        ):
            return None
        total_ms = 0.0
        for entry in self.stimulus_start_end_ts:
            try:
                start = float(entry["start_ts"])
                stop = float(entry["stop_ts"])
            except (KeyError, TypeError, ValueError):
                continue
            total_ms += stop - start
        if total_ms <= 0:
            return None
        return round(total_ms / 1000, 3)

    def _reading_time_by_trial(self) -> dict[str, float]:
        """Return total reading time in ms per trial from stimulus timestamps."""
        by_trial: dict[str, float] = {}
        if not isinstance(self.stimulus_start_end_ts, list):
            return by_trial
        for entry in self.stimulus_start_end_ts:
            try:
                start = float(entry["start_ts"])
                stop = float(entry["stop_ts"])
                trial = str(entry["trial"])
            except (KeyError, TypeError, ValueError):
                continue
            by_trial[trial] = by_trial.get(trial, 0.0) + (stop - start)
        return by_trial

    def _compute_trials(self) -> list[Trial] | str:
        """Assemble per-trial metrics from the answers CSV and reading times.

        Returns
        -------
        list[Trial] | str
            Per-trial metrics, or "unknown" when the answers CSV is missing.
        """
        answers_csv = self.sid.answers_dir / f"{self.sid}_answers.csv"
        if not answers_csv.exists():
            return "unknown"

        try:
            answers = pl.read_csv(answers_csv)
        except Exception as exc:
            logger.warning(f"Could not read answers CSV {answers_csv}: {exc}")
            return "unknown"

        required = {"trial", "stimulus", "stimulus_id", "is_correct"}
        if answers.is_empty() or not required.issubset(answers.columns):
            return "unknown"

        reading_by_trial = self._reading_time_by_trial()

        trials: list[Trial] = []
        for trial_id, group in answers.group_by("trial", maintain_order=True):
            trial_id = trial_id[0] if isinstance(trial_id, tuple) else trial_id
            correct = [c for c in group["is_correct"].to_list() if c is not None]
            if not correct:
                score = 0.0
            else:
                score = round(sum(1 for c in correct if c) / len(correct), 3)

            question_time = 0.0
            if "confirmation_rt_ms" in group.columns:
                q_times = [
                    float(t) for t in group["confirmation_rt_ms"].drop_nulls().to_list()
                ]
                question_time = round(sum(q_times), 3) if q_times else 0.0

            first = group.row(0, named=True)
            try:
                trial_number = int(str(trial_id).rsplit("_", 1)[-1])
            except ValueError:
                trial_number = 0

            if first["question_id"] == "session_interrupted":
                trials.append(
                    Trial(
                        trial_number=trial_number,
                        stimulus_id=None,
                        stimulus_name=None,
                        is_practice=str(trial_id).startswith("PRACTICE_"),
                        num_questions=None,
                        comprehension_score=None,
                        comprehension_question_time_ms=None,
                        reading_time_ms=None,
                        status="interrupted",
                    )
                )

            else:
                trials.append(
                    Trial(
                        trial_number=trial_number,
                        stimulus_id=int(first["stimulus_id"]),
                        stimulus_name=str(first["stimulus"]),
                        is_practice=str(trial_id).startswith("PRACTICE_"),
                        num_questions=group.height,
                        comprehension_score=score,
                        comprehension_question_time_ms=question_time,
                        reading_time_ms=round(
                            reading_by_trial.get(str(trial_id), 0.0), 3
                        ),
                        status="completed",
                    )
                )

        trials.sort(key=lambda t: (t.is_practice, t.trial_number))

        return trials
