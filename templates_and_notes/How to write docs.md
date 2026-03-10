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
