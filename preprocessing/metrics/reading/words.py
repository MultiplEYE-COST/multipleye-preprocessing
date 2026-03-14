import polars as pl


def all_tokens_from_aois(
    aois: pl.DataFrame,
    trial: str = None,
) -> pl.DataFrame:
    """
    Returns every AOI token on the page:
    words, spaces, punctuation — everything that has a word_idx.
    """
    aois = (
        aois.with_columns([pl.lit(trial).cast(pl.Utf8).alias("trial")])
        if "trial" not in aois.columns
        else aois
    )

    return aois.select(["trial", "page", "word_idx", "word"]).unique().sort("word_idx")


def mark_skipped_tokens(
    all_tokens: pl.DataFrame, fixations: pl.DataFrame
) -> pl.DataFrame:
    fixated_tokens = (
        fixations.select(["trial", "page", "word_idx"])
        .drop_nulls()
        .unique()
        .with_columns(pl.lit(1).alias("fixated"))
    )

    out = all_tokens.join(
        fixated_tokens,
        on=["trial", "page", "word_idx"],
        how="left",
    )

    return out.with_columns(
        pl.when(pl.col("fixated").is_null())
        .then(1)  # not fixated → skipped
        .otherwise(0)  # fixated → not skipped
        .cast(pl.Int8)
        .alias("skipped")
    ).drop("fixated")
