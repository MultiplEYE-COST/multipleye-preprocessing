from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import polars as pl

from .parser import parse_question_order, construct_question_id
from .io import write_answers
from ..data_collection.stimulus import Stimulus


def _normalize_trial_key(k) -> int:
    """Accept 'trial_7' or 7 or '7' and return int(7)."""
    if isinstance(k, int):
        return k
    s = str(k)
    if s.startswith("trial_"):
        s = s.split("_", 1)[1]
    return int(s)


def collect_session_answers(
    question_order_csv: Path,
    stimuli_trial_map: Mapping[str | int, str],
    stimuli: Sequence[Stimulus] | None = None,
    parsed_answers: pl.DataFrame | None = None,
    out_path: Path | None = None,
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
    """
    order_df = parse_question_order(question_order_csv)  # Adds 'trial' column to CSV

    # Normalize mapping to int trial index -> stimulus
    norm_map = {_normalize_trial_key(k): v for k, v in stimuli_trial_map.items()}
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

    long_df = pl.concat(per_slot_frames).with_columns(
        pl.col("trial").cast(pl.Int64),
        pl.col("order_code").cast(pl.Int64),
    )

    # Add stimulus name and construct canonical question_id
    def _stim_for_trial(trial_idx: int) -> str:
        if trial_idx not in norm_map:
            raise KeyError(f"No stimulus mapping for trial {trial_idx}")
        return norm_map[trial_idx]

    long_df = long_df.with_columns(
        pl.col("trial")
        .map_elements(_stim_for_trial, return_dtype=pl.Utf8)
        .alias("stimulus")
    )

    # Build question_id, ensure trial as 'trial_X'
    long_df = long_df.with_columns(
        pl.col("trial")
        .map_elements(lambda t: f"trial_{int(t)}", return_dtype=pl.Utf8)
        .alias("trial_id")
    )

    long_df = long_df.with_columns(
        pl.struct(["stimulus", "order_code"])
        .map_elements(
            lambda st: construct_question_id(st["stimulus"], int(st["order_code"])),
            return_dtype=pl.Utf8,
        )
        .alias("question_id"),
        pl.col("trial")
        .map_elements(lambda t: f"trial_{int(t)}", return_dtype=pl.Utf8)
        .alias("trial"),
    )

    if parsed_answers is not None:
        # Merge parsed answers by (trial_id, question_id)
        long_df = long_df.join(
            parsed_answers, on=["trial_id", "question_id"], how="left"
        )

        # Compute derived columns
        long_df = long_df.with_columns(
            # final_rt_ms: onset -> final confirmation
            (pl.col("final_confirmation_ts") - pl.col("question_onset_ts")).alias(
                "final_rt_ms"
            ),
            # decision_rt_ms: first preliminary -> final confirmation
            (
                pl.col("final_confirmation_ts") - pl.col("preliminary_tss").list.get(0)
            ).alias("decision_rt_ms"),
            # answer_changed: preliminary_keys non-empty and last one != final_answer_key
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
        # Add null columns if no parsed answers
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
                # In Stimulus.load(), q.id is extracted from item_id.split("_")[-1]
                # item_id is something like Lit_MagicMountain_6_11
                # so q.id is "11", "12", "21", etc. (the order_code)
                try:
                    q_order_code = int(q.id)
                except (ValueError, TypeError):
                    continue

                q_id = construct_question_id(stim.name, q_order_code)
                q_map[q_id] = {
                    "correct_answer_key": "target_key",  # Always target_key for correct
                    "correct_answer_text": q.target,
                }

        def _get_correct_info(q_id: str, field: str) -> str | None:
            return q_map.get(q_id, {}).get(field)

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
    else:
        long_df = long_df.with_columns(
            pl.lit(None).alias("correct_answer_key").cast(pl.Utf8),
            pl.lit(None).alias("correct_answer_text").cast(pl.Utf8),
        )

    # Select final columns in desired order
    final_cols = [
        "trial",
        "stimulus",
        "slot",
        "order_code",
        "question_id",
        "final_answer_key",
        "is_correct",
        "correct_answer_key",
        "correct_answer_text",
        "final_rt_ms",
        "decision_rt_ms",
        "answer_changed",
    ]
    long_df = long_df.select([c for c in final_cols if c in long_df.columns])

    # Determine destination if not provided: .../SESSION/results/answers.csv
    if out_path is None:
        # question_order_csv .../SESSION/logfiles/question_order_versions.csv
        session_dir = question_order_csv.parent.parent
        out_path = session_dir / "results" / "answers.csv"

    write_answers(long_df, out_path)

    return long_df
