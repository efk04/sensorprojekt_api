# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Make the isx3_api package importable for autodoc
sys.path.insert(0, os.path.abspath('../isx3_api/src'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'isx3_api'
copyright = '2026, Martin Engelke, Fedor Keil'
author = 'Martin Engelke, Fedor Keil'
release = '01.08.2026'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'myst_parser',          # Markdown (.md) pages
    'sphinx.ext.autodoc',   # API docs from docstrings
    'sphinx.ext.napoleon',  # Google/NumPy-style docstrings
    'sphinx.ext.viewcode',  # "[source]" links to the highlighted source code
]

# Markdown extensions: ::: fences for admonitions, definition lists
myst_enable_extensions = [
    'colon_fence',
    'deflist',
]
# Create anchors for headings up to level 3 (for links like page.md#section)
myst_heading_anchors = 3

# Third-party packages that are not installed on Read the Docs.
# autodoc replaces them with mock objects, so the modules can be imported.
autodoc_mock_imports = [
    'serial',
    'numpy',
    'shapely',
    'matplotlib',
    'h5py',
    'keyboard',
]

# Keep the order of members like in the source code
autodoc_member_order = 'bysource'

# Show type hints in the parameter description instead of the signature
autodoc_typehints = 'description'

# Show "Attributes" as a field list (like "Parameters") instead of separate entries
napoleon_use_ivar = True

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

language = 'de'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_title = 'isx3_api documentation'

html_theme_options = {
    'navigation_depth': 3,          # show page sections in the sidebar
    'collapse_navigation': False,   # keep the sidebar tree expanded
    'sticky_navigation': True,      # sidebar scrolls with the page
}
