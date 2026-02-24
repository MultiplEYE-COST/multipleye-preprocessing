(reading_measures)=

# Reading Measures
A more elaborate explanation of the reading measures implemented in `reading_measures.py` https://github.com/MultiplEYE-COST/multipleye-preprocessing/blob/main/preprocessing/metrics/reading_measures.py

## Fixation-based Measures

| Abbreviation | Full name | Description |
|---|---|---|
| FFD | First Fixation Duration | duration of the first fixation on a word if this word is fixated in first-pass reading, otherwise 0 |
| FD | First Duration | duration of the first fixation on a word (identical to FFD if not skipped in the first-pass) |
| FPF | First-Pass Fixation | 1 if the word was fixated in the first-pass, otherwise 0 |
| FPFC | First-Pass Fixation Count | number of of all first-pass fixations on a word |
| FPRT | First-Pass Reading Time | sum of the durations of all first-pass fixations on a word (0 if the word was skipped in the first-pass) |
| FRT | First Reading Time | sum of the duration of all fixations from first fixating the word (independent if the first fixations occur in first-pass reading) until leaving the word for the first time (equals FPRT in case the word was fixated in the first-pass) |
| TFC | Total Fixation Count | number of all fixations on a word |
| TFT | Total Fixation Time | sum of all fixations on a word (FPRT + RRT) |
| RR | Re-reading | 1 if the word was fixated after the first-pass reading, otherwise 0 (sign(RRT)) |
| RRT | Re-reading Time | sum of the durations of all fixations on a word that do not belong to the first-pass (TFT−FPRT) | 
| SFD | Single-Fixation Duration | duration of the only first-pass fixation on a word, 0 if the word was skipped or more than one fixations occurred in the first-pass (equals FFD in case of a single first-pass fixation) |


## Transition-based Measures

| Abbreviation | Full name | Description |
|---|---|---|
| LP | Landing Position | Position of the first saccade on the word expressed by the ordinal position of the fixated character |
| RBRT | Right-Bounded Reading Time | Sum of all fixation durations on a word until a word to the right of this word is fixated (RPD_inc - RPD_exc) |
| RPD_exc | Exclusive Regression Path Duration | Sum of all fixation durations after initiating a first-pass regression from a word until fixating a word to its right, excluding fixations on the word itself (RPD_inc - RBRT) |
| RPD_inc | Inclusive Regression Path Duration | Sum of all fixation durations starting from the first first-pass fixation on a word until fixating a word to its right (includes all regressive fixations on previous words); 0 if not fixated in first-pass (RPD_exc + RBRT)|
| SL_in | Incoming Saccade Length | Length of the saccade leading to the first fixation on a word (in number of words); positive = progressive, negative = regression |
| SL_out | Outgoing Saccade Length | Length of the first saccade leaving the word (in number of words); positive = progressive, negative = regressive; 0 if the word is never fixated |
| TRC_in | Total Regressive Count (Incoming) | Total number of regressive saccades landing on this word |
| TRC_out | Total Regressive Count (Outgoing) | Total number of regressive saccades initiated from this word |