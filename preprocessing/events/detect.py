"""Event detection functions."""

import logging

import numpy as np
import polars as pl
from pymovements.events.detection.microsaccades import compute_threshold

from ..config import settings
from ..events.properties import compute_event_properties

logger = logging.getLogger(__name__)

_MINIMUM_SACCADE_THRESHOLD = 1e-10
_GROUP_ROW_INDEX_COLUMN = "__saccade_group_row_index"
_MAX_LOGGED_GROUPS = 10


def detect_fixations(
    gaze,
    method: str | None = None,
    minimum_duration: int | None = None,
    velocity_threshold: float | None = None,
    dispersion_threshold: float | None = None,
) -> None:
    """
    This function applies a fixation detection method and then computes
    descriptive properties (such as fixation location).

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object containing gaze samples and trial metadata.

    method : {"ivt", "idt"} | None, optional
        Event detection method:
        - ``"ivt"`` (Velocity-Threshold Identification):
          Samples are classified as fixations when their velocity is below
          ``velocity_threshold`` degrees/second. Consecutive samples are
          merged into fixation events. This is the default method.
        - ``"idt"`` (Dispersion-Threshold Identification):
          Groups points that remain within a spatial dispersion window for
          at least ``minimum_duration`` ms.
        Defaults to ``settings.FIXATION_METHOD``.

    minimum_duration : int | None, optional
        Minimum duration (in milliseconds) for a group of samples to be
        classified as a fixation. Defaults to ``settings.FIXATION_MINIMUM_DURATION_MS``.

    velocity_threshold : float | None, optional
        Velocity threshold used by the IVT method (in degrees/second).
        Defaults to ``settings.FIXATION_VELOCITY_THRESHOLD``.

    dispersion_threshold : float | None, optional
        Dispersion threshold used by the IDT method.
        Defaults to ``settings.FIXATION_DISPERSION_THRESHOLD``.

    Notes
    -----
    After detection, fixation properties (e.g., fixation location) are
    computed and added to ``gaze.events``.
    """
    if method is None:
        method = settings.FIXATION_METHOD
    if minimum_duration is None:
        minimum_duration = settings.FIXATION_MINIMUM_DURATION_MS
    if velocity_threshold is None:
        velocity_threshold = settings.FIXATION_VELOCITY_THRESHOLD
    if dispersion_threshold is None:
        dispersion_threshold = settings.FIXATION_DISPERSION_THRESHOLD

    if method not in {"ivt", "idt"}:
        raise ValueError(
            f"Unsupported fixation detection method {method!r}. "
            "Supported methods are: ivt, idt."
        )

    method_kwargs = {
        "minimum_duration": minimum_duration,
        "include_nan": settings.FIXATION_INCLUDE_NAN,
        "name": settings.FIXATION,
    }
    if method == "ivt":
        method_kwargs["velocity_threshold"] = velocity_threshold
    else:
        method_kwargs["dispersion_threshold"] = dispersion_threshold

    gaze.detect(method, **method_kwargs)

    compute_event_properties(
        gaze, settings.FIXATION, settings.EVENT_PROPERTIES[settings.FIXATION]
    )


def _auto_eye_components(samples: pl.DataFrame) -> tuple[int, int]:
    """Return the velocity component pair selected by pymovements ``eye='auto'``."""
    velocities = samples.get_column("velocity").drop_nulls()
    if velocities.is_empty():
        return 0, 1

    first_velocity = velocities[0]
    if not isinstance(first_velocity, (list, tuple)):
        return 0, 1

    n_components = len(first_velocity)
    if n_components >= 6:
        return 4, 5
    if n_components >= 4:
        return 2, 3
    return 0, 1


def _is_degenerate_group(
    group: pl.DataFrame,
    eye_components: tuple[int, int],
    threshold: str | tuple[float, float] | list[float] | np.ndarray,
    minimum_threshold: float,
) -> tuple[str | None, int]:
    """Return the reason a trial/page group cannot produce micro-saccades."""
    velocities = group.get_column("velocity").drop_nulls()
    valid_sample_count = len(velocities)
    if valid_sample_count < 2:
        return "fewer_than_2_valid_samples", valid_sample_count

    values = np.asarray(velocities.to_list(), dtype=float)
    if values.ndim != 2 or values.shape[1] <= max(eye_components):
        return "invalid_velocity_shape", valid_sample_count

    if isinstance(threshold, str):
        threshold_values = compute_threshold(
            values[:, eye_components],
            method=threshold,
        )
        if (threshold_values < minimum_threshold).any():
            return "zero_variance", valid_sample_count
    return None, valid_sample_count


def _group_details(
    trial_columns: list[str],
    group_identifier: object,
    valid_sample_count: int,
    reason: str,
) -> dict[str, object]:
    """Build a log-friendly description of a trial/page group."""
    identifier = (
        group_identifier if isinstance(group_identifier, tuple) else (group_identifier,)
    )
    return {
        **dict(zip(trial_columns, identifier)),
        "valid_samples": valid_sample_count,
        "reason": reason,
    }


def _detect_microsaccades_without_degenerate_groups(
    gaze,
    method: str,
    *,
    threshold: str | tuple[float, float] | list[float] | np.ndarray,
    minimum_threshold: float,
    **kwargs,
) -> None:
    """Run micro-saccade detection after removing groups that would abort it."""
    detect_kwargs = {
        **kwargs,
        "threshold": threshold,
        "minimum_threshold": minimum_threshold,
    }
    samples = getattr(gaze, "samples", None)
    trial_columns = getattr(gaze, "trial_columns", None)
    if (
        samples is None
        or samples.is_empty()
        or not trial_columns
        or "velocity" not in samples.columns
    ):
        gaze.detect(method, **detect_kwargs)
        return

    eye_components = _auto_eye_components(samples)
    indexed_samples = samples.with_row_index(_GROUP_ROW_INDEX_COLUMN)
    grouped_samples = indexed_samples.partition_by(
        trial_columns,
        maintain_order=True,
        include_key=True,
        as_dict=True,
    )

    bad_row_indices: list[int] = []
    bad_groups: list[dict[str, object]] = []
    for group_identifier, group in grouped_samples.items():
        reason, valid_sample_count = _is_degenerate_group(
            group,
            eye_components,
            threshold,
            minimum_threshold,
        )
        if reason is None:
            continue
        bad_row_indices.extend(group.get_column(_GROUP_ROW_INDEX_COLUMN).to_list())
        bad_groups.append(
            _group_details(
                trial_columns,
                group_identifier,
                valid_sample_count,
                reason,
            )
        )

    if not bad_row_indices:
        gaze.detect(method, **detect_kwargs)
        return

    session_id = None
    if "session" in samples.columns:
        session_values = samples.get_column("session").drop_nulls()
        if not session_values.is_empty():
            session_id = session_values[0]
    session_suffix = f" in session {session_id}" if session_id else ""

    logger.warning(
        "Skipping saccade detection for %s trial/page group(s)%s because they "
        "have fewer than 2 valid velocity samples or zero variance: %s%s",
        len(bad_groups),
        session_suffix,
        bad_groups[:_MAX_LOGGED_GROUPS],
        " ..." if len(bad_groups) > _MAX_LOGGED_GROUPS else "",
    )

    filtered_samples = indexed_samples.filter(
        ~pl.col(_GROUP_ROW_INDEX_COLUMN).is_in(bad_row_indices)
    ).drop(_GROUP_ROW_INDEX_COLUMN)
    if filtered_samples.is_empty():
        raise ValueError(
            "No valid saccade groups remain"
            f"{session_suffix}. Degenerate groups: {bad_groups}"
        )

    original_samples = gaze.samples
    gaze.samples = filtered_samples
    try:
        gaze.detect(method, **detect_kwargs)
    finally:
        gaze.samples = original_samples


def detect_saccades(
    gaze,
    minimum_duration: int | None = None,
    threshold_factor: float | None = None,
    threshold: str | tuple[float, float] | list[float] | None = None,
    minimum_threshold: float | None = None,
    include_nan: bool | None = None,
) -> None:
    """
    This function detects saccades (or micro-saccades) using a
    noise-adaptive velocity threshold and then computes properties such as
    saccade amplitude and peak velocity.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object.

    minimum_duration : int | None, optional
        Minimum duration (in samples) required for a velocity peak to be
        considered a saccade. Shorter events are ignored as noise.
        Defaults to ``settings.SACCADE_MINIMUM_DURATION``.

    threshold_factor : float | None, optional
        Multiplier that determines the velocity threshold relative to the
        noise level in the signal. Increasing this value makes detection
        more conservative (fewer saccades). Defaults to
        ``settings.SACCADE_THRESHOLD_FACTOR``.

    threshold : str or tuple of float or list of float or None, optional
        Data-driven threshold method or explicit two-value threshold.
        Defaults to ``settings.SACCADE_THRESHOLD``.

    minimum_threshold : float | None, optional
        Minimum threshold value. Defaults to
        ``settings.SACCADE_MINIMUM_THRESHOLD``.

    include_nan : bool | None, optional
        Whether to split saccade events on missing samples. Defaults to
        ``settings.SACCADE_INCLUDE_NAN``.

    Notes
    -----
    After detection, saccade properties (e.g., amplitude and peak velocity)
    are computed and added to ``gaze.events``.
    """
    if minimum_duration is None:
        minimum_duration = settings.SACCADE_MINIMUM_DURATION
    if threshold_factor is None:
        threshold_factor = settings.SACCADE_THRESHOLD_FACTOR
    if threshold is None:
        threshold = settings.SACCADE_THRESHOLD
    if minimum_threshold is None:
        minimum_threshold = settings.SACCADE_MINIMUM_THRESHOLD
    if include_nan is None:
        include_nan = settings.SACCADE_INCLUDE_NAN

    if isinstance(threshold, list):
        threshold = tuple(threshold)

    method = settings.SACCADE_METHOD
    method_kwargs = {
        "minimum_duration": minimum_duration,
        "threshold_factor": threshold_factor,
        "threshold": threshold,
        "minimum_threshold": minimum_threshold,
        "include_nan": include_nan,
        "name": settings.SACCADE,
    }

    if method == "microsaccades":
        _detect_microsaccades_without_degenerate_groups(
            gaze,
            method,
            **method_kwargs,
        )
    else:
        gaze.detect(method, **method_kwargs)

    compute_event_properties(
        gaze, settings.SACCADE, settings.EVENT_PROPERTIES[settings.SACCADE]
    )
