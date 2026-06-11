from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import polars as pl

from .parser import parse_question_order, construct_question_id
from .io import write_answers
from ..data_collection.stimulus import Stimulus
from ..utils.logging import get_logger


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
) -> pl.DataFrame:
    """Assemble per-session question rows from order CSV and a trial->stimulus map.

    Parameters
    ----------
    question_order_csv: Path
        Path to the session's question_order_versions.csv.
    stimuli_trial_map: Mapping
        Maps trial identifiers to stimulus names, e.g., {'trial_1': 'Arg_PISACowsMilk_10', ...}.
    stimuli: Sequence[Stimulus] | None
        List of Stimulus objects to look up correct answer texts.
    parsed_answers: pl.DataFrame | None
        DataFrame with parsed answers from ASC messages or logfile.
    out_path: Path | None
        If provided, the resulting table is written to this CSV path.
    source: str
        The source of the parsed answers, e.g., 'asc' or 'logfile'.
    completed_stimuli_ids: Sequence[int] | None
        List of stimulus numeric IDs in the order they were completed.

    Returns
    -------
    pl.DataFrame with columns:
      - trial (string, e.g., 'trial_1')
      - stimulus (string)
      - slot (string, e.g., 'local_question_1')
      - order_code (int: 11,12,21,22,31,32)
      - question_id (string)
      - final_answer_key (string)
      - is_correct (bool)
      - correct_answer_key (string)
      - correct_answer_text (string)
      - final_rt_ms (float)
      - decision_rt_ms (float)
      - answer_changed (bool)
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
    trial_mapping = {}
    for i, key in enumerate(sorted_keys, start=1):
        trial_mapping[i] = key

    # stim_id_mapping: actual trial identifier -> stimulus numeric ID
    stim_id_map = {}
    if completed_stimuli_ids and len(completed_stimuli_ids) == len(sorted_keys):
        for key, s_id in zip(sorted_keys, completed_stimuli_ids):
            stim_id_map[key] = s_id
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
            pl.lit(slot).alias("slot"),
            pl.col(slot).alias("order_code"),
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

    def _safe_construct_question_id(
        stim_name: str, order_code: int, trial_key: any
    ) -> str | None:
        stim_id = stim_id_map.get(trial_key)
        try:
            return construct_question_id(stim_name, order_code, stimulus_id=stim_id)
        except (ValueError, KeyError, AttributeError):
            return None

    long_df = long_df.with_columns(
        pl.col("trial")
        .map_elements(_stim_for_trial, return_dtype=pl.Utf8)
        .alias("stimulus"),
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

        # Compute derived columns
        long_df = long_df.with_columns(
            (pl.col("final_confirmation_ts") - pl.col("question_onset_ts")).alias(
                "final_rt_ms"
            ),
            (
                pl.col("final_confirmation_ts") - pl.col("preliminary_tss").list.get(0)
            ).alias("decision_rt_ms"),
            pl.coalesce(
                [
                    pl.when(pl.col("preliminary_keys").list.len() > 0)
                    .then(
                        pl.col("preliminary_keys").list.get(-1)
                        != pl.col("final_answer_key")
                    )
                    .otherwise(pl.lit(False)),
                    pl.lit(False),
                ]
            ).alias("answer_changed"),
        )
    else:
        long_df = long_df.with_columns(
            pl.lit(None).alias("final_answer_key").cast(pl.Utf8),
            pl.lit(None).alias("is_correct").cast(pl.Boolean),
            pl.lit(None).alias("final_rt_ms").cast(pl.Float64),
            pl.lit(None).alias("decision_rt_ms").cast(pl.Float64),
            pl.lit(None).alias("answer_changed").cast(pl.Boolean),
        )

    # Add correct answers from stimuli objects
    if stimuli:
        q_map = {}
        for stim in stimuli:
            for q in stim.questions:
                try:
                    q_order_code = int(str(q.id)[-2:])
                except (ValueError, TypeError):
                    continue

                # For Stimulus objects, the numeric ID is already in stim.id
                q_id = construct_question_id(
                    stim.name, q_order_code, stimulus_id=stim.id
                )
                if q_id:
                    q_map[q_id] = {
                        "correct_answer_key": "target_key",
                        "correct_answer_text": q.target,
                        "options": {
                            "target_key": q.target,
                            "distractor_a_key": q.distractor_a,
                            "distractor_b_key": q.distractor_b,
                            "distractor_c_key": q.distractor_c,
                        },
                    }

        def _get_correct_info(q_id: str, field: str) -> str | any | None:
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
            pl.struct(["question_id", "final_answer_key"])
            .map_elements(
                lambda x: _get_answer_text(x["question_id"], x["final_answer_key"]),
                return_dtype=pl.Utf8,
            )
            .alias("answer_text"),
        )
    else:
        long_df = long_df.with_columns(
            pl.lit(None).alias("correct_answer_key").cast(pl.Utf8),
            pl.lit(None).alias("correct_answer_text").cast(pl.Utf8),
            pl.lit(None).alias("answer_text").cast(pl.Utf8),
        )

    # Sort output file by trial and then slot
    slot_order = {
        "local_question_1": 0,
        "local_question_2": 1,
        "bridging_question_1": 2,
        "bridging_question_2": 3,
        "global_question_1": 4,
        "global_question_2": 5,
    }

    def _trial_sort_key(trial_id: str) -> str:
        if trial_id.startswith("PRACTICE_"):
            try:
                num = int(trial_id.split("_")[-1])
                return f"0_{num:03d}"
            except (ValueError, IndexError):
                return "0_000"
        try:
            num = int(trial_id.split("_")[-1])
            return f"1_{num:03d}"
        except (ValueError, IndexError):
            return f"2_{trial_id}"

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

    # Select final columns in desired order
    final_cols = [
        "trial",
        "stimulus",
        "slot",
        "order_code",
        "question_id",
        "final_answer_key",
        "answer_text",
        "is_correct",
        "correct_answer_key",
        "correct_answer_text",
        "final_rt_ms",
        "decision_rt_ms",
        "answer_changed",
        "answer_source",
    ]
    long_df = long_df.select([c for c in final_cols if c in long_df.columns])

    if out_path is None:
        session_dir = question_order_csv.parent.parent
        out_path = session_dir / "results" / "answers.csv"

    write_answers(long_df, out_path)
    return long_df
