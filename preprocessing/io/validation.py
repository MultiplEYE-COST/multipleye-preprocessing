"""Validation helpers for parsed ASC data."""

import logging

import polars as pl
import pymovements as pm

logger = logging.getLogger(__name__)

_START_PREFIX = "start_recording_"
_STOP_PREFIX = "stop_recording_"


def find_message_order_conflicts(
    messages: pl.DataFrame | None,
) -> list[tuple[float | int, list[str]]]:
    """Find same-timestamp recording messages in the wrong order.

    Parameters
    ----------
    messages : pl.DataFrame | None
        Parsed ASC messages with ``time`` and ``content`` columns.

    Returns
    -------
    list[tuple[float | int, list[str]]]
        Timestamps and ordered recording messages where a ``start_recording_*``
        message occurs before a ``stop_recording_*`` message.
    """
    if messages is None or messages.is_empty():
        return []

    messages_by_time: dict[float | int, list[str]] = {}
    for row in messages.iter_rows(named=True):
        timestamp = row.get("time")
        content = row.get("content")
        if timestamp is None or content is None:
            continue
        if not content.startswith((_START_PREFIX, _STOP_PREFIX)):
            continue
        messages_by_time.setdefault(timestamp, []).append(content)

    conflicts: list[tuple[float | int, list[str]]] = []
    for timestamp, contents in messages_by_time.items():
        start_positions = [
            index
            for index, content in enumerate(contents)
            if content.startswith(_START_PREFIX)
        ]
        stop_positions = [
            index
            for index, content in enumerate(contents)
            if content.startswith(_STOP_PREFIX)
        ]
        if (
            start_positions
            and stop_positions
            and min(start_positions) < max(stop_positions)
        ):
            conflicts.append((timestamp, contents))

    return conflicts


def find_low_sample_pages(
    samples: pl.DataFrame | None,
    trial_columns: list[str],
    min_samples: int = 2,
) -> pl.DataFrame:
    """Find non-null trial/page groups with fewer than ``min_samples`` samples.

    Parameters
    ----------
    samples : pl.DataFrame | None
        Parsed ASC samples.
    trial_columns : list[str]
        Columns that identify a trial/page group.
    min_samples : int, optional
        Minimum expected number of samples per group. Defaults to 2.

    Returns
    -------
    pl.DataFrame
        One row per low-sample group with a ``sample_count`` column.
    """
    if samples is None or samples.is_empty() or not trial_columns:
        return pl.DataFrame()

    required_columns = {"trial", "page", *trial_columns}
    if missing_columns := required_columns - set(samples.columns):
        logger.debug(
            "Skipping low-sample page validation, missing columns: %s",
            sorted(missing_columns),
        )
        return pl.DataFrame()

    return (
        samples.filter(pl.col("trial").is_not_null() & pl.col("page").is_not_null())
        .group_by(trial_columns)
        .agg(pl.len().alias("sample_count"))
        .filter(pl.col("sample_count") < min_samples)
        .sort("sample_count")
    )


def validate_asc_parsing(
    gaze: pm.Gaze, session_id: str | None = None
) -> dict[str, int]:
    """Warn about ASC parsing problems that can drop samples or break detection.

    Parameters
    ----------
    gaze : pm.Gaze
        Parsed gaze object with samples and, optionally, messages.
    session_id : str | None, optional
        Session identifier used in warning messages.

    Returns
    -------
    dict[str, int]
        Counts of message-order conflicts and low-sample pages.
    """
    session_suffix = f" in session {session_id}" if session_id else ""

    conflicts = find_message_order_conflicts(getattr(gaze, "messages", None))
    for timestamp, contents in conflicts:
        logger.warning(
            "ASC message order conflict%s at %s: start_recording_* precedes "
            "stop_recording_* in the same timestamp. This can clear trial/page "
            "for following samples. Messages: %s",
            session_suffix,
            timestamp,
            contents,
        )

    trial_columns = getattr(gaze, "trial_columns", None) or [
        "trial",
        "stimulus",
        "page",
    ]
    low_sample_pages = find_low_sample_pages(
        getattr(gaze, "samples", None),
        trial_columns,
    )
    for row in low_sample_pages.iter_rows(named=True):
        sample_count = row["sample_count"]
        key_values = ", ".join(
            f"{key}={value!r}" for key, value in row.items() if key != "sample_count"
        )
        logger.warning(
            "ASC page has only %s sample(s)%s: %s. Groups with fewer than 2 "
            "samples can break saccade detection.",
            sample_count,
            session_suffix,
            key_values,
        )

    return {
        "message_order_conflicts": len(conflicts),
        "low_sample_pages": low_sample_pages.height,
    }
