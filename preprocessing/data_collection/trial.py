from dataclasses import dataclass


@dataclass
class Trial:
    """Per-trial metrics assembled from the session answers and reading times.

    A trial corresponds to one stimulus presentation (including practice
    trials). The comprehension fields are derived from the session answers
    CSV; ``reading_time_ms`` from the documented per-stimulus reading span.
    The eye-tracking fields use the per-trial tables computed during
    preprocessing (or the sanity-check TSV written from them) and the session
    timestamps/validations. They are set to ``"unknown"`` when the session does
    not provide the corresponding source.

    Fields
    ------
    trial_number : int
        Trial number within the session (1-based).
    stimulus_id : int
        Numeric stimulus identifier.
    stimulus_name : str
        Stimulus name (e.g. ``Lit_MagicMountain``).
    is_practice : bool
        True for practice trials.
    num_questions : int
        Number of comprehension questions answered for this trial.
    comprehension_score : float
        Proportion of correct comprehension answers for this trial.
    comprehension_question_time_ms : float
        Total time spent on comprehension questions, in milliseconds.
    reading_time_ms : float
        Total reading time for the trial's pages, in milliseconds.
    trial_duration_ms : float | str
        Total trial recording duration in milliseconds, computed from the
        trial's ``start_ts``/``stop_ts`` entries as the span from the earliest
        start to the latest stop. ``"unknown"`` when no timestamps are stored.
    data_loss_ratio : float | str
        Fraction of missing or invalid samples in the trial, 0 to 1, from the
        per-trial data-loss table. ``"unknown"`` when no such table exists.
    blink_ratio : float | str
        Fraction of the trial recording spent in blinks, 0 to 1, from the
        per-trial blink-loss table. ``"unknown"`` when no such table exists.
    validation_before_start_dva : float | str
        ``accuracy_avg`` in degrees of visual angle of the validation in the
        inter-trial interval immediately before the trial starts. For
        binocular validations the rows sharing the validation timestamp are
        averaged. ``"unknown"`` when no trial timestamp or no such validation
        is available.
    """

    trial_number: int
    stimulus_id: int
    stimulus_name: str
    is_practice: bool
    num_questions: int
    comprehension_score: float
    comprehension_question_time_ms: float
    reading_time_ms: float
    trial_duration_ms: float | str = "unknown"
    data_loss_ratio: float | str = "unknown"
    blink_ratio: float | str = "unknown"
    validation_before_start_dva: float | str = "unknown"
