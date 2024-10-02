"""Code-linting jobs."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import time
import typing

from pipelines import config, nox

GIT = shutil.which("git")


@nox.session()
def type_check(session: nox.Session) -> None:
    """Remove trailing whitespace in source and then run ruff code formatter."""
    session.install("-r", "requirements.txt", *nox.dev_requirements("pyright"))

    session.run("pyright")
