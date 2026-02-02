"""Event detection functions."""

from ..constants import FIXATION, SACCADE
from ..events.properties import compute_event_properties
from ..io.load import DEFAULT_EVENT_PROPERTIES


def detect_fixations(
    gaze,
    method: str = "ivt",
    minimum_duration: int = 100,
    velocity_threshold: float = 20.0,
) -> None:
    """
    This function applies a fixation detection method and then computes
    descriptive properties (such as fixation location).

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object containing gaze samples and trial metadata.

    method : {"ivt", "idt"}, optional
        Event detection method:
        - ``"ivt"`` (Velocity-Threshold Identification):
          Samples are classified as fixations when their velocity is below
          ``velocity_threshold`` degrees/second. Consecutive samples are
          merged into fixation events. This is the default method.
        - ``"idt"`` (Dispersion-Threshold Identification):
          Groups points that remain within a spatial dispersion window for
          at least ``minimum_duration`` ms.

    minimum_duration : int, optional
        Minimum duration (in milliseconds) for a group of samples to be
        classified as a fixation. Default is 100 ms.

    velocity_threshold : float, optional
        Velocity threshold used by the IVT method (in degrees/second).
        Default is 20.0 deg/s.

    Notes
    -----
    After detection, fixation properties (e.g., fixation location) are
    computed and added to ``gaze.events``.
    """

    gaze.detect(
        method, minimum_duration=minimum_duration, velocity_threshold=velocity_threshold
    )

    compute_event_properties(gaze, FIXATION, DEFAULT_EVENT_PROPERTIES[FIXATION])


def detect_saccades(
    gaze,
    minimum_duration: int = 6,
    threshold_factor: float = 6,
) -> None:
    """
    This function detects saccades (or micro-saccades) using a
    noise-adaptive velocity threshold and then computes properties such as
    saccade amplitude and peak velocity.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object containing gaze samples and trial metadata.

    minimum_duration : int, optional
        Minimum duration (in samples) required for a velocity peak to be
        considered a saccade. Default is 6 samples (~12 ms at 500 Hz).
        Shorter events are ignored as noise.

    threshold_factor : float, optional
        Multiplier that determines the velocity threshold relative to the
        noise level in the signal. Increasing this value makes detection
        more conservative (fewer saccades). Default is 6.

    Notes
    -----
    After detection, saccade properties (e.g., amplitude and peak velocity)
    are computed and added to ``gaze.events``.
    """
    gaze.detect(
        "microsaccades",
        minimum_duration=minimum_duration,
        threshold_factor=threshold_factor,
    )

    compute_event_properties(gaze, SACCADE, DEFAULT_EVENT_PROPERTIES[SACCADE])
