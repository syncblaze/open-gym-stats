"""Wrapper around nox to give default job kwargs."""

from __future__ import annotations

import os as _os
import typing as _typing

from nox import options as _options
from nox import session as _session
from nox.sessions import Session

from pipelines import config as _pipelines_config

try:
    import uv

    del uv

    venv_backend = "uv"
except ModuleNotFoundError:
    venv_backend = "venv"


# Default sessions should be defined here
_options.sessions = ["reformat-code", "codespell", "type-check"]
_options.default_venv_backend = venv_backend

_NoxCallbackSig = _typing.Callable[[Session], None]


def session(
    **kwargs: _typing.Any,
) -> _typing.Callable[[_NoxCallbackSig], _NoxCallbackSig]:
    def decorator(func: _NoxCallbackSig) -> _NoxCallbackSig:
        name = func.__name__.replace("_", "-")
        reuse_venv = kwargs.pop("reuse_venv", True)
        return _session(name=name, reuse_venv=reuse_venv, **kwargs)(func)

    return decorator


def dev_requirements(*dependencies: str) -> _typing.Sequence[str]:
    args = []

    for dep in dependencies:
        args.extend(
            (
                "-r",
                _os.path.join(
                    _pipelines_config.DEV_REQUIREMENTS_DIRECTORY, f"{dep}.txt"
                ),
            )
        )

    return args
