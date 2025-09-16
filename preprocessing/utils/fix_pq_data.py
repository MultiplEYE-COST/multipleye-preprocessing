import pandas as pd


def remap_wrong_pq_values(pq_data: dict) -> dict:
    """
    As there was a bug in an earlier version of the experiment, some of the participant data has been lost.
    Data on "other reading time" is not available and the keys of the reading times have been swapped.
    :param pq_data:
    :return: Dict containing new participant data with corrected keys.
    """

    possible_languages = [
        'native_language_1', 'native_language_2', 'native_language_3', 'use_language', 'dominant_language',
        'additional_read_language_1', 'additional_read_language_2', 'additional_read_language_3',
        'additional_read_language_4'
    ]

    reading = [
        'academic_reading_time', 'magazine_reading_time', 'other_reading_time', 'newspaper_reading_time',
        'email_reading_time',
        'social_media_reading_time', 'fiction_reading_time', 'nonfiction_reading_time'
    ]

    corrected_reading_times = {}

    for lang in possible_languages:
        # quick fix to check whether the reading data for this language is in the data
        if f"{lang}_magazine_reading_time" in pq_data:
            for read in reading:
                key = f"{lang}_{read}"
                if read == 'academic_reading_time':
                    corrected_reading_times[key] = pq_data[f'{lang}_magazine_reading_time']
                    #print(f"Correcting {key} to {lang}_magazine_reading_time")
                elif read == 'magazine_reading_time':
                    corrected_reading_times[key] = pq_data[f'{lang}_newspaper_reading_time']
                    #print(f"Correcting {key} to {lang}_newspaper_reading_time")
                elif read == 'newspaper_reading_time':
                    corrected_reading_times[key] = pq_data[f'{lang}_email_reading_time']
                    #print(f"Correcting {key} to {lang}_email_reading_time")
                elif read == 'email_reading_time':
                    corrected_reading_times[key] = pq_data[f'{lang}_fiction_reading_time']
                    #print(f"Correcting {key} to {lang}_fiction_reading_time")
                elif read == 'fiction_reading_time':
                    corrected_reading_times[key] = pq_data[f'{lang}_nonfiction_reading_time']
                    #print(f"Correcting {key} to {lang}_nonfiction_reading_time")
                elif read == 'nonfiction_reading_time':
                    corrected_reading_times[key] = pq_data[f'{lang}_internet_reading_time']
                    #print(f"Correcting {key} to {lang}_internet_reading_time")
                elif read == 'internet_reading_time':
                    corrected_reading_times[key] = pq_data[f'{lang}_other_reading_time']
                    #print(f"Correcting {key} to {lang}_other_reading_time")
                elif read == 'other_reading_time':
                    corrected_reading_times[key] = pd.NA
                    #print(f"Setting {key} to pd.NA as it is not available in the data.")

    # Add the corrected reading times to the original data
    pq_data.update(corrected_reading_times)
    return pq_data

