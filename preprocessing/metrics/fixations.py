import polars as pl
import pymovements as pm


def annotate_fixations(
    gaze: pm.Events,
    group_columns: list[str] | None = None,
) -> pl.DataFrame:
    """
    Annotate fixations with visit- and pass-level information.
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

    # new visit = word change
    fix = fix.with_columns(
        (pl.col("word_idx") != pl.col("word_idx").shift())
        .fill_null(True)
        .alias("new_visit")
    )

    # visit id (resets per trial/page)
    fix = fix.with_columns(
        pl.col("new_visit")
        .cast(pl.Int8)
        .cum_sum()
        .over(group_columns)
        .alias("visit_id")
    )

    # pass number per word. Regressions within a word count as same pass
    fix = fix.with_columns(
        (pl.col("visit_id") != pl.col("visit_id").shift())
        .fill_null(True)
        .cast(pl.Int8)
        .cum_sum()
        .over(group_columns + ["word_idx"])
        .alias("pass_n")
    )

    return fix
