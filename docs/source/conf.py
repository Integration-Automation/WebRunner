# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath('.'))

# -- Project information -----------------------------------------------------

project = 'WebRunner'
copyright = '2021 ~ 2025, JE-Chen'
author = 'JE-Chen'

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autosectionlabel"
]

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
