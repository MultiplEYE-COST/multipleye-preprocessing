import polars as pl
import pymovements as pm


def annotate_fixations(
    gaze_events: pl.DataFrame,
    group_columns: list[str] | None = None,
) -> pl.DataFrame:
    """
    Annotate fixations with run- and pass-level information.

    Definitions:
    - run_id: contiguous fixations on the same word
    - first-pass: a new run (visit) to a word that starts from the left and
      the word has not been exited before
    """
    if group_columns is None:
        group_columns = ["trial", "stimulus", "page"]

    fix = (
        gaze_events
        .filter(
            (pl.col("name") == "fixation") &
            (pl.col("word_idx").is_not_null())
        )
        .with_row_count("fixation_id")
        .sort(group_columns + ["onset"])
    )

    # ----  identifies runs ----
    fix = fix.with_columns(
        (pl.col("word_idx") != pl.col("word_idx").shift().over(group_columns))
        .fill_null(True)
        .alias("new_run")
    )

    fix = fix.with_columns(
        pl.col("new_run")
        .cast(pl.Int8)
        .cum_sum()
        .over(group_columns)
        .alias("run_id")
    )

    # -------------------------------------------------
    # Neighbouring words (for regression detection)
    # -------------------------------------------------
    fix = fix.with_columns([
        pl.col("word_idx").shift().over(group_columns).alias("prev_word"),
        pl.col("word_idx").shift(-1).over(group_columns).alias("next_word"),
    ])

    fix = fix.with_columns([
        (pl.col("word_idx") - pl.col("prev_word")).alias("delta_in"),
        (pl.col("next_word") - pl.col("word_idx")).alias("delta_out"),
    ])

    fix = fix.with_columns([
        (pl.col("delta_in") < 0).alias("is_reg_in"),
        (pl.col("delta_out") < 0).alias("is_reg_out"),
    ])

    # -------------------------------------------------
    # First fix on word
    # -------------------------------------------------
    fix = fix.with_columns(
        pl.col("word_idx")
        .cum_count()
        .over(group_columns + ["word_idx"])
        .eq(1)
        .alias("is_first_fix")
    )

    # -------------------------------------------------
    # First-pass flag (word-level first reading episode)
    # -------------------------------------------------

    def mark_first_pass(df: pl.DataFrame) -> pl.DataFrame:
        """
        Mark fixations that belong to the first-pass reading of a word.

        First-pass is defined at the *run* level:
        - A run is first-pass if:
            1. It is the first time the reader enters the word, AND
            2. The word is entered from the left (forward reading direction)

        All fixations within such a run are labeled `is_first_pass = True`.
        Any later revisit to the word, or entries from the right (regressions),
        are not part of first-pass.
        """
        df = df.sort("onset")

        word_has_been_exited: dict[int, bool] = {}
        first_pass_flags: list[bool] = []

        prev_word = None
        prev_run = None
        current_run_is_first_pass = False  # state carried within a run

        for row in df.iter_rows(named=True):
            w = row["word_idx"]
            run = row["run_id"]
            prev_w = row["prev_word"]

            new_run = run != prev_run

            if new_run:
                entered_from_left = prev_w is None or w > prev_w

                current_run_is_first_pass = (
                    entered_from_left and not word_has_been_exited.get(
                        w, False)
                )

            # All fixations in the same run inherit the same label
            first_pass_flags.append(current_run_is_first_pass)

            # If we moved away from a word, mark that word as "exited"
            if prev_word is not None and w != prev_word:
                word_has_been_exited[prev_word] = True

            prev_word = w
            prev_run = run

        return df.with_columns(pl.Series("is_first_pass", first_pass_flags))

    fix = (
        fix
        .group_by(*group_columns, maintain_order=True)
        .map_groups(mark_first_pass)
    )

    return fix.select([
        "trial", "page", "fixation_id", "onset", "word_idx", "char_idx", "char",
        "run_id", "is_first_pass", "duration", "word", "prev_word", "next_word", "is_reg_in", "is_reg_out", "is_first_fix"
    ])
