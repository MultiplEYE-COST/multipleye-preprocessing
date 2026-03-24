(configuration_guide)=

# Configuration

The configuration of the preprocessing pipeline is handled by the YAML configuration file
`multipleye_settings_preprocessing.yaml`.
You can find this file in the repository root.
As the name suggests, this file contains user-configurable settings for your specific data
collection, while internal constants are defined in `preprocessing/constants.py`
and should be kept as default values unless you know what you are doing.
Edits must be made manually in the YAML file. While some processing commands can be passed explicit variables,
it is best just to set the values once centrally, so throughout the pipeline no values need to be
passed.

For detailed information about the pipeline architecture and how configuration parameters are used in each processing step, please refer to the {ref}`technical_architecture` section.

## Configuration Settings

The main configuration file (`preprocessing/config.py`) contains the following key settings:

### Data Collection Configuration

- `BASE_DATA_DIR`: Root `data/` directory where your data is stored
- `DATA_COLLECTION_ID`: Identifier for your data collection (e.g., "MultiplEYE_SQ_CH_Zurich_1_2025")
  inside `BASE_DATA_DIR`.
- `PSYCHOMETRIC_TESTS_DIR`: Directory containing psychometric test sessions

[//]: # (- `OUTPUT_DIR`: Directory where processed results will be saved)

### Psychometric Test Settings

- `PSYCHOMETRIC_TESTS_DIR`: Directory containing psychometric test sessions (configured per data collection)

### Processing Parameters

- `expected_sampling_rate_hz`: Expected sampling rate of the eye tracker in Hz (default: 1000)
- `include_sessions`: Optional list of specific session IDs to process
- `exclude_sessions`: Optional list of session IDs to exclude from processing
- `include_pilots`: Whether to include pilot sessions in the processing (default: True)
- `session_to_stimuli`: Mapping for non-standard stimulus versions (not yet in use)

## Constants

The constants file (`preprocessing/constants.py`) contains technical parameters that should not need
modification:

- Standard data structure
- Sanity check acceptable thresholds
- Eyetracker names and stimulus name mappings

## Modifying Configuration

To modify the configuration for your data collection:

1. Open `preprocessing/config.py`
2. Update the `DATA_COLLECTION_ID` and directory paths as needed
3. Adjust any test-specific parameters if your data format differs
4. Save the file - changes will take effect on the next run

```{note}
It is useful to test with a small subset of data first and backing up your
`multipleye_settings_preprocessing.yaml`
before making changes.
```
