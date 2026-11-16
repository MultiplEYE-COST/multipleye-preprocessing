"""Helpers for working with pymovements time columns.

pymovements stores time columns as ``polars.Duration`` since version 0.29
(pymovements#1637). Iterating such a column yields ``datetime.timedelta``
objects instead of numbers, so code that needs milliseconds has to convert
explicitly with :meth:`polars.Expr.dt.total_milliseconds`.

The preprocessing pipeline keeps the ``Duration`` dtype in ``pm.Gaze`` objects
and converts only where it consumes time values as milliseconds, for example
when parsing answers, computing session statistics or writing reports.
"""

from __future__ import annotations

import polars as pl

__all__ = [
    "time_column_to_ms",
    "time_columns_to_ms",
]


def time_column_to_ms(frame: pl.DataFrame, column: str = "time") -> pl.Expr:
    """Return an expression that yields ``column`` in milliseconds.

    ``Duration`` columns are converted with
    :meth:`polars.Expr.dt.total_milliseconds`. Numeric columns are returned
    unchanged, so both pymovements frames and numeric millisecond frames are
    supported.

    Parameters
    ----------
    frame : pl.DataFrame
        Frame containing ``column``.
    column : str
        Name of the time column. Default is ``"time"``.

    Returns
    -------
    pl.Expr
        Expression yielding the column in milliseconds.
    """
    if frame.schema.get(column) == pl.Duration:
        return pl.col(column).dt.total_milliseconds()
    return pl.col(column)


def time_columns_to_ms(
    frame: pl.DataFrame | None,
    columns: list[str],
) -> pl.DataFrame | None:
    """Return ``frame`` with the given time columns converted to milliseconds.

    Parameters
    ----------
    frame : pl.DataFrame | None
        Frame to convert. ``None`` is returned unchanged.
    columns : list of str
        Time column names. Columns missing from ``frame`` are ignored.

    Returns
    -------
    pl.DataFrame | None
        Frame with ``Duration`` time columns converted to milliseconds.
    """
    if frame is None:
        return None

    expressions = [
        time_column_to_ms(frame, column).alias(column)
        for column in columns
        if column in frame.columns
    ]
    if not expressions:
        return frame
    return frame.with_columns(expressions)
