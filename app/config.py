import os
import secrets
import typing
import typing as t
from pathlib import Path

import dotenv

dotenv.load_dotenv()

__all__: typing.Sequence[str] = ("CONFIG", "ConfigEnv")


class ConfigMeta(type):
    def resolve_value(cls, value: str) -> t.Any:
        _map: dict[str, t.Callable[[str], t.Any]] = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "set": lambda x: set([cls.resolve_value(e.strip()) for e in x.split(",")]),
            "file": lambda x: Path(x).read_text().strip("\n"),
        }
        return _map[(v := value.split(":", maxsplit=1))[0]](v[1])

    def resolve_key(cls, key: str) -> t.Any:
        try:
            return cls.resolve_key(os.environ[key])
        except Exception:
            return cls.resolve_value(key)

    def __getattr__(cls, name: str) -> t.Any:
        try:
            return cls.resolve_key(name)
        except KeyError:
            raise AttributeError(f"{name} is not a key in config.") from None

    def __getitem__(cls, name: str) -> t.Any:
        return cls.__getattr__(name)


class ConfigEnv(metaclass=ConfigMeta):
    SECRET_KEY: str = secrets.token_urlsafe(32)


CONFIG = ConfigEnv
