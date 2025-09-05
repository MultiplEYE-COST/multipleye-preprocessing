from dataclasses import dataclass


@dataclass
class Trial:

    participant_id: int
    session_id: int
    stimulus_id: str
    stimulus_version: int
    trial_number: int
    reading_time: float
    avg_comprehension_score: float
    question_order: list[str]
    total_trial_duration: float
    comprehension_scores = list[int]
    familiarity_rating_1: int
    familiarity_rating_2: int
    difficulty_rating: int