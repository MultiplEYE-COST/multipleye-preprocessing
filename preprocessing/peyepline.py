import pymovements as pm


def create_gaze_frame(raw_file: str, save=True) -> pm.Gaze:
    """
    Pareses the gaze samples (i.e. x-y-coordinates and timestamps) from the raw eye-tracking data file.
    :param raw_file: In case of EyeLink experiments this is an asc file. For Tobii a TSV file.
    At the moment only works for EyeLink.
    :param save: If True, the gaze data will be saved as a pickle (=TBD, does pm have this????) file in the same folder as the raw file.
    :return:
    """
    # TODO: figure out if pm can save gaze data?
    # TODO: what to do about the metadata arugment? create a fucntion to properly access it? getter?
    pass


def calculate_fixations():
    pass

def calculate_saccades():
    pass

def map_fixations_to_aois():
    """
    The aoi files are stored in the data collection. They are the same for each participant. Excpet for the question answer options.
    :return:
    """
    pass

