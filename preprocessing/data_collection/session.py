from dataclasses import dataclass, field, asdict
from pathlib import Path

import polars as pl

from ..data_collection.stimulus import Stimulus, LabConfig
from ..data_collection.trial import Trial
from ..models import Sid


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
            "total_data_loss_ratio": getattr(
                self,
                "_measure_total_data_loss_ratio",
                None,
            ),
            "blink_loss_ratio": getattr(
                self,
                "_measure_blink_loss_ratio",
                None,
            ),
            "Mount_configuration": self.pm_gaze_metadata["mount_configuration"],
            "Pupil_data_type": self.pm_gaze_metadata["pupil_data_type"],
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
