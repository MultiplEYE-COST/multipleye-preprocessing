import re
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TypeVar

import polars as pl

from ..config import settings
from ..data_collection.stimulus import LabConfig, Stimulus
from ..data_collection.trial import Trial
from ..models import Sid
from ..utils.logging import get_logger
from .experimenter_doc import (
    ExperimenterDoc,
    normalize_dominant_eye,
    normalize_dominant_eye_test,
)

logger = get_logger()

T = TypeVar("T")

_CALIBRATION_QUALITY_REGEX = re.compile(
    r"!CAL\s+CALIBRATION\b.*?\b(GOOD|FAILED)\b",
    re.IGNORECASE,
)
_VALIDATION_QUALITY_REGEX = re.compile(
    r"!CAL\s+VALIDATION\s+"
    r"(?:HV\d+\s+\S+\s+(?:LEFT|RIGHT)|[LR])\s+"
    r"(?P<grade>GOOD|FAIR|POOR|ABORTED)\b",
    re.IGNORECASE,
)
_QUALITY_LINE_REGEX = re.compile(r"!CAL\s+(?:CALIBRATION|VALIDATION)", re.IGNORECASE)
_FINAL_VALIDATION_MSG_REGEX = re.compile(r"^\s*final_validation\s*$", re.IGNORECASE)
_CALIBRATION_MSG_REGEX = re.compile(r"!CAL\s+CALIBRATION\b", re.IGNORECASE)
_EXPERIMENT_TRIAL_REGEX = re.compile(r"^trial_\d+$")


def _parse_rating_option(key: object) -> int | None:
    """Return the integer rating from an ``option_<n>`` logfile key, else None."""
    if not isinstance(key, str) or not key.startswith("option_"):
        return None
    try:
        return int(key.split("_", 1)[1])
    except (ValueError, IndexError):
        return None


def _consensus(values: list[object], unknown: object) -> object:
    """Return the common value when all values agree, else *unknown*."""
    if not values:
        return unknown
    first = values[0]
    return first if all(value == first for value in values) else unknown


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
    asc_path: Path | str = field(default="unknown", init=False)

    # stimuli
    # TODO: move stimuli, completed stimuli, stimuli trial mapping to one thing
    stimuli: list[Stimulus] | str = field(default="unknown", init=False)
    randomization_version: int | str = field(default="unknown", init=False)
    stimulus_folder_name: str = field(default="unknown", init=False)
    completed_stimuli_ids: list[int] | str = field(default="unknown", init=False)
    completed_stimuli_names: list[str] | str = field(default="unknown", init=False)
    question_order: dict[str, list[str]] | str = field(default="unknown", init=False)
    stimulus_order_ids: list[int] | str = field(default="unknown", init=False)
    stimulus_order_ids_with_names: list[dict[str, object]] | str = field(
        default="unknown", init=False
    )
    messages: pl.DataFrame | list[dict[str, str]] | str = field(
        default="unknown", init=False
    )
    uncategorized_messages: list[dict[str, str]] | str = field(
        default="unknown", init=False
    )
    stimuli_trial_mapping: dict[str, str] | str = field(default="unknown", init=False)
    stimulus_content_version: str | None = field(default="unknown", init=False)
    stimulus_start_end_ts: list[dict[str, str | float]] | str = field(
        default="unknown", init=False
    )

    logfile: str = field(default="unknown", init=False)
    interrupted: bool | str = field(default="unknown", init=False)
    restarted_session_name: str = field(default="unknown", init=False)
    lab_config: LabConfig | str = field(default="unknown", init=False)

    # stats
    total_reading_time: float | str = field(default="unknown", init=False)
    mean_rt_per_stim_ms: float | str = field(default="unknown", init=False)
    sd_rt_per_stim_ms: float | str = field(default="unknown", init=False)
    total_question_time_ms: float | str = field(default="unknown", init=False)
    total_rating_time_ms: float | str = field(default="unknown", init=False)
    familiarity_1: float | str = field(default="unknown", init=False)
    familiarity_2: float | str = field(default="unknown", init=False)
    subjective_difficulty: float | str = field(default="unknown", init=False)
    total_session_duration: float | str = field(default="unknown", init=False)
    obligatory_break_made: bool | str = field(default="unknown", init=False)
    num_optional_breaks_made: int | str = field(default="unknown", init=False)
    total_break_time: float | str = field(default="unknown", init=False)

    # calibrations & validations
    calibrations: pl.DataFrame | str = field(default="unknown", init=False)
    validations: pl.DataFrame | str = field(default="unknown", init=False)
    avg_comprehension_score: float | str = field(default="unknown", init=False)
    avg_comprehension_score_local: float | str = field(default="unknown", init=False)
    avg_comprehension_score_global: float | str = field(default="unknown", init=False)
    avg_comprehension_score_bridging: float | str = field(default="unknown", init=False)
    avg_calibration_error: float | str = field(default="unknown", init=False)
    calibration_quality: str = field(default="unknown", init=False)
    validation_quality: str = field(default="unknown", init=False)
    num_aborted_validations: int = field(default=0, init=False)
    num_calibrations: int | str = field(default="unknown", init=False)
    num_validations: int | str = field(default="unknown", init=False)
    avg_validation_error: float | str = field(default="unknown", init=False)
    final_validation_score_dva: float | str = field(default="unknown", init=False)

    # eye tracking metadata
    tracked_eye: str = field(default="unknown", init=False)
    tracked_eye_consistent: bool = field(default=True, init=False)
    num_good_validations: int = field(default=0, init=False)
    num_moderate_validations: int = field(default=0, init=False)
    num_bad_validations: int = field(default=0, init=False)

    # completed trials
    num_completed_trials: int = field(default=0, init=False)

    # sanity report
    sanity_report_path: Path | str = field(default="unknown", init=False)

    # preprocessing pm
    pm_gaze_path: Path | str = field(default="unknown", init=False)
    pm_gaze_metadata: dict | str = field(default="unknown", init=False)

    # psychometric tests
    psychometric_tests_session: str = field(default="unknown", init=False)

    # participant info (from the participant questionnaire + psychometric sessions)
    participant_info: dict | str = field(default="unknown", init=False)

    # data formats
    # True by default: our pipeline produces all formats. Other pipelines may
    # set these to False when a format is not generated.
    raw_data: bool = field(default=True, init=False)
    fixations: bool = field(default=True, init=False)
    saccades: bool = field(default=True, init=False)
    reading_measures: bool = field(default=True, init=False)
    answers: bool = field(default=True, init=False)

    # per-trial metrics
    trials: list[Trial] | str = field(default="unknown", init=False)

    @property
    def sid(self) -> "Sid":
        return Sid(self.session_identifier)

    def create_overview(self, experimenter_doc: ExperimenterDoc | None = None) -> dict:
        """
        Create a topic-grouped overview of the session.

        Parameters
        ----------
        experimenter_doc : ExperimenterDoc, optional
            Experimenter documentation workbook. Used for the dominant-eye
            fields in ``technical_setup``. When omitted or missing, those
            fields are ``unknown``.

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
                "year_of_data_collection": self._get_metadata("year", "unknown"),
                "month_of_data_collection": self._get_metadata("month", "unknown"),
            },
            "participant": self.participant_info,
            "technical_setup": self._technical_setup(experimenter_doc),
            "tracking": {
                "tracked_eye": self.tracked_eye,
                "tracked_eye_consistent": self.tracked_eye_consistent,
            },
            "calibration_validation": {
                "num_calibrations": self.num_calibrations,
                "num_validations": self.num_validations,
                "avg_calibration_error_dva": self.avg_calibration_error,
                "avg_validation_error_dva": self.avg_validation_error,
                "final_validation_score_dva": self.final_validation_score_dva,
                "calibration_quality": self.calibration_quality,
                "validation_quality": self.validation_quality,
                "num_aborted_validations": self.num_aborted_validations,
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
                "stimulus_content_version": self.stimulus_content_version,
                "stimulus_order_ids": self.stimulus_order_ids,
                "stimulus_order_ids_with_names": self.stimulus_order_ids_with_names,
                "num_completed_trials": len(self.stimulus_order_ids)
                if isinstance(self.stimulus_order_ids, list)
                else None,
                "was_session_interrupted": self.interrupted,
                "restarted_session_name": self.restarted_session_name,
                "obligatory_break_made": self.obligatory_break_made,
                "num_optional_breaks_made": self.num_optional_breaks_made,
                "total_break_time_s": self.total_break_time,
                "total_reading_time_s": self.total_reading_time,
                "total_session_duration_s": self.total_session_duration,
                "mean_rt_per_stim_ms": self.mean_rt_per_stim_ms,
                "sd_rt_per_stim_ms": self.sd_rt_per_stim_ms,
                "total_question_time_ms": self.total_question_time_ms,
                "total_rating_time_ms": self.total_rating_time_ms,
                "familiarity_1": self.familiarity_1,
                "familiarity_2": self.familiarity_2,
                "subjective_difficulty": self.subjective_difficulty,
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

    def _get_metadata(self, key: str, default: T = "unknown") -> str | T:
        """Return a value from pm_gaze_metadata without raising on missing keys."""
        if isinstance(self.pm_gaze_metadata, dict):
            return self.pm_gaze_metadata.get(key, default)
        return default

    def _technical_setup(self, experimenter_doc: ExperimenterDoc | None = None) -> dict:
        """Assemble the technical setup section from lab config and gaze metadata."""
        cfg = self.lab_config if isinstance(self.lab_config, LabConfig) else None
        mount = self._get_metadata("mount_configuration", {})
        if not isinstance(mount, dict):
            mount = {}

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

        short_name = mount.get("short_name")
        if not isinstance(short_name, str) or not short_name.strip():
            short_name = None

        dominant_eye, dominant_eye_test = self._dominant_eye_from_doc(experimenter_doc)

        return {
            "eye_tracker_name": _resolve("name_eye_tracker", None),
            "sampling_frequency_hz": _resolve("sampling_frequency_hz", None),
            "mount_type": mount.get("mount_type"),
            "mount_short_name": short_name,
            "head_stabilization": mount.get("head_stabilization"),
            "eyes_recorded": mount.get("eyes_recorded"),
            "pupil_data_type": self._get_metadata("pupil_data_type"),
            "dominant_eye": dominant_eye,
            "dominant_eye_test": dominant_eye_test,
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

    def _dominant_eye_from_doc(
        self, experimenter_doc: ExperimenterDoc | None
    ) -> tuple[str, bool | str]:
        """Return ``(dominant_eye, dominant_eye_test)`` from the experimenter sheet.

        Missing sheets, columns, rows and values yield ``unknown``. Duplicate
        matching rows are never resolved silently: a warning is emitted, and a
        field is only used when all duplicate rows agree. ``dominant_eye`` is
        not inferred from ``tracked_eye`` and is forced to ``unknown`` when the
        sheet says that no dominance test was performed.
        """
        if not isinstance(experimenter_doc, ExperimenterDoc):
            return "unknown", "unknown"

        rows = experimenter_doc.get_et_rows(
            self.session_identifier, self.participant_id
        )
        if not rows:
            return "unknown", "unknown"

        eyes = [normalize_dominant_eye(row.get("dominant_eye")) for row in rows]
        tests = [
            normalize_dominant_eye_test(row.get("dominant_eye_test")) for row in rows
        ]

        if len(rows) > 1:
            warnings.warn(
                f"Experimenter documentation has {len(rows)} rows for session "
                f"{self.session_identifier}. Dominant-eye values are only used "
                "when duplicate rows agree.",
                UserWarning,
                stacklevel=2,
            )

        dominant_eye = _consensus(eyes, "unknown")
        dominant_eye_test = _consensus(tests, "unknown")
        if dominant_eye_test is False:
            dominant_eye = "unknown"
        return str(dominant_eye), dominant_eye_test

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

    def _quality_message_lines(self) -> list[str]:
        """Return lines carrying EyeLink calibration or validation grades.

        Prefer the already-parsed messages frame. Fall back to reading the ASC
        when the message filter did not include the ``!CAL`` lines, which is the
        case for older message CSVs and the default message patterns.
        """
        if isinstance(self.messages, pl.DataFrame) and not self.messages.is_empty():
            if "content" in self.messages.columns:
                lines = [
                    str(value)
                    for value in self.messages["content"].drop_nulls().to_list()
                ]
                if any(_QUALITY_LINE_REGEX.search(line) for line in lines):
                    return lines
        elif isinstance(self.messages, list):
            lines = [
                str(item.get("content", item.get("message", "")))
                for item in self.messages
                if isinstance(item, dict)
            ]
            if any(_QUALITY_LINE_REGEX.search(line) for line in lines):
                return lines

        path = self.asc_path
        if not isinstance(path, (str, Path)) or str(path) == "unknown":
            return []
        asc = Path(path)
        if not asc.exists():
            return []
        try:
            with open(asc, encoding="utf-8", errors="ignore") as f:
                return [line for line in f if "!CAL" in line]
        except OSError:
            return []

    def _compute_calibration_quality(self, lines: list[str] | None = None) -> str:
        """Return the calibration quality flag from the ASC messages or file.

        EyeLink reports calibration quality only as a ``GOOD``/``FAILED`` flag on
        the ``!CAL CALIBRATION ...`` line (there is no numeric calibration error;
        that is only reported for validations). Returns ``"GOOD"`` or
        ``"FAILED"`` when all calibrations agree, ``"MIXED"`` when they differ,
        and ``"unknown"`` when no calibration line or ASC file is available.
        """
        flags: list[str] = []
        for line in self._quality_message_lines() if lines is None else lines:
            match = _CALIBRATION_QUALITY_REGEX.search(line)
            if match:
                flags.append(match.group(1).upper())

        if not flags:
            return "unknown"
        if all(flag == "GOOD" for flag in flags):
            return "GOOD"
        if all(flag == "FAILED" for flag in flags):
            return "FAILED"
        return "MIXED"

    def _compute_validation_quality(
        self,
        lines: list[str] | None = None,
    ) -> tuple[str, int]:
        """Return the worst validation grade and the number of aborted validations.

        ``GOOD``/``FAIR``/``POOR`` come from the validation summary lines.
        ``ABORTED`` comes from the dedicated aborted-validation lines. The
        returned grade is the worst scored grade; it is ``ABORTED`` when only
        aborted validations exist and ``unknown`` when no validation line exists.
        """
        grades: list[str] = []
        for line in self._quality_message_lines() if lines is None else lines:
            match = _VALIDATION_QUALITY_REGEX.search(line)
            if match:
                grades.append(match.group("grade").upper())

        num_aborted = sum(1 for grade in grades if grade == "ABORTED")
        scored = [grade for grade in grades if grade in {"GOOD", "FAIR", "POOR"}]

        if not scored:
            return ("ABORTED" if num_aborted else "unknown", num_aborted)
        if "POOR" in scored:
            return "POOR", num_aborted
        if "FAIR" in scored:
            return "FAIR", num_aborted
        return "GOOD", num_aborted

    def _message_rows(self) -> list[tuple[object, object]]:
        """Return ``(time, content)`` pairs from the parsed messages, if available."""
        if isinstance(self.messages, pl.DataFrame) and not self.messages.is_empty():
            if not {"time", "content"}.issubset(self.messages.columns):
                return []
            return list(
                zip(
                    self.messages["time"].to_list(),
                    self.messages["content"].to_list(),
                )
            )
        if isinstance(self.messages, list):
            return [
                (
                    item.get("time", item.get("timestamp")),
                    item.get("content", item.get("message", "")),
                )
                for item in self.messages
                if isinstance(item, dict)
            ]
        return []

    def _final_validation_message_time(self) -> float | None:
        """Return the timestamp of the ``final_validation`` ASC message, if logged."""
        times: list[float] = []
        for time_value, content in self._message_rows():
            if not isinstance(content, str):
                continue
            if not _FINAL_VALIDATION_MSG_REGEX.match(content):
                continue
            try:
                times.append(float(time_value))
            except (TypeError, ValueError):
                continue
        return max(times) if times else None

    def _final_experimental_trial_end(self) -> float | None:
        """Return the end timestamp of the last non-practice trial, if known."""
        if not isinstance(self.stimulus_start_end_ts, list):
            return None

        stops: list[float] = []
        for entry in self.stimulus_start_end_ts:
            if not isinstance(entry, dict):
                continue
            if not _EXPERIMENT_TRIAL_REGEX.match(str(entry.get("trial", ""))):
                continue
            try:
                stops.append(float(entry["stop_ts"]))
            except (KeyError, TypeError, ValueError):
                continue
        return max(stops) if stops else None

    def _calibration_between(self, start: float, end: float) -> bool:
        """Return whether a calibration lies strictly between two session times.

        Calibrations are read from the calibration table. When no calibration
        table is stored, the ASC calibration messages are used instead so that
        an intervening recalibration is still detected.
        """
        times: list[float] = []
        if (
            isinstance(self.calibrations, pl.DataFrame)
            and "time" in self.calibrations.columns
        ):
            times = [
                float(time_value)
                for time_value in self.calibrations["time"]
                .cast(pl.Float64, strict=False)
                .drop_nulls()
                .to_list()
            ]

        if not times:
            for time_value, content in self._message_rows():
                if not isinstance(content, str):
                    continue
                if not _CALIBRATION_MSG_REGEX.search(content):
                    continue
                try:
                    times.append(float(time_value))
                except (TypeError, ValueError):
                    continue

        return any(start < time_value < end for time_value in times)

    def _compute_final_validation_score(self) -> float | str:
        """Return the ``accuracy_avg`` (dVA) of the post-experiment final validation.

        The score is the ``accuracy_avg`` of the last validation, but only when
        the ``final_validation`` screen is logged after the final experimental
        trial, the validation follows that screen, and no calibration happened
        between the end of the final trial and the validation. Sessions where
        this cannot be established from the available data return ``"unknown"``.

        Notes
        -----
        A binocular validation produces one row per eye. Rows sharing the final
        validation timestamp are averaged.
        """
        final_validation_time = self._final_validation_message_time()
        final_trial_end = self._final_experimental_trial_end()
        if final_validation_time is None or final_trial_end is None:
            return "unknown"
        if final_validation_time <= final_trial_end:
            return "unknown"

        if not isinstance(self.validations, pl.DataFrame):
            return "unknown"
        if self.validations.is_empty():
            return "unknown"
        if not {"time", "accuracy_avg"}.issubset(self.validations.columns):
            return "unknown"

        validation_times = (
            self.validations["time"].cast(pl.Float64, strict=False).drop_nulls()
        )
        if validation_times.is_empty():
            return "unknown"

        last_time = float(validation_times.max())
        if last_time <= final_validation_time:
            return "unknown"
        if self._calibration_between(final_trial_end, last_time):
            return "unknown"

        final_rows = self.validations.filter(
            pl.col("time").cast(pl.Float64, strict=False) == last_time
        )
        scores = [
            float(score)
            for score in final_rows["accuracy_avg"]
            .cast(pl.Float64, strict=False)
            .drop_nulls()
            .to_list()
        ]
        if not scores:
            return "unknown"
        return round(sum(scores) / len(scores), 3)

    def _create_stats(self):
        self.num_calibrations = len(self.calibrations)
        self.num_validations = len(self.validations)
        quality_lines = self._quality_message_lines()
        self.calibration_quality = self._compute_calibration_quality(quality_lines)
        self.validation_quality, self.num_aborted_validations = (
            self._compute_validation_quality(quality_lines)
        )
        self.final_validation_score_dva = self._compute_final_validation_score()

        self.tracked_eye = self._get_metadata("tracked_eye", "unknown")

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
        self.total_question_time_ms = self._compute_total_question_time()
        self._compute_rating_stats()

        self._compute_restart_info()

        duration = self._compute_session_duration()
        if duration is not None:
            self.total_session_duration = duration

        if self.total_reading_time == "unknown":
            reading = self._compute_total_reading_time()
            if reading is not None:
                self.total_reading_time = reading

        order_with_names = self._compute_stimulus_order_with_names()
        if isinstance(order_with_names, list):
            self.stimulus_order_ids_with_names = order_with_names

        mean_rt, sd_rt = self._compute_rt_per_stim()
        if mean_rt is not None:
            self.mean_rt_per_stim_ms = mean_rt
            self.sd_rt_per_stim_ms = sd_rt if sd_rt is not None else "unknown"

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
            total_ms += max(0.0, stop - start)
        if total_ms <= 0:
            return None
        return round(total_ms / 1000, 3)

    def _compute_stimulus_order_with_names(
        self,
    ) -> list[dict[str, object]] | str:
        """Return the stimulus order as a list of trial/stim-id/stim-name mappings.

        Each entry maps the presented order to its trial, stimulus id, and
        stimulus name. Returns ``"unknown"`` when the stimulus order or stimulus
        metadata is not available.
        """
        if not isinstance(self.stimulus_order_ids, list) or not self.stimulus_order_ids:
            return "unknown"
        if not isinstance(self.stimuli, list):
            return "unknown"

        id_to_stim = {
            getattr(s, "id", None): s for s in self.stimuli if hasattr(s, "id")
        }
        id_to_stim = {sid: s for sid, s in id_to_stim.items() if sid is not None}

        result: list[dict[str, object]] = []
        for stim_id in self.stimulus_order_ids:
            entry: dict[str, object] = {"stimulus_id": stim_id}
            stim = id_to_stim.get(stim_id)
            if stim is not None:
                entry["stimulus_name"] = getattr(stim, "name", None)
                entry["trial"] = getattr(stim, "trial_id", None)
            result.append(entry)
        return result

    def _compute_rt_per_stim(
        self,
    ) -> tuple[float | None, float | None]:
        """Return (mean, sd) of reading time per stimulus in ms across stimuli.

        Reading time per stimulus is the sum of per-page reading durations
        (entries with ``type == "reading time"``) for that stimulus. The mean
        and sample standard deviation are computed across stimuli. Returns
        ``(None, None)`` when no reading-time data is available.
        """
        if (
            not isinstance(self.stimulus_start_end_ts, list)
            or not self.stimulus_start_end_ts
        ):
            return None, None

        per_stim: dict[str, float] = {}
        for entry in self.stimulus_start_end_ts:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "reading time":
                continue
            try:
                dur = max(0.0, float(entry["duration_ms"]))
                stim = str(entry.get("stimulus", "unknown"))
            except (KeyError, TypeError, ValueError):
                continue
            per_stim[stim] = per_stim.get(stim, 0.0) + dur

        if not per_stim:
            return None, None

        values = list(per_stim.values())
        mean_rt = round(sum(values) / len(values), 2)
        if len(values) < 2:
            sd_rt: float | None = 0.0
        else:
            variance = sum((v - mean_rt) ** 2 for v in values) / (len(values) - 1)
            sd_rt = round(variance**0.5, 2)
        return mean_rt, sd_rt

    def _compute_restart_info(self) -> None:
        """Set the interrupted flag and restarted session name from the SID postfix.

        A session is a restart when its identifier carries a ``start_after_trial_<n>``
        or ``full_restart`` postfix. In that case ``restarted_session_name`` stores the
        canonical session identifier (without the postfix) that was restarted.
        """
        try:
            sid = Sid(self.session_identifier)
        except (ValueError, TypeError):
            return
        is_restart = bool(sid.notes)
        if isinstance(self.interrupted, str):
            self.interrupted = is_restart
        self.restarted_session_name = sid.id_no_postfix if is_restart else "unknown"

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
            by_trial[trial] = by_trial.get(trial, 0.0) + max(0.0, stop - start)
        return by_trial

    def _trial_time_spans(self) -> dict[str, tuple[float, float]]:
        """Return the recorded ``(start, stop)`` span per trial in milliseconds.

        The span is the earliest ``start_ts`` and the latest ``stop_ts`` across
        the trial's entries in ``stimulus_start_end_ts``, so it covers the whole
        recorded trial rather than only its reading pages. Trials without a
        usable timestamp pair are omitted.
        """
        spans: dict[str, list[float]] = {}
        if not isinstance(self.stimulus_start_end_ts, list):
            return {}
        for entry in self.stimulus_start_end_ts:
            if not isinstance(entry, dict):
                continue
            try:
                start = float(entry["start_ts"])
                stop = float(entry["stop_ts"])
                trial = str(entry["trial"])
            except (KeyError, TypeError, ValueError):
                continue
            if trial not in spans:
                spans[trial] = [start, stop]
            else:
                spans[trial][0] = min(spans[trial][0], start)
                spans[trial][1] = max(spans[trial][1], stop)
        return {trial: (span[0], span[1]) for trial, span in spans.items()}

    @staticmethod
    def _collect_loss_metrics(
        frames: list[pl.DataFrame | None],
    ) -> dict[str, dict[str, float]]:
        """Collect per-trial loss ratios from frames keyed by ``trial``.

        Rows from the data-loss and blink-loss tables are merged per trial.
        Columns without a value are left out so callers can fall back to
        ``"unknown"``.
        """
        metrics: dict[str, dict[str, float]] = {}
        for frame in frames:
            if not isinstance(frame, pl.DataFrame) or frame.is_empty():
                continue
            if "trial" not in frame.columns:
                continue
            for row in frame.iter_rows(named=True):
                trial = row.get("trial")
                if trial is None:
                    continue
                entry = metrics.setdefault(str(trial), {})
                for column in ("data_loss_ratio", "blink_loss_ratio"):
                    if column in entry or row.get(column) is None:
                        continue
                    try:
                        entry[column] = float(row[column])
                    except (TypeError, ValueError):
                        continue
        return metrics

    def _read_per_trial_loss_tsv(self) -> pl.DataFrame | None:
        """Read the sanity-check ``per_trial_data_loss_<sid>.tsv``, if present."""
        report_path = self.sanity_report_path
        if not isinstance(report_path, (str, Path)) or str(report_path) == "unknown":
            return None
        tsv_path = Path(report_path).parent / (
            f"per_trial_data_loss_{self.session_identifier}.tsv"
        )
        if not tsv_path.exists():
            return None
        try:
            return pl.read_csv(tsv_path, separator="\t")
        except Exception as exc:
            logger.warning(f"Could not read per-trial loss table {tsv_path}: {exc}")
            return None

    def _per_trial_loss_metrics(self) -> dict[str, dict[str, float]]:
        """Return per-trial data-loss and blink ratios keyed by trial id.

        Uses the per-trial tables computed during preprocessing. When those are
        not held in memory (for example after reloading cached outputs), falls
        back to the TSV the sanity report writes from the same tables. The
        ratios are fractions between 0 and 1.
        """
        metrics = self._collect_loss_metrics(
            [
                getattr(self, "_per_trial_data_loss", None),
                getattr(self, "_per_trial_blink_loss", None),
            ]
        )
        if metrics:
            return metrics
        return self._collect_loss_metrics([self._read_per_trial_loss_tsv()])

    def _validation_before_trial_start(
        self,
        spans: dict[str, tuple[float, float]],
    ) -> dict[str, float]:
        """Return the validation score in dVA immediately before each trial start.

        A validation counts for a trial when its timestamp lies in the
        inter-trial interval before the trial's ``start_ts``, that is, after the
        previous trial's ``stop_ts``. This prevents reusing the validation of an
        earlier trial when the expected pre-trial validation is missing. For
        binocular validations the rows sharing the selected timestamp are
        averaged, matching the final-validation score convention.
        """
        validations = self.validations
        if not isinstance(validations, pl.DataFrame) or validations.is_empty():
            return {}
        if not {"time", "accuracy_avg"}.issubset(validations.columns):
            return {}

        rows: list[tuple[float, float]] = []
        for time_value, accuracy in zip(
            validations["time"].cast(pl.Float64, strict=False).to_list(),
            validations["accuracy_avg"].cast(pl.Float64, strict=False).to_list(),
        ):
            if time_value is None or accuracy is None:
                continue
            rows.append((float(time_value), float(accuracy)))
        if not rows:
            return {}

        stops = sorted(stop for _, stop in spans.values())
        result: dict[str, float] = {}
        for trial, (start, _) in spans.items():
            previous_stops = [stop for stop in stops if stop <= start]
            lower = previous_stops[-1] if previous_stops else None
            candidates = [
                (time_value, accuracy)
                for time_value, accuracy in rows
                if time_value < start and (lower is None or time_value >= lower)
            ]
            if not candidates:
                continue
            last_time = max(time_value for time_value, _ in candidates)
            scores = [
                accuracy
                for time_value, accuracy in candidates
                if time_value == last_time
            ]
            result[trial] = round(sum(scores) / len(scores), 3)
        return result

    def _compute_trials(self) -> list[Trial] | str:
        """Assemble per-trial metrics from the answers CSV and eye-tracking data.

        Comprehension and reading-time fields come from the answers CSV and the
        per-stimulus reading spans. ``trial_duration_ms`` comes from the trial
        start/stop timestamps, ``data_loss_ratio`` and ``blink_ratio`` from the
        per-trial loss tables (or their sanity-check TSV), and
        ``validation_before_start_dva`` from the session validations. Fields
        without a matching source stay ``"unknown"``.

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
        trial_spans = self._trial_time_spans()
        loss_metrics = self._per_trial_loss_metrics()
        validations_before = self._validation_before_trial_start(trial_spans)

        trials: list[Trial] = []
        for trial_id, group in answers.group_by("trial", maintain_order=True):
            trial_id = trial_id[0] if isinstance(trial_id, tuple) else trial_id
            trial_key = str(trial_id)
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
            if first["stimulus_id"] is None:
                logger.warning(
                    f"Skipping trial {trial_id} in overview: missing stimulus_id."
                )
                continue
            try:
                trial_number = int(str(trial_id).rsplit("_", 1)[-1])
            except ValueError:
                trial_number = 0

            span = trial_spans.get(trial_key)
            trial_duration: float | str = (
                round(max(0.0, span[1] - span[0]), 3) if span is not None else "unknown"
            )
            loss = loss_metrics.get(trial_key, {})
            data_loss: float | str = (
                round(loss["data_loss_ratio"], 3)
                if "data_loss_ratio" in loss
                else "unknown"
            )
            blink_ratio: float | str = (
                round(loss["blink_loss_ratio"], 3)
                if "blink_loss_ratio" in loss
                else "unknown"
            )

            trials.append(
                Trial(
                    trial_number=trial_number,
                    stimulus_id=int(first["stimulus_id"]),
                    stimulus_name=str(first["stimulus"]),
                    is_practice=str(trial_id).startswith("PRACTICE_"),
                    num_questions=group.height,
                    comprehension_score=score,
                    comprehension_question_time_ms=question_time,
                    reading_time_ms=round(reading_by_trial.get(str(trial_id), 0.0), 3),
                    trial_duration_ms=trial_duration,
                    data_loss_ratio=data_loss,
                    blink_ratio=blink_ratio,
                    validation_before_start_dva=validations_before.get(
                        trial_key, "unknown"
                    ),
                )
            )

        trials.sort(key=lambda t: (t.is_practice, t.trial_number))
        return trials

    def _compute_total_question_time(self) -> float | str:
        """Sum comprehension question time in milliseconds over experiment trials.

        Practice trials are excluded, matching the comprehension score
        convention. Returns ``"unknown"`` when no trial data is available.
        """
        if not isinstance(self.trials, list):
            return "unknown"
        total = sum(
            t.comprehension_question_time_ms for t in self.trials if not t.is_practice
        )
        return round(total, 3)

    def _compute_rating_stats(self) -> None:
        """Compute rating-screen averages and total rating time from the logfile.

        Rating responses are logged as ``option_<n>`` key presses on the
        ``familiarity_rating_screen_1``/``familiarity_rating_screen_2`` and
        ``subject_difficulty_screen`` pages. The per-screen mean is stored as
        ``familiarity_1``/``familiarity_2``/``subjective_difficulty`` and the
        summed screen duration as ``total_rating_time_ms``. Fields keep their
        ``"unknown"`` default when no matching rows are present.
        """
        if not isinstance(self.logfile, pl.DataFrame) or self.logfile.is_empty():
            return

        required = {
            "page_number",
            "key_pressed",
            "screen_onset_timestamp",
            "timestamp",
        }
        if not required.issubset(self.logfile.columns):
            return

        screen_to_field = {
            "familiarity_rating_screen_1": "familiarity_1",
            "familiarity_rating_screen_2": "familiarity_2",
            "subject_difficulty_screen": "subjective_difficulty",
        }
        responses: dict[str, list[float]] = {v: [] for v in screen_to_field.values()}
        total_ms = 0.0
        found = False

        for page, key, onset, response_ts in self.logfile.select(
            ["page_number", "key_pressed", "screen_onset_timestamp", "timestamp"]
        ).iter_rows():
            if not isinstance(page, str) or page not in screen_to_field:
                continue
            try:
                onset_ms = float(onset)
                response_ms = float(response_ts)
            except (TypeError, ValueError):
                continue
            found = True
            if response_ms >= onset_ms:
                total_ms += response_ms - onset_ms
            option = _parse_rating_option(key)
            if option is not None:
                responses[screen_to_field[page]].append(float(option))

        if not found:
            return

        self.total_rating_time_ms = round(total_ms, 3)
        for field_name, values in responses.items():
            if values:
                setattr(self, field_name, round(sum(values) / len(values), 3))
