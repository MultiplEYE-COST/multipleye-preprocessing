# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

from datetime import datetime

from sphinx.search import languages

project = 'MultiplEYE Preprocessing pEYEpline'
copyright = f"2024–{datetime.now().year}, Deborah N. Jakobi et al"
author = 'Deborah N. Jakobi et al.'
release = '0.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_nb",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx.ext.autosectionlabel",
    "sphinxcontrib.bibtex",
    "sphinx_design"
]

templates_path = ['_templates']
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

bibtex_bibfiles = ["refs.bib"]
bibtex_encoding = 'utf-8'
bibtex_default_style = 'alpha'

language = "en"

myst_enable_extensions = ["colon_fence", "deflist", "dollarmath", "amsmath"]
myst_links_external_new_tab = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_book_theme'
html_static_path = ['_static']
html_theme_options = {
    "repository_url": "https://github.com/theDebbister/multipleye-preprocessing/",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_edit_page_button": True,
    "path_to_docs": "docs",
}
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
    "pymovements": ("https://pymovements.readthedocs.io/en/stable/", None),
}