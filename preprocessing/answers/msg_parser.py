import polars as pl
import re


def parse_answers_from_messages(messages: pl.DataFrame) -> pl.DataFrame:
    """Parse comprehension question answers from ASC messages.

    Parameters
    ----------
    messages : pl.DataFrame
        DataFrame with columns 'time' (int/float) and 'content' (str).

    Returns
    -------
    pl.DataFrame
        A DataFrame with one row per question attempt.
    """
    if messages is None or messages.is_empty():
        return pl.DataFrame(
            schema={
                "trial_id": pl.Utf8,
                "stimulus_name": pl.Utf8,
                "stimulus_id": pl.Utf8,
                "question_id": pl.Utf8,
                "question_onset_ts": pl.Float64,
                "preliminary_keys": pl.List(pl.Utf8),
                "preliminary_tss": pl.List(pl.Float64),
                "final_confirmation_ts": pl.Float64,
                "image_offset_ts": pl.Float64,
                "final_answer_key": pl.Utf8,
                "is_correct": pl.Boolean,
                "question_stop_ts": pl.Float64,
            }
        )

    # Define regex patterns based on the implementation guide
    START_RE = re.compile(
        r"start_recording_(?P<trial>PRACTICE_trial_\d+|trial_\d+)_"
        r"stimulus_(?P<stimulus_name>[A-Za-z_]+)_"
        r"(?P<stimulus_id>\d+)_"
        r"question_(?P<question_id>\d+)"
    )

    PRELIMINARY_RE = re.compile(
        r"(?P<trial>PRACTICE_trial_\d+|trial_\d+)_stimulus_"
        r"(?P<stimulus_name>[A-Za-z_]+)_"
        r"(?P<stimulus_id>\d+)_"
        r"question_(?P<question_id>\d+)_"
        r"preliminary_answer_(?P<key>target_key|distractor_[a-d]_key|final_confirmation)"
    )

    FINAL_ANSWER_RE = re.compile(
        r"(?P<trial>PRACTICE_trial_\d+|trial_\d+)_stimulus_"
        r"(?P<stimulus_name>[A-Za-z_]+)_"
        r"(?P<stimulus_id>\d+)_"
        r"question_(?P<question_id>\d+)_"
        r"final_answer_given_is_(?P<key>target_key|distractor_[a-d]_key)"
    )

    CORRECTNESS_RE = re.compile(
        r"(?P<trial>PRACTICE_trial_\d+|trial_\d+)_stimulus_"
        r"(?P<stimulus_name>[A-Za-z_]+)_"
        r"(?P<stimulus_id>\d+)_"
        r"question_(?P<question_id>\d+)_"
        r"answer_given_is_correct:(?P<correct>True|False)"
    )

    IMAGE_OFFSET_RE = re.compile(r"question_screen_image_offset")

    STOP_RE = re.compile(
        r"stop_recording_(?P<trial>PRACTICE_trial_\d+|trial_\d+)_"
        r"stimulus_(?P<stimulus_name>[A-Za-z_]+)_"
        r"(?P<stimulus_id>\d+)_"
        r"question_(?P<question_id>\d+)"
    )

    parsed_rows = []

    for row in messages.iter_rows(named=True):
        content = row["content"]
        time = row["time"]

        m = START_RE.match(content)
        if m:
            parsed_rows.append(
                {
                    "time": float(time),
                    "trial_id": m.group("trial"),
                    "stimulus_name": m.group("stimulus_name"),
                    "stimulus_id": m.group("stimulus_id"),
                    "question_id": m.group("question_id"),
                    "action": "question_start",
                }
            )
            continue

        m = PRELIMINARY_RE.match(content)
        if m:
            key = m.group("key")
            action = (
                "final_confirmation"
                if key == "final_confirmation"
                else "preliminary_answer"
            )
            parsed_rows.append(
                {
                    "time": float(time),
                    "trial_id": m.group("trial"),
                    "stimulus_name": m.group("stimulus_name"),
                    "stimulus_id": m.group("stimulus_id"),
                    "question_id": m.group("question_id"),
                    "action": action,
                    "key_type": key if action == "preliminary_answer" else None,
                }
            )
            continue

        m = FINAL_ANSWER_RE.match(content)
        if m:
            parsed_rows.append(
                {
                    "time": float(time),
                    "trial_id": m.group("trial"),
                    "stimulus_name": m.group("stimulus_name"),
                    "stimulus_id": m.group("stimulus_id"),
                    "question_id": m.group("question_id"),
                    "action": "final_answer_given",
                    "key_type": m.group("key"),
                }
            )
            continue

        m = CORRECTNESS_RE.match(content)
        if m:
            parsed_rows.append(
                {
                    "time": float(time),
                    "trial_id": m.group("trial"),
                    "stimulus_name": m.group("stimulus_name"),
                    "stimulus_id": m.group("stimulus_id"),
                    "question_id": m.group("question_id"),
                    "action": "correctness",
                    "is_correct": m.group("correct") == "True",
                }
            )
            continue

        if IMAGE_OFFSET_RE.match(content):
            parsed_rows.append({"time": float(time), "action": "image_offset"})
            continue

        m = STOP_RE.match(content)
        if m:
            parsed_rows.append(
                {
                    "time": float(time),
                    "trial_id": m.group("trial"),
                    "stimulus_name": m.group("stimulus_name"),
                    "stimulus_id": m.group("stimulus_id"),
                    "question_id": m.group("question_id"),
                    "action": "question_stop",
                }
            )
            continue

    if not parsed_rows:
        return pl.DataFrame(
            schema={
                "trial_id": pl.Utf8,
                "stimulus_name": pl.Utf8,
                "stimulus_id": pl.Utf8,
                "question_id": pl.Utf8,
                "question_onset_ts": pl.Float64,
                "preliminary_keys": pl.List(pl.Utf8),
                "preliminary_tss": pl.List(pl.Float64),
                "final_confirmation_ts": pl.Float64,
                "image_offset_ts": pl.Float64,
                "final_answer_key": pl.Utf8,
                "is_correct": pl.Boolean,
                "question_stop_ts": pl.Float64,
            }
        )

    df_parsed = pl.DataFrame(parsed_rows)

    # Fill missing identifiers for image_offset which doesn't contain trial/stim info
    df_parsed = df_parsed.with_columns(
        [
            pl.col("trial_id").forward_fill(),
            pl.col("stimulus_name").forward_fill(),
            pl.col("stimulus_id").forward_fill(),
            pl.col("question_id").forward_fill(),
        ]
    )

    groups = df_parsed.group_by(
        ["trial_id", "stimulus_name", "stimulus_id", "question_id"], maintain_order=True
    )

    result_rows = []
    for (trial_id, stim_name, stim_id, q_id), group in groups:
        row_data = {
            "trial_id": trial_id,
            "stimulus_name": stim_name,
            "stimulus_id": stim_id,
            "question_id": q_id,
            "question_onset_ts": None,
            "preliminary_keys": [],
            "preliminary_tss": [],
            "final_confirmation_ts": None,
            "image_offset_ts": None,
            "final_answer_key": None,
            "is_correct": None,
            "question_stop_ts": None,
        }

        for p_row in group.iter_rows(named=True):
            action = p_row["action"]
            if action == "question_start":
                row_data["question_onset_ts"] = p_row["time"]
            elif action == "preliminary_answer":
                row_data["preliminary_keys"].append(p_row["key_type"])
                row_data["preliminary_tss"].append(p_row["time"])
            elif action == "final_confirmation":
                row_data["final_confirmation_ts"] = p_row["time"]
            elif action == "image_offset":
                row_data["image_offset_ts"] = p_row["time"]
            elif action == "final_answer_given":
                row_data["final_answer_key"] = p_row["key_type"]
            elif action == "correctness":
                row_data["is_correct"] = p_row["is_correct"]
            elif action == "question_stop":
                row_data["question_stop_ts"] = p_row["time"]

        result_rows.append(row_data)

    return pl.DataFrame(
        result_rows,
        schema={
            "trial_id": pl.Utf8,
            "stimulus_name": pl.Utf8,
            "stimulus_id": pl.Utf8,
            "question_id": pl.Utf8,
            "question_onset_ts": pl.Float64,
            "preliminary_keys": pl.List(pl.Utf8),
            "preliminary_tss": pl.List(pl.Float64),
            "final_confirmation_ts": pl.Float64,
            "image_offset_ts": pl.Float64,
            "final_answer_key": pl.Utf8,
            "is_correct": pl.Boolean,
            "question_stop_ts": pl.Float64,
        },
    )
