import polars as pl

# ---------------------------
# Basic fixation-based counts
# ---------------------------


def compute_total_fixation_count(fix: pl.DataFrame) -> pl.DataFrame:
    """
    Total Fixation Count (TFC):
    Total number of fixations on the word.
    """
    return (
        fix
        .group_by(["trial", "page", "word_idx"])
        .len()
        .rename({"len": "TFC"})
    )


def compute_first_pass_fixation_count(
    fix: pl.DataFrame,
) -> pl.DataFrame:
    """
    First Pass Fixation Count (FPFC):
    Number of fixations in the first pass through a word.
    """
    return (
        fix
        .filter(pl.col("is_first_pass"))
        .group_by(["trial", "page", "word_idx"])
        .len()
        .rename({"len": "FPFC"})
    )


def compute_first_duration(fix: pl.DataFrame) -> pl.DataFrame:
    """
    First Duration (FD):
    Duration of the first fixation on the word, regardless of pass
    """
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
    Sum of fixations from first entering word until first leaving it (first run)
    """
    return (
        fix
        .group_by(["trial", "page", "word_idx", "run_id"])
        .agg(pl.col("duration").sum().alias("run_duration"))
        .sort(["trial", "page", "word_idx", "run_id"])
        .group_by(["trial", "page", "word_idx"])
        .first()
        .select(["trial", "page", "word_idx", "run_duration"])
        .rename({"run_duration": "FRT"})
    )


def compute_first_fixation_duration(fix: pl.DataFrame) -> pl.DataFrame:
    """First fixation during first-pass only"""
    return (
        fix
        .filter(pl.col("is_first_pass"))
        .group_by(["trial", "page", "word_idx"])
        .agg(
            pl.col("duration")
            .sort_by("onset")
            .first()
            .alias("FFD")
        )
    )


def compute_first_pass_reading_time(fix: pl.DataFrame) -> pl.DataFrame:
    """
    First Pass Reading Time (FPRT):
    Sum of all fixations during first pass only
    """
    return (
        fix
        .filter(pl.col("is_first_pass"))
        .group_by(["trial", "page", "word_idx"])
        .agg(pl.col("duration").sum().alias("FPRT"))
    )


def compute_rereading_time(fix: pl.DataFrame) -> pl.DataFrame:
    """
    Rereading Time (RRT):
    Sum of all fixations that are NOT part of first pass
    """
    return (
        fix
        .filter(~pl.col("is_first_pass"))
        .group_by(["trial", "page", "word_idx"])
        .agg(pl.col("duration").sum().alias("RRT"))
    )

# ---------------------------
# Transition-based measures
# ---------------------------


def compute_trc_in_out(fix: pl.DataFrame) -> pl.DataFrame:
    """
    Total Regression Count (TRC):
    Number of regressions into (TRC_in) and out of (TRC_out) the word.
    """
    return (
        fix
        .group_by(["trial", "page", "word_idx"])
        .agg([
            pl.col("is_reg_in").sum().alias("TRC_in"),
            pl.col("is_reg_out").sum().alias("TRC_out"),
        ])
    )


def compute_landing_position(fix: pl.DataFrame) -> pl.DataFrame:
    """
    Landing Position (LP):
    Character index of the first fixation on the word.
    """
    return (
        fix
        .group_by(["trial", "page", "word_idx"])
        .agg(
            pl.col("char_idx")
            .sort_by("onset")
            .first()
            .alias("LP")
        )
    )


def compute_sl_in(fix: pl.DataFrame) -> pl.DataFrame:
    """
    Saccade Length In (SL_in):
    Number of words between the current word and the previous word
    during the first fixation on the word.
    """
    return (
        fix
        .filter(pl.col("is_first_fix"))
        .with_columns((pl.col("word_idx") - pl.col("prev_word")).alias("SL_in"))
        .select(["trial", "page", "word_idx", "SL_in"])
    )


def compute_sl_out(fix: pl.DataFrame) -> pl.DataFrame:
    """
    Saccade Length Out (SL_out):
    Number of words between the current word and the next word
    during the last fixation of the first pass on the word.
    """
    first_run = (
        fix
        .group_by(["trial", "page", "word_idx"])
        .agg(pl.col("run_id").min().alias("first_run"))
    )

    last_fix = (
        fix
        .join(first_run, on=["trial", "page", "word_idx"])
        .filter(pl.col("run_id") == pl.col("first_run"))
        .group_by(["trial", "page", "word_idx"])
        .agg(pl.all().sort_by("onset").last())
    )

    return (
        last_fix
        .with_columns(
            (pl.col("next_word") - pl.col("word_idx"))
            .fill_null(0)
            .alias("SL_out")
        )
        .select(["trial", "page", "word_idx", "SL_out"])
    )

# ---------------------------
# Regression-path measures
# ---------------------------


def compute_rpd_measures(fix: pl.DataFrame) -> pl.DataFrame:
    """
    Regression-Path Duration (RPD):
    Sum of all fixations from first entering the word until
    first leaving it to the right (exiting to a higher word index).
    Both inclusive (RPD_inc) and exclusive (RPD_exc) of fixations on the word.
    Also computes Rereading Before Rightward Transition (RBRT):
    Sum of all fixations on the word before first leaving it to the right.
    """

    fix = fix.collect() if isinstance(fix, pl.LazyFrame) else fix

    def per_group(df: pl.DataFrame) -> pl.DataFrame:
        rows = []

        for w in df["word_idx"].unique().to_list():

            first = (
                df
                .filter((pl.col("word_idx") == w) & (pl.col("is_first_pass")))
                .sort("onset")
                .head(1)
            )

            if first.height == 0:
                rows.append((w, 0, 0, 0))
                continue

            start_onset = first["onset"][0]

            after = df.filter(pl.col("onset") >= start_onset)

            exit_right = (
                after
                .filter(pl.col("word_idx") > w)
                .sort("onset")
                .head(1)
            )

            if exit_right.height > 0:
                stop_onset = exit_right["onset"][0]
                window = after.filter(pl.col("onset") < stop_onset)
            else:
                window = after

            rbrt = window.filter(pl.col("word_idx") == w)["duration"].sum()
            rpd_exc = window.filter(pl.col("word_idx") != w)["duration"].sum()
            rpd_inc = rbrt + rpd_exc

            rows.append((w, rpd_inc, rpd_exc, rbrt))

        return (
            pl.DataFrame(
                rows,
                schema=["word_idx", "RPD_inc", "RPD_exc", "RBRT"],
            )
            .with_columns([
                pl.lit(df["trial"][0]).alias("trial"),
                pl.lit(df["page"][0]).alias("page"),
            ])
        )

    return (
        fix
        .group_by("trial", "page", maintain_order=True)
        .map_groups(per_group)
    )


# ---------------------------
# Word-level table
# ---------------------------


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
    trc = compute_trc_in_out(fix)
    lp = compute_landing_position(fix)
    sl_in = compute_sl_in(fix)
    sl_out = compute_sl_out(fix)
    rpd = compute_rpd_measures(fix)

    return (
        words
        .join(tfc, on=["trial", "page", "word_idx"], how="left")
        .join(fd, on=["trial", "page", "word_idx"], how="left")
        .join(ffd, on=["trial", "page", "word_idx"], how="left")
        .join(fprt, on=["trial", "page", "word_idx"], how="left")
        .join(frt, on=["trial", "page", "word_idx"], how="left")
        .join(rrt, on=["trial", "page", "word_idx"], how="left")
        .join(fpfc, on=["trial", "page", "word_idx"], how="left")
        .join(trc, on=["trial", "page", "word_idx"], how="left")
        .join(lp, on=["trial", "page", "word_idx"], how="left")
        .join(sl_in, on=["trial", "page", "word_idx"], how="left")
        .join(sl_out, on=["trial", "page", "word_idx"], how="left")
        .join(rpd, on=["trial", "page", "word_idx"], how="left")
        .with_columns([
            pl.col("TFC").fill_null(0),
            pl.col("FD").fill_null(0),
            pl.col("FFD").fill_null(0),
            pl.col("FPRT").fill_null(0),
            pl.col("FRT").fill_null(0),
            pl.col("RRT").fill_null(0),
            pl.col("FPFC").fill_null(0),
            pl.col("TRC_in").fill_null(0),
            pl.col("TRC_out").fill_null(0),
            pl.col("LP").fill_null(0),
            pl.col("SL_in").fill_null(0),
            pl.col("SL_out").fill_null(0),
            pl.col("RPD_inc").fill_null(0),
            pl.col("RPD_exc").fill_null(0),
            pl.col("RBRT").fill_null(0),
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
