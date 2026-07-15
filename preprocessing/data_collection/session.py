from dataclasses import dataclass, field, asdict
from pathlib import Path

import polars as pl

from ..data_collection.stimulus import Stimulus, LabConfig
from ..data_collection.trial import Trial
from ..models import Sid
from ..config import settings


@dataclass
class Session:
    # general info
    participant_id: int

    session_identifier: str
    is_pilot: bool

    # paths and files
    session_folder_path: Path
    session_file_path: Path
    session_file_name: str
    asc_path: Path = field(default="unknown", init=False)

    # stimuli
    # TODO: move stimuli, completed stimuli, stimuli trial mapping to one thing
    stimuli: list[Stimulus] = field(default="unknown", init=False)
    randomization_version: int = field(default="unknown", init=False)
    stimulus_folder_name: str = field(default="unknown", init=False)
    completed_stimuli_ids: list[int] = field(default="unknown", init=False)
    completed_stimuli_names: list[str] = field(default="unknown", init=False)
    question_order: dict[str, list[str]] = field(default="unknown", init=False)
    stimulus_order_ids: list[int] = field(default="unknown", init=False)
    messages: list[dict[str, str]] = field(default="unknown", init=False)
    stimuli_trial_mapping: dict[str, str] = field(default="unknown", init=False)
    stimulus_start_end_ts: dict[str, list[str]] = field(default="unknown", init=False)

    logfile: str = field(default="unknown", init=False)
    interrupted: bool = field(default="unknown", init=False)
    lab_config: LabConfig = field(default="unknown", init=False)

    # stats
    total_reading_time: float = field(default="unknown", init=False)
    total_session_duration: float = field(default="unknown", init=False)
    obligatory_break_made: bool = field(default="unknown", init=False)
    num_optional_breaks_made: int = field(default="unknown", init=False)
    total_break_time: float = field(default="unknown", init=False)

    # calibrations & validations
    calibrations: pl.DataFrame = field(default="unknown", init=False)
    validations: pl.DataFrame = field(default="unknown", init=False)
    avg_comprehension_score: float = field(default="unknown", init=False)
    avg_calibration_error: float = field(default="unknown", init=False)
    num_calibrations: int = field(default="unknown", init=False)
    num_validations: int = field(default="unknown", init=False)
    avg_validation_error: float = field(default="unknown", init=False)

    # eye tracking metadata
    tracked_eye: str = field(default="unknown", init=False)
    tracked_eye_consistent: bool = field(default=True, init=False)
    num_good_validations: int = field(default=0, init=False)
    num_moderate_validations: int = field(default=0, init=False)
    num_bad_validations: int = field(default=0, init=False)

    # completed trials
    num_completed_trials: int = field(default=0, init=False)

    # sanity report
    sanity_report_path: Path = field(default="unknown", init=False)

    # preprocessing pm
    pm_gaze_path: Path = field(default="unknown", init=False)
    pm_gaze_metadata: dict = field(default="unknown", init=False)

    # psychometric tests
    psychometric_tests_session: str = field(default="unknown", init=False)

    # data formats
    raw_data: bool = field(default=False, init=False)
    fixations: bool = field(default=False, init=False)
    saccades: bool = field(default=False, init=False)
    reading_measures: bool = field(default=False, init=False)
    answers: bool = field(default=False, init=False)

    trials = list[Trial]

    @property
    def sid(self) -> "Sid":
        return Sid(self.session_identifier)

    def create_overview(self):
        self._create_stats()

        dict_repr = {
            "participant_id": self.participant_id,
            "session_identifier": self.session_identifier,
            "is_pilot": self.is_pilot,
            "question_order": self.question_order,
            "stimulus_order_ids": self.stimulus_order_ids,
            "was_session_interrupted": self.interrupted,
            "lab_config": asdict(self.lab_config)
            if isinstance(self.lab_config, LabConfig)
            else self.lab_config,
            "total_reading_time": self.total_reading_time,
            "total_session_duration": self.total_session_duration,
            "obligatory_break_made": self.obligatory_break_made,
            "num_optional_breaks_made": self.num_optional_breaks_made,
            "total_break_time": self.total_break_time,
            "avg_comprehension_score": self.avg_comprehension_score,
            "avg_calibration_error": self.avg_calibration_error,
            "num_calibrations": self.num_calibrations,
            "num_validations": self.num_validations,
            "avg_validation_error": self.avg_validation_error,
            "data_loss_ratio": self.pm_gaze_metadata["data_loss_ratio"],
            "measure_data_loss_ratio": getattr(
                self,
                "_measure_data_loss_ratio",
                None,
            ),
            "measure_data_loss_ratio_blinks": getattr(
                self,
                "_measure_data_loss_ratio_blinks",
                None,
            ),
            "Mount_configuration": self.pm_gaze_metadata["mount_configuration"],
            "Pupil_data_type": self.pm_gaze_metadata["pupil_data_type"],
            "tracked_eye": self.tracked_eye,
            "tracked_eye_consistent": self.tracked_eye_consistent,
            "num_good_validations": self.num_good_validations,
            "num_moderate_validations": self.num_moderate_validations,
            "num_bad_validations": self.num_bad_validations,
            "num_completed_trials": len(self.stimulus_order_ids)
            if isinstance(self.stimulus_order_ids, list)
            else None,
            "Raw_data": self.raw_data,
            "Fixations": self.fixations,
            "Saccades": self.saccades,
            "Reading_measures": self.reading_measures,
            "Answers": self.answers,
        }

        return dict_repr

    def _create_stats(self):
        self.num_calibrations = len(self.calibrations)
        self.num_validations = len(self.validations)

        self.tracked_eye = self.pm_gaze_metadata.get("tracked_eye", "unknown")

        if not isinstance(self.validations, str) and not self.validations.is_empty():
            scores = self.validations["accuracy_avg"].to_list()
            eyes = self.validations["eye"].to_list()
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
