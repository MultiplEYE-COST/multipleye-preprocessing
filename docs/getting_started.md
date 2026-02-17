(getting_started)=

# Getting Started

For the pipeline to function, there are some requirements that need to be met.
This page explains the setup of the {ref}`pipeline`, how to install the {ref}`eyelink_dev_kit`,
and {ref}`running_pipelines`.
More details on how to use the preprocessing pipeline can be found in the {ref}`reference_guide`.

(pipeline_structure)=

## Pipeline

The preprocessing pipeline is written in Python and uses a few dependencies,
including [`pymovements`](https://pymovements.readthedocs.io/), `polars`, `matplotlib`,
among others.
The pipeline itself is not distributed on PyPI and should be used directly from the source code.
To download the source code,
you can clone the [
`MultiplEYE-COST/multipleye-preprocessing`](https://github.com/MultiplEYE-COST/multipleye-preprocessing)
repository to your local machine.

```bash
git clone https://github.com/MultiplEYE-COST/multipleye-preprocessing.git
```

Once cloned, navigate into the cloned repository.

```bash
cd multipleye-preprocessing/
```

### Installation

To use the pipeline, we expect you to have python set up on your machine.
Make sure to use an up-to-date python version.
The pipeline has been developed with `3.13` and up in mind.

We recommend using `uv` to set up your environment, as it will automatically install the
dependencies
as specified in `pyproject.toml`.

1. Install `uv` by following the instructions on
   their [website](https://docs.astral.sh/uv/getting-started/installation/).
2. Clone the repository and navigate into it (see above).
3. Now, you can set the environment up using [`uv`](https://docs.astral.sh/uv/):

    ```bash
    uv sync
    ```
4. And activate it:
   ```
   source .venv/bin/activate
   ```

```{note}
If you do not want to use `uv`, you can install the pipeline in editable mode:
```bash
pip install -e .
```

## Eye-tracker specific requirements

In order to run the preprocessing pipeline, there are eye-tracker specific libraries required.
At the moment, only EyeLink eye-trackers are supported.

(eyelink_dev_kit)=

### EyeLink Developers Kit

Before we can {ref}`run the pipelines <running_pipelines>`,
we need to install the EyeLink Developers Kit.
This is needed to convert files from the proprietary `.edf` format to the parsable `.asc` format,
the binary `edf2asc` needs to be installed.

The `edf2asc` utility is being delivered with the EyeLink Developers Kit and is owned by
SR Research Ltd., being distributed through their forum website.
To access the download, an account must be created first.
If you do not own an account on the SR Support Forum yet,
[register in their support forum](https://www.sr-research.com/support/member.php?action=register):

1. Fill in the *Account Details* and *Preferences*.
2. In the *Required Information* section, select the EyeLink system you use
   (e.g., EyeLink Portable Duo) and your institution and role information.
3. Fill in *Image Verification* and *Security Question*.
4. Confirm your mail address through the mail you should receive from `support@sr-research.com`.
5. Wait, as each registration needs to be approved manually. This may take a day.

When you have an account:
Navigate to [the download page](https://www.sr-research.com/support/thread-13.html)
and login, unless you are already logged in.
If you need some context on the EyeLink Developers Kit,
you can read through this page.
Select the download fitting your operating system and install it.
An installation guide is available for Windows and macOS at the bottom of the page.

After installation, you should have access to the `edf2asc` program.
To confirm that it is available, open a terminal or command prompt and run:

```bash
edf2asc
```

This should show the program's version and usage information.

(running_pipelines)=

## Running the Pipelines

The process described below is also documented in a step-by-step notebook. This notebook breaks up
the
pipeline into the smaller steps. And you can go through them one by one.

```{tip}
Go through the [step-by-step notebook](https://github.com/MultiplEYE-COST/multipleye-preprocessing/blob/main/preprocessing.ipynb).
You can also open the same file locally at `preprocessing.ipynb` in the repo root.
```

After installation, the pipelines can be executed directly from the command line as they are
registered as entry points in `pyproject.toml`.
If this is your first time with the pipeline, or you are unsure if you have the right data and
formats, please read into the more detailled {ref}`reference_guide` chapter.

To run a pipeline you wil have to fill in the relevant information in the
`multipleye_settings_preprocessing.yaml` file.

Currently, there is one pipeline available which has been moved to `preprocessing.scripts`
and should be called by its registered name. The main pipelines require the config file path as an
argument. However,
the default config file is `multipleye_settings_preprocessing.yaml`, so if you have
updated the relevant information in that file, you can run the pipelines without providing the path
to the config file.

```{note}
All other pipelines and scripts are under development and should not be used yet.
```

### Download your MultiplEYE data

```{attention}
The steps below require that you have access to a protected folder where the MultiplEYE data for one data collection is stored.
You have only been granted access to this folder if you are part of the data collection for this language.
```

1. Download the data folder from the online repository. Download the content of the entire folder.
   When you download it from SwitchDrive, it will automatically create a .tar file.
2. Add the folder to the `data/` folder in this repo. Its name should be the name of the data
   collection, e.g. `MultiplEYE_ZH_CH_Zurich_1_2025`.
3. Extract the .tar file in the `data/` folder.
4. Please make sure that the extracted folder has the same structure as the folder online.

### Preprocess your data

To run the MultiplEye preprocessing pipeline (if you used `uv` for installation and activated the
environment):

```bash
run_multipleye_preprocessing
```

You can always check the available options for each script by using the `--help` flag:

```bash
run_multipleye_preprocessing --help
```
