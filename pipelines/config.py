from __future__ import annotations

import os as _os

# Packaging
MAIN_PACKAGE = "app"
TEST_PACKAGE = "tests"
EXAMPLE_SCRIPTS = "examples"

# Directories
ARTIFACT_DIRECTORY = "public"
DOCUMENTATION_DIRECTORY = "docs"
DEV_REQUIREMENTS_DIRECTORY = "dev-requirements"

# Linting and test configs
FLAKE8_REPORT = _os.path.join(ARTIFACT_DIRECTORY, "flake8")
PYPROJECT_TOML = "pyproject.toml"
COVERAGE_HTML_PATH = _os.path.join(ARTIFACT_DIRECTORY, "coverage", "html")

if "READTHEDOCS_OUTPUT" in _os.environ:
    DOCUMENTATION_OUTPUT_PATH = _os.environ["READTHEDOCS_OUTPUT"] + "/html"
else:
    DOCUMENTATION_OUTPUT_PATH = _os.path.join(ARTIFACT_DIRECTORY, "docs")


# Reformatting paths
REFORMATTING_FILE_EXTS = (
    ".py",
    ".pyx",
    ".pyi",
    ".c",
    ".cpp",
    ".cxx",
    ".hpp",
    ".hxx",
    ".h",
    ".yml",
    ".yaml",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".css",
    ".md",
    ".dockerfile",
    "Dockerfile",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".dockerignore",
    ".flake8",
    ".txt",
    ".sh",
    ".bat",
    ".ps1",
    ".rb",
    ".pl",
)

PYTHON_REFORMATTING_PATHS = (
    MAIN_PACKAGE,
    TEST_PACKAGE,
    "pipelines",
    "noxfile.py",
)

FULL_REFORMATTING_PATHS = (
    *PYTHON_REFORMATTING_PATHS,
    *(
        f
        for f in _os.listdir(".")
        if _os.path.isfile(f) and f.endswith(REFORMATTING_FILE_EXTS)
    ),
    ".github",
)

SKIP_FILE_EXTENSIONS = ("*.json",)
