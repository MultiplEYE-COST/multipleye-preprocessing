from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import polars as pl

from ..data_collection.stimulus import Stimulus
from ..utils.logging import get_logger
from .io import write_answers
from .parser import construct_question_id, parse_question_order


def _normalize_trial_key(k) -> int | str:
    """Accept 'trial_7' or 7 or '7' or 'PRACTICE_1' and return int(7) or 'PRACTICE_1'."""
    if isinstance(k, int):
        return k
    s = str(k)
    if s.startswith("trial_"):
        try:
            return int(s.split("_", 1)[1])
        except (ValueError, IndexError):
            return s
    try:
        return int(s)
    except ValueError:
        return s


def collect_session_answers(
    question_order_csv: Path,
    stimuli_trial_map: Mapping[str | int, str],
    stimuli: Sequence[Stimulus] | None = None,
    parsed_answers: pl.DataFrame | None = None,
    out_path: Path | None = None,
    source: str = "unknown",
    completed_stimuli_ids: Sequence[int] | None = None,
    was_session_interrupted: bool = False,
) -> pl.DataFrame:
    """Assemble per-session question rows from order CSV and a trial->stimulus map.

    Parameters
    ----------
    question_order_csv: Path
        Path to the session's question_order_versions.csv.
    stimuli_trial_map: Mapping
        Maps trial identifiers to stimulus names, e.g., {'trial_1': 'Arg_PISACowsMilk_10', ...}.
        Contains all stimulus names that should have been completed in the session even if the session had been
        interrupted.
    stimuli: Sequence[Stimulus] | None
        List of Stimulus objects to look up correct answer texts.
    parsed_answers: pl.DataFrame | None
        DataFrame with parsed answers from ASC messages or logfile.
    out_path: Path | None
        If provided, the resulting table is written to this CSV path.
    source: str
        The source of the parsed answers, e.g., 'asc' or 'logfile'.
    completed_stimuli_ids: Sequence[int] | None
        List of stimulus numeric IDs in the order they were completed. Can contain less items than stimuli_trial_map if
        the session had been interrupted.
    was_session_interrupted: bool
        Whether a session was interrupted.

    Returns
    -------
    pl.DataFrame with columns:
      - trial (string, e.g., 'trial_1')
      - stimulus (string)
      - question_id (string)
      - question_order_version (int)
      - stimulus_id (int)
      - snippet_number (int)
      - condition_number (int: 1=local, 2=bridging, 3=global)
      - slot (string, e.g., 'local_question_1')
      - final_answer_key (string)
      - answer_text (string)
      - is_correct (bool)
      - correct_answer_key (string)
      - correct_answer_text (string)
      - preliminary_rt_ms (float)  time from question onset to last preliminary key press
      - confirmation_rt_ms (float)  time from question onset to confirmation button press
      - preliminary_answer_keys (list[str])  all preliminary key presses in order
      - preliminary_answer_onsets_ms (list[float])  onset-relative timestamps for each preliminary press
      - answer_source (string)
    """
    logger = get_logger()

    # Normalize mapping
    norm_map = {_normalize_trial_key(k): v for k, v in stimuli_trial_map.items()}
    logger.debug(f"DEBUG: Normalized trial map: {norm_map}")

    # Adds 'trial' column (as int 1, 2, 3...) from question_order CSV
    order_df = parse_question_order(question_order_csv)

    # MultiplEYE trial logic: match order_df rows to norm_map keys by sequence
    def _sort_key(x):
        if isinstance(x, int):
            return (1, x)
        s = str(x)
        if s.startswith("PRACTICE_"):
            try:
                # Extract number from PRACTICE_1 or PRACTICE_trial_1
                num_part = s.split("_")[-1]
                return (0, int(num_part))
            except (ValueError, IndexError):
                return (0, 0)
        return (2, s)

    sorted_keys = sorted(norm_map.keys(), key=_sort_key)
    logger.debug(f"DEBUG: Sorted norm_map keys: {sorted_keys}")

    # trial_mapping: CSV row index -> actual trial identifier (int or PRACTICE_X)
    trial_mapping = dict(enumerate(sorted_keys, start=1))

    # stim_id_mapping: actual trial identifier -> stimulus numeric ID
    stim_id_map = {}
    if (
        completed_stimuli_ids
        and len(completed_stimuli_ids) == len(sorted_keys)
        or completed_stimuli_ids
        and was_session_interrupted
    ):
        stim_id_map = dict(zip(sorted_keys, completed_stimuli_ids))
    elif completed_stimuli_ids:
        logger.warning(
            f"Completed stimuli count ({len(completed_stimuli_ids)}) does not match "
            f"trial map count ({len(sorted_keys)}). Stimulus enrichment might be limited."
        )
    logger.debug(f"DEBUG: Stimulus ID map: {stim_id_map}")

    # Long format per trial with 6 question slots
    slots = [
        "local_question_1",
        "local_question_2",
        "bridging_question_1",
        "bridging_question_2",
        "global_question_1",
        "global_question_2",
    ]

    missing = [c for c in slots if c not in order_df.columns]
    if missing:
        raise ValueError(f"Missing columns in question order csv: {missing}")

    # Build long format
    per_slot_frames = []
    for slot in slots:
        df_slot = order_df.select(
            pl.col("trial"),
            pl.col("question_order_version"),
            pl.lit(slot).alias("slot"),
            pl.col(slot).alias("order_code"),
            (pl.col(slot) // 10).alias("condition_number"),
        )
        per_slot_frames.append(df_slot)

    long_df = pl.concat(per_slot_frames)

    # Build identifier columns
    def _stim_for_trial(order_trial_idx: int) -> str:
        actual_key = trial_mapping.get(order_trial_idx)
        if actual_key is None or actual_key not in norm_map:
            return f"Unknown_Stim_{order_trial_idx}"
        return norm_map[actual_key]

    def _to_trial_id(order_trial_idx: int) -> str:
        actual_key = trial_mapping.get(order_trial_idx)
        if isinstance(actual_key, int):
            return f"trial_{actual_key}"
        if isinstance(actual_key, str) and actual_key.startswith("PRACTICE_"):
            if "trial" in actual_key:
                return actual_key
            num = actual_key.split("_")[1] if "_" in actual_key else "1"
            return f"PRACTICE_trial_{num}"
        return str(actual_key)

    # Build snippet map from stimuli objects
    snippet_map = {}
    if stimuli:
        for stim in stimuli:
            for q in stim.questions:
                try:
                    q_order_code = int(q.id[-2:])
                    # Map (stimulus_name, order_code) -> snippet_no
                    snippet_map[(stim.name, q_order_code)] = q.snippet_no
                except (ValueError, TypeError):
                    continue

    def _safe_construct_question_id(
        stim_name: str, order_code: int, trial_key: any
    ) -> str | None:
        stim_id = stim_id_map.get(trial_key)
        # Try to get snippet_no from map, default to 1
        snippet_no = snippet_map.get((stim_name, order_code), 1)
        try:
            return construct_question_id(
                stim_name, order_code, stimulus_id=stim_id, snippet_no=snippet_no
            )
        except (ValueError, KeyError, AttributeError):
            return None

    long_df = long_df.with_columns(
        pl.col("trial")
        .map_elements(_stim_for_trial, return_dtype=pl.Utf8)
        .alias("stimulus"),
        pl.col("trial")
        .map_elements(
            lambda t: stim_id_map.get(trial_mapping.get(int(t))),
            return_dtype=pl.Int32,
        )
        .alias("stimulus_id"),
        pl.col("trial")
        .map_elements(_to_trial_id, return_dtype=pl.Utf8)
        .alias("trial_id"),
    )

    long_df = long_df.with_columns(
        pl.struct(["trial", "stimulus", "order_code"])
        .map_elements(
            lambda x: _safe_construct_question_id(
                x["stimulus"],
                int(x["order_code"]),
                trial_mapping.get(int(x["trial"])),
            ),
            return_dtype=pl.Utf8,
        )
        .alias("question_id"),
    )

    # Convert 'trial' back to original trial_id string for output
    long_df = long_df.with_columns(pl.col("trial_id").alias("trial"))

    # Add answer source
    long_df = long_df.with_columns(pl.lit(source).alias("answer_source"))

    if parsed_answers is not None:
        # Merge parsed answers by (trial_id, question_id)
        long_df = long_df.join(
            parsed_answers, on=["trial_id", "question_id"], how="left"
        )

        # Handle space-only answers: participant pressed space without selecting
        long_df = long_df.with_columns(
            pl.when(
                pl.col("final_confirmation_ts").is_not_null()
                & pl.col("final_answer_key").is_null()
            )
            .then(pl.lit("space"))
            .otherwise(pl.col("final_answer_key"))
            .alias("final_answer_key"),
        )

        # Compute derived columns
        long_df = long_df.with_columns(
            (pl.col("preliminary_tss").list.last() - pl.col("question_onset_ts")).alias(
                "preliminary_rt_ms"
            ),
            (pl.col("final_confirmation_ts") - pl.col("question_onset_ts")).alias(
                "confirmation_rt_ms"
            ),
            pl.col("preliminary_keys").alias("preliminary_answer_keys"),
            pl.struct(["preliminary_tss", "question_onset_ts"])
            .map_elements(
                lambda row: (
                    [
                        round(t - row["question_onset_ts"], 1)
                        for t in row["preliminary_tss"]
                    ]
                    if row["preliminary_tss"] and row["question_onset_ts"] is not None
                    else None
                ),
                return_dtype=pl.List(pl.Float64),
            )
            .alias("preliminary_answer_onsets_ms"),
        )

        # Warn if any final_answer_key differs from the last preliminary key (data anomaly)
        anomaly = long_df.filter(
            pl.col("preliminary_keys").is_not_null()
            & (pl.col("preliminary_keys").list.len() > 0)
            & (pl.col("preliminary_keys").list.last() != pl.col("final_answer_key"))
        )
        if anomaly.height > 0:
            logger.warning(
                f"Found {anomaly.height} question(s) where final_answer_key differs from "
                f"the last preliminary key press (data anomaly)."
            )
    else:
        long_df = long_df.with_columns(
            pl.lit(None).alias("final_answer_key").cast(pl.Utf8),
            pl.lit(None).alias("is_correct").cast(pl.Boolean),
            pl.lit(None).alias("preliminary_rt_ms").cast(pl.Float64),
            pl.lit(None).alias("confirmation_rt_ms").cast(pl.Float64),
        )

    # Add correct answers from stimuli objects
    q_map: dict = {}
    if stimuli:
        for stim in stimuli:
            for q in stim.questions:
                try:
                    q_order_code = int(q.id[-2:])
                except (ValueError, TypeError):
                    continue

                # For Stimulus objects, the numeric ID is already in stim.id
                q_id = construct_question_id(
                    stim.name,
                    q_order_code,
                    stimulus_id=stim.id,
                    snippet_no=q.snippet_no,
                )
                if q_id:
                    q_map[q_id] = {
                        "correct_answer_key": "target_key",
                        "correct_answer_text": q.target,
                        "snippet_number": q.snippet_no,
                        "options": {
                            "target_key": q.target,
                            "distractor_a_key": q.distractor_a,
                            "distractor_b_key": q.distractor_b,
                            "distractor_c_key": q.distractor_c,
                        },
                    }

        def _get_correct_info(q_id: str, field: str) -> str | None:
            return q_map.get(q_id, {}).get(field)

        def _get_answer_text(q_id: str, key: str) -> str | None:
            if not q_id or not key:
                return None
            options = q_map.get(q_id, {}).get("options")
            if options:
                return options.get(key)
            return None

        long_df = long_df.with_columns(
            pl.col("question_id")
            .map_elements(
                lambda q_id: _get_correct_info(q_id, "correct_answer_key"),
                return_dtype=pl.Utf8,
            )
            .alias("correct_answer_key"),
            pl.col("question_id")
            .map_elements(
                lambda q_id: _get_correct_info(q_id, "correct_answer_text"),
                return_dtype=pl.Utf8,
            )
            .alias("correct_answer_text"),
        )
        long_df = long_df.with_columns(
            pl.struct(["question_id", "final_answer_key"])
            .map_elements(
                lambda x: _get_answer_text(x["question_id"], x["final_answer_key"]),
                return_dtype=pl.Utf8,
            )
            .alias("answer_text"),
            # Re-calculate or confirm is_correct if we have keys
            pl.when(
                pl.col("final_answer_key").is_not_null()
                & pl.col("correct_answer_key").is_not_null()
            )
            .then(pl.col("final_answer_key") == pl.col("correct_answer_key"))
            .otherwise(pl.col("is_correct"))
            .alias("is_correct"),
        )
    else:
        long_df = long_df.with_columns(
            pl.lit(None).alias("correct_answer_key").cast(pl.Utf8),
            pl.lit(None).alias("correct_answer_text").cast(pl.Utf8),
            pl.lit(None).alias("answer_text").cast(pl.Utf8),
        )

    # Drop unanswered practice trial rows
    n_before = long_df.height
    long_df = long_df.filter(
        ~(
            pl.col("trial").str.starts_with("PRACTICE_")
            & pl.col("final_answer_key").is_null()
        )
    )
    n_dropped = n_before - long_df.height
    if n_dropped > 0:
        logger.debug(f"Dropped {n_dropped} unanswered practice trial row(s).")

    # Sort output file by trial and then slot
    slot_order = {
        "local_question_1": 0,
        "local_question_2": 1,
        "bridging_question_1": 2,
        "bridging_question_2": 3,
        "global_question_1": 4,
        "global_question_2": 5,
    }

    def _trial_sort_key(trial_id: str | None) -> str:
        if trial_id is not None and str(trial_id).startswith("PRACTICE_"):
            try:
                num = int(str(trial_id).split("_")[-1])
                return f"0_{num:03d}"
            except (ValueError, IndexError):
                return "0_000"
        if trial_id is None:
            return "2_unknown"
        try:
            num = int(str(trial_id).split("_")[-1])
            return f"1_{num:03d}"
        except (ValueError, IndexError):
            return f"2_{trial_id!s}"

    long_df = long_df.with_columns(
        pl.col("trial")
        .map_elements(_trial_sort_key, return_dtype=pl.Utf8)
        .alias("_trial_sort"),
        pl.col("slot")
        .map_elements(lambda s: slot_order.get(s, 99), return_dtype=pl.Int32)
        .alias("_slot_sort"),
    )
    long_df = long_df.sort(["_trial_sort", "_slot_sort"])
    long_df = long_df.drop(["_trial_sort", "_slot_sort"])

    # Add component columns
    long_df = long_df.with_columns(
        pl.col("question_id")
        .map_elements(
            lambda qid: q_map.get(qid, {}).get("snippet_number", 1),
            return_dtype=pl.Int32,
        )
        .alias("snippet_number"),
    )

    # Select final columns in desired order
    final_cols = [
        "trial",
        "stimulus",
        "question_id",
        "question_order_version",
        "stimulus_id",
        "snippet_number",
        "condition_number",
        "slot",
        "final_answer_key",
        "answer_text",
        "is_correct",
        "correct_answer_key",
        "correct_answer_text",
        "preliminary_rt_ms",
        "confirmation_rt_ms",
        "preliminary_answer_keys",
        "preliminary_answer_onsets_ms",
        "answer_source",
    ]
    long_df = long_df.select([c for c in final_cols if c in long_df.columns])

    # if session was interrupted fill NAs with value
    if was_session_interrupted:
        long_df = long_df.fill_null("session_interrupted")

    if out_path is None:
        session_dir = question_order_csv.parent.parent
        out_path = session_dir / "results" / "answers.csv"

    write_answers(long_df, out_path)
    return long_df
