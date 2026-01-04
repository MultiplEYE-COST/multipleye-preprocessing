import polars as pl


def all_words_from_aois(
    aois: pl.DataFrame,
    page: str,
) -> pl.DataFrame:
    return (
        aois
        .filter(pl.col("page") == page)
        .filter(pl.col("word").is_not_null() & (pl.col("word") != ""))
        .select(["page", "word_idx", "word"])
        .unique()
        .sort(["word_idx"])
    )


def find_skipped_words(
    all_words: pl.DataFrame,
    fixations: pl.DataFrame,
) -> pl.DataFrame:
    fixated_word_ids = fixations["word_idx"].unique()

    return (
        all_words
        .with_columns(
            (~pl.col("word_idx").is_in(fixated_word_ids))
            .cast(pl.Int8)
            .alias("skipped")
        )
    )
