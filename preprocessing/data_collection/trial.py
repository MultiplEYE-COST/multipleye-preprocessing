from dataclasses import dataclass, field


@dataclass
class TrialAnswer:
    """One comprehension answer belonging to a trial.

    The fields mirror the session answers CSV. Values that are absent from the
    CSV stay ``None`` so partial answer data remains usable.

    Fields
    ------
    question_id : str | None
        Question identifier. Together with the trial this identifies the
        answer.
    condition : str | None
        Question condition, ``local``, ``bridging`` or ``global``.
    slot : str | None
        Question slot from the question-order CSV, for example
        ``local_question_1``.
    selected_option_key : str | None
        Key of the option the participant confirmed.
    selected_option_text : str | None
        Text of the selected option.
    is_correct : bool | None
        Whether the confirmed option is the target option.
    correct_answer_key : str | None
        Key of the target option.
    correct_answer_text : str | None
        Text of the target option.
    preliminary_answer_keys : list[str] | None
        Preliminary key presses in order.
    preliminary_answer_onsets_ms : list[float] | None
        Question-onset-relative timestamps for the preliminary key presses,
        in milliseconds.
    confirmation_rt_ms : float | None
        Time from question onset to the confirmation key press, in
        milliseconds.
    answer_source : str | None
        Source the answer was parsed from, for example ``logfile``.
    """

    question_id: str | None
    condition: str | None
    slot: str | None
    selected_option_key: str | None
    selected_option_text: str | None
    is_correct: bool | None
    correct_answer_key: str | None
    correct_answer_text: str | None
    preliminary_answer_keys: list[str] | None
    preliminary_answer_onsets_ms: list[float] | None
    confirmation_rt_ms: float | None
    answer_source: str | None


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
    trial_id : str
        Trial identifier inside the session, for example ``trial_1`` or
        ``PRACTICE_trial_1``.
    trial_number : int
        Trial number within the session (1-based).
    stimulus_id : int
        Numeric stimulus identifier.
    stimulus_name : str
        Stimulus name (e.g. ``Lit_MagicMountain``).
    text_id : str
        Language-specific stimulus text identifier, used to join the item
        view. Built as ``<stimulus_name>_<language>``.
    is_practice : bool
        True for practice trials.
    num_questions : int
        Number of comprehension questions answered for this trial.
    num_questions_local : int
        Number of local comprehension questions.
    num_questions_global : int
        Number of global comprehension questions.
    num_questions_bridging : int
        Number of bridging comprehension questions.
    comprehension_score : float
        Proportion of correct comprehension answers for this trial.
    comprehension_score_local : float | str
        Proportion of correct local answers, ``"unknown"`` when the trial has
        no local questions.
    comprehension_score_global : float | str
        Proportion of correct global answers, ``"unknown"`` when the trial has
        no global questions.
    comprehension_score_bridging : float | str
        Proportion of correct bridging answers, ``"unknown"`` when the trial
        has no bridging questions.
    comprehension_question_time_ms : float
        Total time spent on comprehension questions, in milliseconds.
    reading_time_ms : float
        Total reading time for the trial's pages, in milliseconds.
    familiarity_1 : float | str
        Selected option number on the first familiarity rating screen.
        ``"unknown"`` when no rating was logged for the trial.
    familiarity_2 : float | str
        Selected option number on the second familiarity rating screen.
    subjective_difficulty : float | str
        Selected option number on the subjective-difficulty rating screen.
    rating_time_ms : float | str
        Summed duration of the trial's rating screens, in milliseconds.
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
    question_order_version : int | None
        Question-order version for this trial from the session CSV. ``None``
        when no matching order record exists.
    question_order : dict[str, list[int]] | None
        Explicit local, bridging and global question order codes for this
        trial. ``None`` when no matching order record exists.
    answers : list[TrialAnswer]
        Comprehension answers for this trial. Empty when the answers CSV has
        no usable rows for the trial.
    """

    trial_id: str
    trial_number: int
    stimulus_id: int
    stimulus_name: str
    text_id: str
    is_practice: bool
    num_questions: int
    num_questions_local: int
    num_questions_global: int
    num_questions_bridging: int
    comprehension_score: float
    comprehension_score_local: float | str
    comprehension_score_global: float | str
    comprehension_score_bridging: float | str
    comprehension_question_time_ms: float
    reading_time_ms: float
    familiarity_1: float | str = "unknown"
    familiarity_2: float | str = "unknown"
    subjective_difficulty: float | str = "unknown"
    rating_time_ms: float | str = "unknown"
    trial_duration_ms: float | str = "unknown"
    data_loss_ratio: float | str = "unknown"
    blink_ratio: float | str = "unknown"
    validation_before_start_dva: float | str = "unknown"
    question_order_version: int | None = None
    question_order: dict[str, list[int]] | None = None
    answers: list[TrialAnswer] = field(default_factory=list)
