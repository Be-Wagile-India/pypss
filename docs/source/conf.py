# Configuration file for the Sphinx documentation builder.
import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "pypss"
copyright = "2025, Saidatta Teja Ghanta"
author = "Saidatta Teja Ghanta"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

# -- Options for sphinx_autodoc_typehints ------------------------------------
typehints_use_igeneric = False
autodoc_type_aliases = {"Redis": "redis.Redis"}

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
