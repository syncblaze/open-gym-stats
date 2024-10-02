from __future__ import annotations

import typing
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import Permissions

from .database import Base

__all__: typing.Sequence[str] = ("User", "Email", "RecoveryCode")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[Email] = relationship(back_populates="user")
    username: Mapped[str] = mapped_column(String(255))
    password: Mapped[bytes] = mapped_column(LargeBinary)
    salt: Mapped[bytes] = mapped_column(LargeBinary)
    banned: Mapped[bool] = mapped_column(server_default=text(f"false"))
    permissions: Mapped[int] = mapped_column(
        default=Permissions.ME.value, server_default=text(f"'{Permissions.ME.value}'")
    )
    owner: Mapped[bool] = mapped_column(server_default=text(f"false"))
    mfa: Mapped[bool] = mapped_column(server_default=text(f"false"))
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text(f"now()")
    )

    recovery_codes: Mapped[List["RecoveryCode"]] = relationship(back_populates="user")


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="recovery_codes")
    used: Mapped[bool] = mapped_column(server_default=text(f"false"))


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="email")
    email: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    verified: Mapped[bool] = mapped_column(server_default=text(f"false"))
