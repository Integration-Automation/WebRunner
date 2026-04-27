# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath('.'))
# Reach the repo root so ``import je_web_runner`` works inside autodoc.
sys.path.insert(0, os.path.abspath(os.path.join(os.pardir, os.pardir)))

# -- Project information -----------------------------------------------------

project = 'WebRunner'
copyright = '2021 ~ 2025, JE-Chen'
author = 'JE-Chen'

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.napoleon",
    "sphinxcontrib.mermaid",
]

# Autosummary writes per-module reference pages on every build.
autosummary_generate = True
# autosectionlabel collides on common section titles (Overview, Methods,
# Parameters, plus repeated CJK headings). Prefix every label with the
# document path so duplicates become unique.
autosectionlabel_prefix_document = True
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
# Autodoc imports the modules it documents; some carry soft deps that
# aren't installed in the docs build environment, so silence them.
autodoc_mock_imports = [
    "selenium",
    "appium",
    "playwright",
    "PIL",
    "faker",
    "sqlalchemy",
    "locust",
    "opentelemetry",
    "axe_selenium_python",
    "testcontainers",
    "webdriver_manager",
    "requests",
    "dotenv",
    "defusedxml",
]

# sphinxcontrib-mermaid renders the ``.. mermaid::`` directive used in
# extended_features_doc.rst. Add ``sphinxcontrib-mermaid`` to
# ``docs/requirements.txt`` for ReadTheDocs builds.
mermaid_version = "10.9.0"

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
