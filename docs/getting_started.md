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
`theDebbister/multipleye-preprocessing`](https://github.com/theDebbister/multipleye-preprocessing)
repository to your local machine.

```bash
git clone https://github.com/theDebbister/multipleye-preprocessing.git
```

Once cloned, navigate into the cloned repository.

```bash
cd multipleye-preprocessing/
```

To use the pipeline, we expect you to have python set up on your machine.
Make sure to use an up-to-date python version.
The pipeline has been developed with `3.13` and up in mind.
It is recommended to [create a virtual environment](https://docs.python.org/3/library/venv.html)
for your project.
Then you can set it up using [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
```

If you do not want to use `uv`, you can install it in editable mode:

```bash
pip install -e .
```

```{warning}
To be finished!
```

Before we can {ref}`run the pipelines <running_pipelines>`,
we need to install the EyeLink Developers Kit.
This is needed to convert files from the proprietary `.edf` format to the parsable `.asc` format,
the binary `edf2asc` needs to be installed.

(eyelink_dev_kit)=

## EyeLink Developers Kit

The `edf2asc` utility is being delivered with the EyeLink Developers Kit and is owned by
SR Research Ltd., being distributed through their forum website.
To access the download, an account must be created first.
If you do not own an account on the SR Support Forum yet,
[register in their support forum](https://www.sr-research.com/support/member.php?action=register).
For a registration:

1. Fill in the *Account Details* and *Preferences*.
2. In the *Required Information* section, select the EyeLink system you use
   (e.g., EyeLink Portable Duo) and your institure and role information.
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

After installation, the pipelines can be executed directly from the command line as they are
registered as entry points in `pyproject.toml`.
If this is your first time with the pipeline, or you are unsure if you have the right data and
formats, please read into the more detailled {ref}`reference_guide` chapter.

Previously, the pipelines were run as standalone scripts (e.g.,
`python run_multipleye_preprocessing.py`), but they have now been moved to `preprocessing.scripts`
and should be called by their registered names.
The main pipelines require the name of the data collection folder (which should be located in the
`data/` directory) as a positional argument.

To run the MultiplEye preprocessing pipeline (if you used `uv` for installation):

```bash
run_multipleye_preprocessing <data_collection_name>
```

To run the MERID preprocessing pipeline:

```bash
run_merid_preprocessing <data_collection_name>
```

You can also run them using `uv run`:

```bash
uv run run_multipleye_preprocessing <data_collection_name>
```

Additional scripts are available for sanity checks (e.g., `run_merid_sanity_checks`) and processing
psychometric tests. Note that sanity checks for MultiplEye are currently under development.
The details of calculating the psychometric tests can be found in the
{ref}`calculating_psychometric_tests` section.

You can always check the available options for each script by using the `--help` flag:

```bash
run_multipleye_preprocessing --help
```
