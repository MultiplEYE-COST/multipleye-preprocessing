(preprocessing_guide)=

# Preprocessing

## Data Collection Naming Convention

The MultiplEYE preprocessing pipeline follows a standardized naming convention for data collections
to ensure consistency across labs and languages. The pattern is:

`[projectName]_[languageISOcode]_[countryISOcode]_[city]_[identifier]_[yearDataCollectionEnd]`

For the data collection identifier `MultiplEYE_SQ_CH_Zurich_1_2025`, the breakdown includes
MultiplEYE as the project name, SQ as the Albanian language code
(see [ISO 639 language codes](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes)), CH as
the Switzerland country code
(see [ISO 3166 country codes](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)),
Zurich as the city name, 1 as the lab/experiment identifier,
and 2025 as the year of data collection completion.

## Eye-Tracking Preprocessing Pipeline

The main preprocessing pipeline handles the conversion and processing of eye-tracking data from the
proprietary EyeLink format to analysis-ready data.

The pipeline processes data on a session level and consists of several key steps including EDF to
ASC conversion, data parsing, gaze event detection, AOI mapping, and reading measures calculation.
For detailed technical specifications of each step, including file formats and quality control
procedures, please refer to the {ref}`technical_architecture` section.

### Input Data Structure

The expected eye-tracking data structure follows the MultiplEYE data folder organization. Each
dataset contains eye-tracking sessions organized by participant and session identifiers, with
stimulus information available in a separate folder containing AOI files. For the complete data
structure specification, see the {ref}`multiplEYE_data_structure` section.

### Running the Preprocessing

```bash
# Run full preprocessing pipeline
run_multipleye_preprocessing <data_collection_name>

# Run with uv
uv run run_multipleye_preprocessing <data_collection_name>
```

### Output Files

The pipeline generates several types of output files including sample-level CSV files, gaze event
files, AOI mapping files, and reading measures. Each step produces specific output files with
standardized naming conventions. For detailed output file specifications and data quality reports,
please refer to the {ref}`technical_architecture` section.
