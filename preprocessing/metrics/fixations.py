import polars as pl
import pymovements as pm


def annotate_fixations(
    gaze: pm.Events,
    group_columns: list[str] | None = None,
) -> pl.DataFrame:
    """
    Annotate fixations with visit- and Tobii-compatible pass-level information.

    Definitions:
    - visit_id: contiguous fixations on the same word
    - pass_n:
        NEW VISIT on word w:
            IF w not visited before:
                IF coming from left:
                    pass = 1
                ELSE (coming from right / after regression):
                    pass = global_max_pass + 1

            ELSE (word visited before):
                pass = last_pass[w] + 1
    """
    if group_columns is None:
        group_columns = ["trial", "stimulus", "page"]

    fix = (
        gaze
        .filter(
            (pl.col("name") == "fixation") &
            (pl.col("word_idx").is_not_null())
        )
        .with_row_count("fixation_id")
        .sort(group_columns + ["onset"])
    )

    # ---- visits ----
    fix = fix.with_columns(
        (pl.col("word_idx") != pl.col("word_idx").shift())
        .fill_null(True)
        .alias("new_visit")
    )

    fix = fix.with_columns(
        pl.col("new_visit")
        .cast(pl.Int8)
        .cum_sum()
        .over(group_columns)
        .alias("visit_id")
    )

    # ---- assign passes ----
    def assign_passes(df: pl.DataFrame) -> pl.DataFrame:
        df = df.sort("onset")

        visited = set()
        last_pass = {}
        global_max_pass = 0

        pass_values = []
        prev_word = None
        current_pass = None

        for row in df.iter_rows(named=True):
            w = row["word_idx"]

            # detect new visit
            if w != prev_word:
                if w not in visited:
                    # first-ever visit to this word
                    if prev_word is None or w > prev_word:
                        # entered from left (normal reading)
                        current_pass = 1
                    else:
                        # entered from right (after regression)
                        current_pass = global_max_pass + 1
                else:
                    # revisit of previously seen word
                    current_pass = last_pass[w] + 1

                visited.add(w)
                last_pass[w] = current_pass
                global_max_pass = max(global_max_pass, current_pass)

            pass_values.append(current_pass)
            prev_word = w

        return df.with_columns(pl.Series("pass_n", pass_values))

    fix = (
        fix
        .group_by(*group_columns, maintain_order=True)
        .map_groups(assign_passes)
    )

    return fix
