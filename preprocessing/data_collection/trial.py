from dataclasses import dataclass


@dataclass
class Trial:
    """Per-trial metrics assembled from the session answers and reading times.

    A trial corresponds to one stimulus presentation (including practice
    trials). The comprehension fields are derived from the session answers
    CSV; ``reading_time_ms`` from the documented per-stimulus reading span.

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
    """

    trial_number: int
    stimulus_id: int
    stimulus_name: str
    is_practice: bool
    num_questions: int
    comprehension_score: float
    comprehension_question_time_ms: float
    reading_time_ms: float
