from __future__ import annotations

import re
from pathlib import Path

import polars as pl


def parse_question_order(csv_path: Path) -> pl.DataFrame:
    """Parse the question order CSV for a session.

    The CSV is expected to have at least the following columns:
    - question_order_version TODO: for what? randomization?
    - local_question_1, local_question_2,
      bridging_question_1, bridging_question_2,
      global_question_1, global_question_2

    Returns a DataFrame with the original columns plus a 1-based "trial" column.
    """
    df = pl.read_csv(csv_path)

    # Add 1-based row index as trial number
    df = df.with_row_index(name="trial")
    df = df.with_columns((pl.col("trial") + 1).alias("trial"))
    return df


def _extract_stimulus_numeric_id(stimulus_name: str) -> str:
    """Extract numeric stimulus id from names like 'Arg_PISACowsMilk_10'.

    Falls back to extracting a trailing integer and raises ValueError if none found.
    """
    m = re.search(r"(\d+)$", stimulus_name)
    if not m:
        raise ValueError(
            f"Could not extract numeric stimulus id from {stimulus_name!r}")
    return m.group(1)


def construct_question_id(stimulus_name: str, order_code: int) -> str:
    """Construct the canonical question id.

    Format: <stimulus_numeric_id><middle><order_code>
    - middle digit is '2' for PISA texts (name contains 'PISA'), otherwise '1'.
    - order_code is a two-digit number among {11, 12, 21, 22, 31, 32}.
    """
    stim_num = _extract_stimulus_numeric_id(stimulus_name)
    middle = "2" if "PISA" in stimulus_name else "1"
    return f"{stim_num}{middle}{order_code}"
