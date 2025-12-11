(getting_started)=

# Getting Started

For the pipeline to function, there are some requirements that need to be met.

## Pipeline

The preprocessing pipeline is written in Python and uses a few dependencies,
including [`pymovements`](https://pymovements.readthedocs.io/), `polars`, `matplotlib`,
among others.
The pipeline itself is not distributed on PyPI and is to be used from the source code.
To download the source code,
you can clone the [`theDebbister/multipleye-preprocessing`](https://github.com/theDebbister/multipleye-preprocessing)
repository to your local machine.

```bash
git clone https://github.com/theDebbister/multipleye-preprocessing.git
```

Once cloned, navigate into the cloned repository.
To use the pipeline, we expect you to have python set up on your machine.
It is recommended to [create a virtual environment](https://docs.python.org/3/library/venv.html)
for your project.
Then you can install it in editable mode:

```bash
pip install -e .
```

Or set it up using [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
```

```{warning}
To be finished!
```

To convert files from the proprietary `.edf` format to the parsable `.asc` format,
the binary `edf2asc` needs to be installed.

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