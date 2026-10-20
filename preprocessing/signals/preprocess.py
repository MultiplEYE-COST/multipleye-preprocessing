"""Preprocessing functions for gaze data."""

import pymovements as pm

from ..config import settings


def preprocess_gaze(
    gaze: pm.Gaze,
    method: str | None = None,
    window_ms: int | None = None,
    poly_degree: int | None = None,
) -> None:
    """
    Convert gaze samples from pixel coordinates to degrees of visual angle (dva),
    and compute velocity for event detection.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object containing raw gaze samples.

    method : {"preceding", "neighbors", "fivepoint", "smooth", "savitzky_golay"} | None, optional
        Velocity estimation method. Defaults to ``settings.VELOCITY_ESTIMATION_METHOD``.

    window_ms : int | None, optional
        Length of the smoothing/differentiation window in milliseconds.
        Only used when ``method="savitzky_golay"``.
        Defaults to ``settings.VELOCITY_SMOOTHING_WINDOW_MS``.

    poly_degree : int | None, optional
        Polynomial degree used in the Savitzky-Golay filter.
        Defaults to ``settings.VELOCITY_POLYNOMIAL_DEGREE``.

    Notes
    -----
    This function should be called **before** detecting fixations or saccades,
    since event detection relies on the velocity signal.

    Available velocity estimation methods:
      - ``preceding``: difference between current and previous sample.
      - ``neighbors``: difference between next and previous sample.
      - ``fivepoint``: mean of two preceding and two following samples.
      - ``smooth``: alias of ``fivepoint``.
      - ``savitzky_golay``: fits a local polynomial using a sliding window.
    """
    if method is None:
        method = settings.VELOCITY_ESTIMATION_METHOD
    if window_ms is None:
        window_ms = settings.VELOCITY_SMOOTHING_WINDOW_MS
    if poly_degree is None:
        poly_degree = settings.VELOCITY_POLYNOMIAL_DEGREE

    # Savitzky-Golay filter as in https://doi.org/10.3758/BRM.42.1.188
    window_length = round(gaze.experiment.sampling_rate / 1000 * window_ms)
    if window_length % 2 == 0:
        window_length += 1

    # pix2deg is element-wise (per-sample). Gaze.pix2deg() otherwise applies it
    # separately for every trial/page group (hundreds here), which is pure
    # overhead for a row-wise transform. Run it on the whole samples frame at
    # once by temporarily disabling trial grouping.
    trial_columns = getattr(gaze, "trial_columns", None)
    if trial_columns is None:
        gaze.pix2deg()
    else:
        try:
            gaze.trial_columns = None
            gaze.pix2deg()
        finally:
            gaze.trial_columns = trial_columns

    # pos2vel smooths across a window, so it must stay grouped by trial/page to
    # avoid bleeding across page boundaries.
    gaze.pos2vel(method, window_length=window_length, degree=poly_degree)
