(preprocessing_pipeline_index)=

# MultiplEYE Preprocessing pEYEpline

::::{grid} 1 2 2 2
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

If you are interested in the details of the preprocessing pipeline,
this section is for you.

+++
{ref}`Learn more »<reference_guide>`
:::

::::

The preprocessing pipeline for the MultiplEYE corpus by
{cite:t}`JakobiDingEtAl2025MultipleyeCorpus`.
This website documents the current state of the preprocessing pipeline, **which is still under
development**. This pipeline
is designed to process the raw eye-tracking data and psychometric test data
collected in the MultiplEYE project, transforming it into a standardized format suitable for
analysis and sharing with the research community.

The pipeline is built in Python and its core functionalities rely on the `pymovements` library,
which provides tools for processing eye-tracking data.
See [pymovements website](https://github.com/pymovements/pymovements)

## Setup and use

To use the preprocessing pipeline, please follow the instructions in the
{ref}`getting_started` section.
This section will guide you through the setup of the pipeline, including how to install
dependencies and run the preprocessing on your data collection.


[//]: # (TODO: write section)

## How to cite

If you use this preprocessing pipeline, or parts of it in your research,
please cite the pipeline as specified in {cite:t}`Jakobi2026MultiplEYEPreprocessing`.
You can also find citation information for this project in the `CITATION.cff`
file in the repository and cite it accordingly.

[//]: # (TODO: add citation)

## Acknowledgments

This project has been partially funded by:

- MultiplEYE COST Action, CA21131
- Swiss National Science Foundation (SNSF), 212276 (MeRID)
- swissuniversities, OpenEye

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
