from __future__ import annotations

from pipelines import config, nox

IGNORED_WORDS = ["ro", "falsy", "ws"]


@nox.session()
def codespell(session: nox.Session) -> None:
    """Run codespell to check for spelling mistakes."""
    session.install(*nox.dev_requirements("codespell"))
    session.run(
        "codespell",
        "--builtin",
        "clear,rare,code",
        "--ignore-words-list",
        ",".join(IGNORED_WORDS),
        "--skip",
        ",".join(config.SKIP_FILE_EXTENSIONS),
        *config.FULL_REFORMATTING_PATHS,
    )
