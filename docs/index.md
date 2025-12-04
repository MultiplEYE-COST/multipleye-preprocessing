(preprocessing_pipeline_index)=

# MultiplEYE Preprocessing pEYEpline

::::{grid} 1 2 2 3
:gutter: 1 1 1 2

:::{grid-item-card} {material-regular}`rocket;2em` Getting Started
:link: getting_started
:link-type: ref

How to prepare before running your first preprocessing.\
Start your endeavour here!

+++
{ref}`Learn more » <getting_started>`
:::

:::{grid-item-card} {material-regular}`menu_book;2em` Reference Guide
:link: reference_guide
:link-type: ref

Theoretic background...
See all...

+++
{ref}`Learn more »<reference_guide>`
:::

:::{grid-item-card} {material-regular}`lightbulb;2em` Demos
:link: demos
:link-type: ref

Short demos showcasing package xyz.
+++
{ref}`Learn more »<Demos>`
:::

::::

Preprocessing pipeline for the MultiplEYE corpus by {cite:t}`JakobiDingEtAl2025MultipleyeCorpus`.
This website documents...

[//]: # (TODO: finish short description and change grid items)

## Setup and use

{ref}`getting_started`, {ref}`reference_guide`.

[//]: # (TODO: write section)

## How to cite

If you use this preprocessing pipeline, or parts of it in your research,
please cite our paper in **?**.
You can also find citation information for this project in the `CITATION.cff`
file in the repository and cite it accordingly.

[//]: # (TODO: add citation)

## Acknowledgments

This project has received functing from...

[//]: # (TODO: add acknowledgements and funding)

```{eval-rst}
.. toctree::
   :hidden:
   :name: table_of_contents
   :caption: Table of Contents
   :maxdepth: 1
   :glob:

   getting_started
   guide/index
   bibliography
```

```{error}
Text below is only for internal explanation. Delete content below before going public.
```

## Writing In a nutshell:

Pages can be written with Markdown (`.md`) or rST (`.rst`). Notebooks also work.
Due to syntactical reasons any directive from rST like ```:...:`ref-or-text` ``` turns to ```{...}`ref-or-text` ``` in MyST.
The ecosystem of MyST can be a bit confusing, take a short look at the summary [Ecosystem of tools](https://executablebooks.org/en/latest/tools/).
This page uses the [`sphinx-book-theme`](https://sphinx-book-theme.readthedocs.io/en/stable/index.html).

### Citing

See this paper of {cite:t}`JakobiDingEtAl2025MultipleyeCorpus`.

Just the bracket without a name: {cite:p}`Krakowczyk_pymovementsETRA2023` and multiple papers {cite:p}`KrakowczykReich2025MoreTheMerrier,MultiplEYE_DSP_2024`,
see [usage](https://sphinxcontrib-bibtex.readthedocs.io/en/stable/usage.html#roles-and-directives).

### Building the documentation

When writing, building the documentation is important to see your changes.
For this, ensure the documentation dependencies are installed.
To build the pages once, from the root of the repository, run:

```bash
sphinx-build docs/ public -b dirhtml
```

Alternatively, using `sphinx-autobuild` is helpful, as it automatically starts a server to show the
documentation pages and for every saved change, the documentation is rebuilt and reloaded automatically.

```bash
sphinx-autobuild docs/ public -b dirhtml
```

It runs until you close it with `ctrl+c`.