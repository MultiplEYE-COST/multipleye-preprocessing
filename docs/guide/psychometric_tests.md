(psychometric_tests)=

# Psychometric Tests

To obtain results for the psychometric tests, the recorded data has to be processed.
This page explains the steps involved in the processing. Furthermore, some background information
about the psychometric tests is provided.

## Data Collection

Data for the psychometric tests have been collected using the [
`MultiplEYE-psychometric-tests`](https://github.com/MultiplEYE-COST/MultiplEYE-psychometric-tests)
repository. Find details about it in the project's `README.md`.

## Theoretical Background

...

[//]: # (TODO: one h3 section per test)

(calculating_psychometric_tests)=

## Calculating the Psychometric Tests

As hinted in the {ref}`running_pipelines` section, there are project scripts for the psychometric
tests.
But before calculation, the input data must be structured correctly.

### Preparing the Data

For each session, there should be a folder containing one subfolder for each test with its data.
The data should be structured as follows, i.e. for the session identifier (sid)
`008_SQ_CH_1_PT2` and data collection identifier `MultiplEYE_SQ_CH_Zurich_1_2025`:

```text
data/MultiplEYE_SQ_CH_Zurich_1_2025/psychometric-tests-sessions/
├── ...
├── 008_SQ_CH_1_PT2
│   ├── 008_SQ_CH_1_PT2.yaml
│   ├── PLAB
│   │   ├── SQCH1_008_PT2_2025-09-13_15-18-01.csv
│   │   ├── SQCH1_008_PT2_2025-09-13_15-18-01.log
│   │   └── SQCH1_008_PT2_2025-09-13_15-18-01.psydat
│   ├── RAN
│   │   ├── SQCH1_008_PT2_2025-09-13_15-12-11.log
│   │   ├── SQCH1_8_S2_2025-09-13_15-12-11.csv
│   │   └── audio_SQCH1_008_PT2_2025-09-13_15-12-11
│   │       ├── SQCH1_8_S2_trial1.wav
│   │       └── SQCH1_8_S2_trial2.wav
│   ├── Stroop_Flanker
│   │   ├── SQCH1_008_PT2_2025-09-13_15-13-23.csv
│   │   ├── SQCH1_008_PT2_2025-09-13_15-13-23.log
│   │   └── SQCH1_008_PT2_2025-09-13_15-13-23.psydat
│   ├── WMC
│   │   ├── MU-8.dat
│   │   ├── OS-8.dat
│   │   ├── SQCH1_008_PT2_2025-09-13_14-31-31.csv
│   │   ├── SQCH1_008_PT2_2025-09-13_14-31-31.log
│   │   ├── SQCH1_008_PT2_2025-09-13_14-31-31.psydat
│   │   ├── SS-8.dat
│   │   ├── SSTM-8.dat
│   │   └── sstm_detailed
│   │       └── SSTM-8.dat
│   ├── WikiVocab
│   │   ├── SQCH1_008_PT2_2025-09-13_15-26-53.csv
│   │   └── images
│   └── psychometric_details_008_SQ_CH_1_PT2.csv (detail output for session)
```

The `psychometric_details_008_SQ_CH_1_PT2.csv` is written as an output of the psychometric tests
with all detailled measures for the session.
Furthermore, an overview of all sessions will be written to
`data/{data_collection_id}/{data_collection_id}_overview.yaml`

If it happens that the data is structured first by the test folder and then by session folder,
the data can be restructured using the `preprocessing.scripts.restructure_psycho_tests:main`
script.
This can be invoked like this:

```bash
restructure_psycho_tests
```

In short, if your data structure looks like below, `restructure_psycho_tests` can format it into
the desired structure as shown above.

```text
data/MultiplEYE_SQ_CH_Zurich_1_2025/psychometric-tests-sessions/core_data/
├── PLAB
│   ├── 001_SQ_CH_1_PT2
│   ├── ...
│   └── 026_SQ_CH_1_PT1
├── RAN
│   ├── 001_SQ_CH_1_PT2
│   ├── ...
│   └── 026_SQ_CH_1_PT1
├── Stroop_Flanker
│   ├── 001_SQ_CH_1_PT2
│   ├── ...
│   └── 026_SQ_CH_1_PT1
├── WMC
│   ├── 001_SQ_CH_1_PT2
│   ├── ...
│   └── 026_SQ_CH_1_PT1
├── WikiVocab
│   ├── 001_SQ_CH_1_PT2
│   ├── ...
│   └── 026_SQ_CH_1_PT1
└── participant_configs_SQ_CH_1
    ├── 001_SQ_CH_1_PT2.yaml
    ├── ...
    └── 026_SQ_CH_1_PT1.yaml
```

Usually, the command needs no arguments, if the {ref}`configuration` was correctly set up.
Otherwise, you can find out how to overwirte the global settings
by invoking `restructure_psycho_tests --help`.

### Calculation

```{warning}
To be done!
```
