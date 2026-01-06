import polars as pl


def compute_total_fixation_count(fix: pl.DataFrame) -> pl.DataFrame:
    return (
        fix
        .group_by(["trial", "page", "word_idx"])
        .len()
        .rename({"len": "TFC"})
    )


def compute_first_pass_fixation_count(
    fix: pl.DataFrame,
) -> pl.DataFrame:
    return (
        fix
        .filter(pl.col("pass_n") == 1)
        .group_by(["trial", "page", "word_idx"])
        .len()
        .rename({"len": "FPFC"})
    )


def compute_first_duration(fix: pl.DataFrame) -> pl.DataFrame:
    return (
        fix
        .group_by(["trial", "page", "word_idx"])
        .agg(
            pl.col("duration")
            .sort_by("onset")
            .first()
            .alias("FD")
        )
    )


def compute_first_reading_time(fix: pl.DataFrame) -> pl.DataFrame:
    """
    First Reading Time (FRT):
    Sum of durations of all fixations in the first visit to a word.
    """
    return (
        fix
        .group_by(["trial", "page", "word_idx", "visit_id"])
        .agg(pl.col("duration").sum().alias("visit_duration"))
        .sort(["trial", "page", "word_idx", "visit_id"])
        .group_by(["trial", "page", "word_idx"])
        .first()
        .select(["trial", "page", "word_idx", "visit_duration"])
        .rename({"visit_duration": "FRT"})
    )


def compute_first_fixation_duration(fix: pl.DataFrame) -> pl.DataFrame:
    return (
        fix
        .filter(pl.col("pass_n") == 1)
        .group_by(["trial", "page", "word_idx"])
        .agg(
            pl.col("duration")
            .sort_by("onset")
            .first()
            .alias("FFD")
        )
    )


def compute_first_pass_reading_time(fix: pl.DataFrame) -> pl.DataFrame:
    return (
        fix
        .filter(pl.col("pass_n") == 1)
        .group_by(["trial", "page", "word_idx"])
        .agg(pl.col("duration").sum().alias("FPRT"))
    )


def compute_rereading_time(fix: pl.DataFrame) -> pl.DataFrame:
    return (
        fix
        .filter(pl.col("pass_n") > 1)
        .group_by(["trial", "page", "word_idx"])
        .agg(pl.col("duration").sum().alias("RRT"))
    )


def build_word_level_table(
    words: pl.DataFrame,
    fix: pl.DataFrame,
) -> pl.DataFrame:

    tfc = compute_total_fixation_count(fix)
    fd = compute_first_duration(fix)
    ffd = compute_first_fixation_duration(fix)
    fprt = compute_first_pass_reading_time(fix)
    frt = compute_first_reading_time(fix)
    rrt = compute_rereading_time(fix)
    fpfc = compute_first_pass_fixation_count(fix)

    return (
        words
        .join(tfc, on=["trial", "page", "word_idx"], how="left")
        .join(fd, on=["trial", "page", "word_idx"], how="left")
        .join(ffd, on=["trial", "page", "word_idx"], how="left")
        .join(fprt, on=["trial", "page", "word_idx"], how="left")
        .join(frt, on=["trial", "page", "word_idx"], how="left")
        .join(rrt, on=["trial", "page", "word_idx"], how="left")
        .join(fpfc, on=["trial", "page", "word_idx"], how="left")
        .with_columns([
            pl.col("TFC").fill_null(0),
            pl.col("FD").fill_null(0),
            pl.col("FFD").fill_null(0),
            pl.col("FPRT").fill_null(0),
            pl.col("FRT").fill_null(0),
            pl.col("RRT").fill_null(0),
            pl.col("FPFC").fill_null(0),
        ])

        # ---- derived measures ----
        .with_columns([
            # total fixation time
            (pl.col("FPRT") + pl.col("RRT")).alias("TFT"),

            # binary indicators
            (pl.col("FPRT") > 0).cast(pl.Int8).alias("FPF"),
            (pl.col("RRT") > 0).cast(pl.Int8).alias("RR"),

            # single-fixation duration
            pl.when(pl.col("FPFC") == 1)
              .then(pl.col("FFD"))
              .otherwise(0)
              .alias("SFD"),
        ])
    )
