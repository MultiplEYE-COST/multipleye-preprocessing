"""Event properties submodule of the preprocessing module."""

import pymovements as pm


def compute_event_properties(
    gaze: pm.Gaze,
    event_name: str,
    properties: list[tuple[str, dict]],
) -> None:
    """
    Compute and add event properties to `gaze.events`.

    Parameters
    ----------
    gaze : pm.Gaze
        Gaze object containing detected events.
    event_name : str
        Event type ('fixation', 'saccade', ...).
    properties : list[tuple[str, dict]]
        Each tuple defines (property_name, kwargs) passed to EventGazeProcessor.
    """
    join_on = gaze.trial_columns + ["name", "onset", "offset"]

    for prop_name, kwargs in properties:
        processor = pm.EventGazeProcessor((prop_name, kwargs))
        new_props = processor.process(
            gaze.events,
            gaze,
            identifiers=gaze.trial_columns,
            name=event_name,
        )
        gaze.events.add_event_properties(new_props, join_on=join_on)
