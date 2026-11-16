"""Conversion between pymovements Duration columns and pipeline milliseconds.

pymovements stores time columns as ``polars.Duration`` (pymovements#1637). The
preprocessing pipeline keeps ``pm.Gaze`` objects in that native dtype and
converts to numeric milliseconds when pymovements tables enter the pipeline's
own, millisecond-based data model (``Session``, reports and plots).
"""

from __future__ import annotations

import polars as pl

__all__ = ["durations_to_ms"]


def durations_to_ms(frame: pl.DataFrame | None) -> pl.DataFrame | None:
    """Return ``frame`` with every ``Duration`` column converted to milliseconds.

    Frames without ``Duration`` columns are returned unchanged, so numeric
    millisecond tables (for example the ones loaded from our own CSVs) pass
    through untouched. Values are converted with fractional millisecond
    precision and narrowed to ``Int64`` when a column contains only whole
    milliseconds, matching pymovements' own ``durations_to_ms`` semantics.

    Parameters
    ----------
    frame : pl.DataFrame | None
        Frame whose ``Duration`` columns should be converted.

    Returns
    -------
    pl.DataFrame | None
        Frame with ``Duration`` columns as numeric milliseconds.
    """
    if frame is None:
        return None

    duration_columns = [
        column
        for column, dtype in frame.schema.items()
        if isinstance(dtype, pl.Duration)
    ]
    if not duration_columns:
        return frame

    frame = frame.with_columns(
        [
            pl.col(column).dt.total_milliseconds(fractional=True).alias(column)
            for column in duration_columns
        ]
    )

    # Narrow to Int64 when every value is a whole millisecond, so CSV output and
    # report formatting stay identical to the pre-Duration behaviour.
    for column in duration_columns:
        all_whole = frame.select(pl.col(column).round().eq(pl.col(column)).all()).item()
        if all_whole:
            frame = frame.with_columns(pl.col(column).cast(pl.Int64))

    return frame
