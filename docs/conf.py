import os
import sys

DEFAULT_ENV_VARS = {
    "DBUSER": "docs",
    "DBPASS": "docs",
    "DBHOST": "localhost",
    "DBPORT": "5432",
    "DBNAME": "docs",
    "FLASKSECRET": "docssecret",
}
for env_key, env_value in DEFAULT_ENV_VARS.items():
    os.environ.setdefault(env_key, env_value)

sys.path.insert(0, os.path.abspath("../src"))

project = "DB Interop Registry Backend"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]
autosummary_generate = True
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_last_updated_fmt = "%Y-%m-%d"
suppress_warnings = ["ref.ref"]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
