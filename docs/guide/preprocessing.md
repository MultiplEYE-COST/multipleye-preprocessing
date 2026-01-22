(preprocessing_guide)=

# Preprocessing

## Data Collection Naming Convention

The MultiplEYE preprocessing pipeline follows a standardized naming convention for data collections
to ensure consistency across labs and languages. The pattern is:

`MultiplEYE_[languageISOcode]_[countryISOcode]_[city]_[identifier]_[yearDataCollectionEnd]`

### Example Breakdown

For the data collection identifier `MultiplEYE_SQ_CH_Zurich_1_2025`:

- **MultiplEYE** - Project name
- **SQ** - Language code (Albanian)
    - [List of ISO 639 language codes](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes)
- **CH** - Country code (Switzerland)
    - [List of ISO 3166 country codes](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
- **Zurich** - City name
- **1** - Lab/experiment identifier
- **2025** - Year of data collection completion

## Eye-Tracking Preprocessing Pipeline

The main preprocessing pipeline handles the conversion and processing of eye-tracking data from the
proprietary EyeLink format to analysis-ready data.

### Pipeline Steps

1. **EDF to ASC Conversion**: Converts proprietary `.edf` files to parseable `.asc` format using the
   EyeLink Developers Kit
2. **Data Parsing**: Extracts gaze position, ...
3. **Quality Control**: Sanity checks ...
4. **Event Detection**: ?
5. **Data Export**: ?

### Input Data Structure

Expected eye-tracking data structure _(confirm)_:

```
data/{data_collection_id}/
├── raw/
│   ├── {participant_id}.edf
│   └── ...
└── sessions/
    ├── {session_id}/
    │   ├── {session_id}.edf
    │   └── ...
    └── ...
preprocessed_data/
├── {participant_id}_processed.csv
└── ...
```

### Running the Preprocessing

```bash
# Run full preprocessing pipeline
run_multipleye_preprocessing <data_collection_name>

# Run with uv
uv run run_multipleye_preprocessing <data_collection_name>
```

### Output Files

The pipeline generates several output files:

- **Quality reports**: Summary of data quality metrics
- ...
- Session summaries?
