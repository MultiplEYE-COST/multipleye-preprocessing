(configuration_guide)=

# Configuration

The configuration of the preprocessing pipeline is handled by the `preprocessing/config.py` file.

The `settings` object in `preprocessing/config.py` manages all configuration parameters, with
built-in defaults and a flexible loading mechanism.

## Loading Precedence

The pipeline loads configuration settings with the following precedence:

1. **Explicit path**: Using `--config_path` in CLI or `settings.load(path)` in API.
2. **Environment variable**: `MULTIPLEYE_CONFIG` pointing to a YAML file.
3. **Local default**: `multipleye_settings_preprocessing.yaml` in the current working directory.
4. **Legacy location**: `multipleye_settings_preprocessing.yaml` in the repository root
   (deprecated).

## Configuration Settings

The main settings include:

### Data Collection Configuration

- `DATA_COLLECTION_NAME`: Identifier for your data collection (e.g., `ME_EN_UK_LON_LAB1_2025`).
  **(Required)**
- `INCLUDE_PILOTS`: Whether to include pilot data (default: `False`).
- `EXCLUDE_SESSIONS`: List of session IDs to exclude.
- `INCLUDE_SESSIONS`: List of session IDs to include (if provided, only these will be processed).
- `EXPECTED_SAMPLING_RATE_HZ`: The expected sampling rate of the eye tracker (default: `1000`).

### Programmatic Usage (Notebooks)

In a Jupyter notebook, you can load your configuration explicitly:

```python
from preprocessing import settings

settings.load_from_yaml("path/to/your_config.yaml")
```

### CLI Usage

When running the preprocessing script:

```bash
python -m preprocessing.scripts.run_multipleye_preprocessing --config_path your_config.yaml
```

## Internal Constants

The `settings` object also contains technical parameters that should generally not need
modification:

- Standard data structure (`RAW_DATA_FOLDER`, `FIXATIONS_FOLDER`, etc.)
- Sanity check acceptable thresholds
- Eyetracker names and stimulus name mappings
