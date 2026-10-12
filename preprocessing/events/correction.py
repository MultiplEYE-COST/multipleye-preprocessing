"""Fixation drift correction wrapper around pymovements."""

import pymovements as pm

from ..config import settings
from ..mapping.aoi import build_combined_text_stimulus


def correct_fixations(
    gaze: pm.Gaze,
    stimuli: list,
    algorithm: str | list[str] | None = None,
    algorithm_kwargs: dict | None = None,
) -> None:
    """
    Correct the vertical drift of fixation locations for all trials of a session.

    Correction is applied per trial by ``pymovements.events.correction``. Fixation
    locations are replaced in place and the original locations are preserved in
    ``location_x_original`` / ``location_y_original`` columns, while the applied
    algorithm is recorded in a ``correction_algorithm`` column.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object whose fixation events are corrected in place.
    stimuli : list of Stimulus
        A list of Stimulus objects, each containing ``text_stimulus`` data with defined
        AOIs and trial IDs. Their AOIs are consolidated into a single text stimulus.
    algorithm : str | list[str] | None, optional
        Drift correction algorithm or list of algorithms. Defaults to
        ``settings.FIXATION_CORRECTION_ALGORITHM``.
    algorithm_kwargs : dict | None, optional
        Additional tuning parameters passed to the drift algorithms. Defaults to
        ``settings.FIXATION_CORRECTION_KWARGS``.

    Notes
    -----
    The ``character_level`` flag is derived from the presence of the configured character
    index column in the AOIs, since pymovements needs to aggregate character-level AOIs
    to word locations for the DTW-based algorithms.
    """
    if algorithm is None:
        algorithm = settings.FIXATION_CORRECTION_ALGORITHM
    if algorithm_kwargs is None:
        algorithm_kwargs = settings.FIXATION_CORRECTION_KWARGS

    stimulus = build_combined_text_stimulus(stimuli)
    character_level = settings.CHAR_IDX_COL in stimulus.aois.columns

    gaze.events.correct_fixations(
        stimulus,
        algorithm=algorithm,
        algorithm_kwargs=algorithm_kwargs,
        fixation_name=settings.FIXATION,
        character_level=character_level,
    )
