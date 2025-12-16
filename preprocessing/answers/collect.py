from __future__ import annotations

from pathlib import Path
from typing import Mapping

import polars as pl

from .parser import parse_question_order, construct_question_id
from .io import write_answers


def _normalize_trial_key(k) -> int:
    """Accept 'trial_7' or 7 or '7' and return int(7).

    TODO: Check if one is standard - if so, remove
    """
    if isinstance(k, int):
        return k
    s = str(k)
    if s.startswith("trial_"):
        s = s.split("_", 1)[1]
    return int(s)


def collect_session_answers(
        question_order_csv: Path,
        stimuli_trial_map: Mapping[str | int, str],
        out_path: Path | None = None,
) -> pl.DataFrame:
    """Assemble per-session question rows from order CSV and a trial->stimulus map.

    Parameters
    ----------
    question_order_csv: Path
        Path to the session's question_order_versions.csv.
    stimuli_trial_map: Mapping
        Maps trial identifiers to stimulus names, e.g., {'trial_1': 'Arg_PISACowsMilk_10', ...}.
        Keys may be 'trial_#', '#', or integers, to be normalized.  TODO: verify
    out_path: Path | None
        If provided, the resulting table is written to this CSV path.
        If None, defaults to `<session_dir>/results/answers.csv`, where
        `<session_dir>` is the parent folder of the `logfiles` directory
        containing the provided CSV. TODO: Change default folder - might use config.py

    Returns
    -------
    pl.DataFrame with columns:
      - trial (string, e.g., 'trial_1')
      - stimulus (string)
      - slot (string, e.g., 'local_question_1')
      - order_code (int: 11,12,21,22,31,32)
      - question_id (string)
      - preliminary_dir, preliminary_ts, final_dir, final_ts (TODO: currently unused, needed?)
    """
    order_df = parse_question_order(question_order_csv)  # Adds 'trial' column to CSV

    # Normalize mapping to int trial index -> stimulus
    norm_map = {_normalize_trial_key(k): v for k, v in stimuli_trial_map.items()}
    # Long format per trial with 6 question slots
    slots = [
        "local_question_1", "local_question_2",
        "bridging_question_1", "bridging_question_2",
        "global_question_1", "global_question_2",
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
        pl.col("trial").map_elements(_stim_for_trial, return_dtype=pl.Utf8).alias(
            "stimulus")
    )

    # Build question_id, ensure trial as 'trial_X'
    long_df = long_df.with_columns(
        pl.col("stimulus").map_elements(
            lambda s: construct_question_id(s, 0), return_dtype=pl.Utf8
        ).alias("_qid_prefix")
    )

    # Replace the trailing '0' with real order_code by reconstructing per-row
    long_df = long_df.with_columns(
        pl.struct(["stimulus", "order_code"]).map_elements(
            lambda st: construct_question_id(st["stimulus"], int(st["order_code"])),
            return_dtype=pl.Utf8,
        ).alias("question_id"),
        pl.col("trial").map_elements(lambda t: f"trial_{int(t)}",
                                     return_dtype=pl.Utf8).alias("trial"),
    ).drop("_qid_prefix")

    # TODO: Placeholder columns for preliminary/final answers
    long_df = long_df.with_columns(
        pl.lit(None).alias("preliminary_dir"),
        pl.lit(None).alias("preliminary_ts"),
        pl.lit(None).alias("final_dir"),
        pl.lit(None).alias("final_ts"),
    )

    # Determine destination if not provided: .../SESSION/results/answers.csv
    if out_path is None:
        # question_order_csv .../SESSION/logfiles/question_order_versions.csv
        session_dir = question_order_csv.parent.parent
        out_path = session_dir / "results" / "answers.csv"

    write_answers(long_df, out_path)

    return long_df
