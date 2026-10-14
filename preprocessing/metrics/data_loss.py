"""Vectorized, pymovements-compatible data-loss computation.

The three data-loss ratios the pipeline needs (session, per page, per trial) are
derived from a single vectorized pass over the samples. This replaces three
separate ``pymovements.measure.data_loss`` calls, each of which runs a Python
``map_elements`` over every sample.

The fast path is only used for float position columns; any other inner dtype
falls back to ``pymovements.measure.data_loss`` to preserve its exact semantics.

REVERT / follow-up
------------------
This is a workaround for a pymovements performance issue and should be revisited
once https://github.com/pymovements/pymovements/pull/1772
("perf: vectorise the invalid-value check used by ``null_ratio`` and
``data_loss``") has landed and is released. At that point ``data_loss`` no longer
uses ``map_elements`` and this module can be dropped: in
``preprocessing/scripts/run_preprocessing.py`` call
``pm.measure.data_loss("pixel", sampling_rate=sr, unit="ratio")`` directly again
for the session, per-page and per-trial values (the three-pass cost then becomes
negligible). The only thing lost by reverting is the 3 -> 1 pass deduplication,
which is minor once the upstream fix is in.
"""

from __future__ import annotations

import polars as pl
import pymovements as pm


def compute_data_loss(
    samples: pl.DataFrame,
    *,
    sampling_rate: float,
    page_columns: list[str],
    trial_columns: list[str],
    pixel_column: str = "pixel",
    time_column: str = "time",
) -> tuple[float, pl.DataFrame, pl.DataFrame]:
    """Compute session, per-page and per-trial data-loss ratios in one pass.

    Mirrors ``pymovements.measure.data_loss`` (with
    ``sampling_rate``/``unit='ratio'``): expected samples are derived from the
    group's time span and sampling rate, and lost samples are missing rows plus
    rows with an invalid position.

    Parameters
    ----------
    samples : pl.DataFrame
        Sample data.
    sampling_rate : float
        Expected sampling rate in Hz.
    page_columns : list[str]
        Columns identifying a page (e.g. ``["trial", "stimulus", "page"]``).
    trial_columns : list[str]
        Columns identifying a trial (e.g. ``["trial", "stimulus"]``).
    pixel_column : str
        Position column to check for invalid values.
    time_column : str
        Timestamp column.

    Returns
    -------
    tuple[float, pl.DataFrame, pl.DataFrame]
        Session ratio, per-page table (``page_columns`` + ``data_loss_ratio``)
        and per-trial table (``trial_columns`` + ``data_loss_ratio``).
    """
    dtype = samples.schema[pixel_column]
    if not _supports_fast_path(dtype):
        return _pymovements_data_loss(
            samples,
            sampling_rate=sampling_rate,
            page_columns=page_columns,
            trial_columns=trial_columns,
            pixel_column=pixel_column,
        )

    frame = samples.with_columns(
        _invalid_mask(pixel_column, dtype).cast(pl.Int64).alias("_invalid")
    )
    aggregations = [
        pl.col(time_column).min().alias("_t0"),
        pl.col(time_column).max().alias("_t1"),
        pl.len().alias("_n"),
        pl.col("_invalid").sum().alias("_inv"),
    ]
    ratio = _ratio_expr(sampling_rate)

    def _grouped(columns: list[str]) -> pl.DataFrame:
        return (
            frame.group_by(columns)
            .agg(aggregations)
            .with_columns(ratio)
            .select([*columns, "data_loss_ratio"])
        )

    per_page = _grouped(page_columns)
    per_trial = _grouped(trial_columns)
    total = (
        frame.select(aggregations).with_columns(ratio).select("data_loss_ratio").item()
    )

    return total, per_page, per_trial


def _supports_fast_path(dtype: pl.DataType) -> bool:
    if dtype in (pl.Float32, pl.Float64):
        return True
    return isinstance(dtype, pl.List) and dtype.inner in (pl.Float32, pl.Float64)


def _invalid_mask(column: str, dtype: pl.DataType) -> pl.Expr:
    expression = pl.col(column)
    if isinstance(dtype, pl.List):
        return (
            expression.is_null()
            | expression.list.eval(
                pl.element().is_null()
                | pl.element().is_nan()
                | pl.element().is_infinite()
            ).list.any()
        )
    return expression.is_null() | expression.is_nan() | expression.is_infinite()


def _ratio_expr(sampling_rate: float) -> pl.Expr:
    expected = ((pl.col("_t1") - pl.col("_t0")) * sampling_rate / 1000).floor().cast(
        pl.Int64
    ) + 1
    lost = pl.max_horizontal(expected - pl.col("_n"), pl.lit(0)) + pl.col("_inv")
    return (lost.cast(pl.Float64) / expected.cast(pl.Float64)).alias("data_loss_ratio")


def _pymovements_data_loss(
    samples: pl.DataFrame,
    *,
    sampling_rate: float,
    page_columns: list[str],
    trial_columns: list[str],
    pixel_column: str,
) -> tuple[float, pl.DataFrame, pl.DataFrame]:
    measure = pm.measure.data_loss(
        pixel_column, sampling_rate=sampling_rate, unit="ratio"
    )
    total = samples.select(measure).item()
    per_page = samples.group_by(page_columns).agg(measure)
    per_trial = samples.group_by(trial_columns).agg(measure)
    return total, per_page, per_trial
