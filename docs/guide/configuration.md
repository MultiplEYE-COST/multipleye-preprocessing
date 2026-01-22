(configuration_guide)=

# Configuration

The configuration of the preprocessing pipeline is handled by the `config.py` and `constants.py`
files.
You can find these files in the `preprocessing/` directory.
As the names suggest, `config.py` contains user-configurable settings for your specific data
collection, while `constants.py` contains technical constants that should be kept as default values
unless you know what you are doing.
Edits must be made manually. While some processing commands can be passed explicit variables,
it is best just to set the values once centrally, so throughout the pipeline no values need to be
passed.

## Configuration Settings

The main configuration file (`preprocessing/config.py`) contains the following key settings:

### Data Collection Configuration

- `BASE_DATA_DIR`: Root `data/` directory where your data is stored
- `DATA_COLLECTION_ID`: Identifier for your data collection (e.g., "MultiplEYE_SQ_CH_Zurich_1_2025")
  inside `BASE_DATA_DIR`.
- `PSYCHOMETRIC_TESTS_DIR`: Directory containing psychometric test sessions

[//]: # (- `OUTPUT_DIR`: Directory where processed results will be saved)

### Psychometric Test Settings

- ...

### Processing Parameters

- ...

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
Is is useful to test with a small subset of data first and backing up your `config.py`
before making changes.
```
