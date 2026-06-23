import warnings
import polars as pl


def parse_answers_from_logfile(
    logfile: pl.DataFrame, stimuli_trial_mapping: dict[str, str] = None
) -> pl.DataFrame:
    """Parse comprehension question answers from experiment logfile.

    Parameters
    ----------
    logfile : pl.DataFrame
        DataFrame from EXPERIMENT_*.txt with columns like 'timestamp', 'message', etc.
    stimuli_trial_mapping : dict[str, str], optional
        Mapping from trial_id (e.g. 'trial_1') to stimulus_name.

    Returns
    -------
    pl.DataFrame
        A DataFrame with one row per question attempt.
    """
    warnings.warn(
        "ASC messages are missing or empty. Falling back to parsing answers from the experiment logfile. "
        "Response time (onset-based) and image offset information will not be available.",
        UserWarning,
    )
    if logfile is None or logfile.is_empty():
        return _empty_result_df()

    # Filter for relevant messages
    relevant_df = logfile.filter(
        pl.col("message").str.contains("preliminary answer:|FINAL ANSWER:")
    )

    if relevant_df.is_empty():
        return _empty_result_df()

    # Normalize trial_id to match messages/mapping (e.g. 1 -> "trial_1")
    # In the toy logfile, trial_number is often 1, 2, 3...
    # But it can also be PRACTICE_trial_1 if handled specially?
    # Actually the toy logfile showed trial_number as 1, 2, 3.

    result_rows = []

    # We group by trial_number, stimulus_number, and page_number (which is question_id)
    # Maintain order of events
    groups = relevant_df.group_by(
        ["trial_number", "stimulus_number", "page_number"], maintain_order=True
    )

    for (trial_num, stim_num, q_id), group in groups:
        # Ignore rows without trial/stim/page info (shouldn't happen with our filter usually)
        if trial_num is None or stim_num is None or q_id is None:
            continue

        trial_id = f"trial_{int(trial_num)}"
        # Handle practice trials if possible (though logfile might not use this format)
        # Based on multipleye_data_collection.py, they map PRACTICE_1 to PRACTICE_trial_1
        # But here we just have numeric trial_number.

        stim_name = None
        if stimuli_trial_mapping and trial_id in stimuli_trial_mapping:
            stim_name = stimuli_trial_mapping[trial_id]

        stim_id_str = str(int(stim_num))
        q_id_str = str(int(q_id))

        row_data = {
            "trial_id": trial_id,
            "stimulus_name": stim_name,
            "stimulus_id": stim_id_str,
            "question_id": q_id_str,
            "question_onset_ts": None,  # Logfile doesn't have a clear "onset" message like ASC
            "preliminary_keys": [],
            "preliminary_tss": [],
            "final_confirmation_ts": None,
            "image_offset_ts": None,
            "final_answer_key": None,
            "is_correct": None,
            "question_stop_ts": None,
        }

        for p_row in group.iter_rows(named=True):
            msg = p_row["message"]
            ts = p_row["timestamp"]

            if msg.startswith("preliminary answer:"):
                key = msg.split("preliminary answer:")[1].strip()
                if key == "final_confirmation":
                    row_data["final_confirmation_ts"] = ts
                else:
                    row_data["preliminary_keys"].append(key)
                    row_data["preliminary_tss"].append(ts)
            elif msg.startswith("FINAL ANSWER:"):
                # Example: FINAL ANSWER: correct answer is 'down' (A Python package), participant's answer is True
                row_data["is_correct"] = "participant's answer is True" in msg
                # We don't have the final_answer_key here explicitly, but we can take the last preliminary one
                if row_data["preliminary_keys"]:
                    row_data["final_answer_key"] = row_data["preliminary_keys"][-1]

                # Use timestamp as stop_ts
                row_data["question_stop_ts"] = ts

        result_rows.append(row_data)

    if not result_rows:
        return _empty_result_df()

    return pl.DataFrame(result_rows, schema=_result_schema())


def _empty_result_df():
    return pl.DataFrame(schema=_result_schema())


def _result_schema():
    return {
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
