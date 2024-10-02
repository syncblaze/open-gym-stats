from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel

from app.enums import Permissions


class UserBase(BaseModel):
    username: str


class EmailBase(BaseModel):
    email: str


class Email(EmailBase):
    id: Decimal
    user_id: Decimal
    verified: bool = False

    class Config:
        from_attributes = True


class UserCreate(UserBase):
    password: str
    email: str


class RecoveryCode(BaseModel):
    id: Decimal
    code: str
    user_id: Decimal
    used: bool

    class Config:
        from_attributes = True


class EditPermissions(BaseModel):
    permissions: Permissions


class User(UserBase):
    id: Decimal
    email: Email | None = None
    owner: bool = False
    permissions: Permissions = Permissions.ME
    banned: bool = False
    mfa: bool = False
    last_hwid_reset: datetime | None = None
    hwid: str | None = None
    ip: str | None = None
    created_at: datetime

    # recovery_codes: list[RecoveryCode] = []

    class Config:
        from_attributes = True

    """@validator('permissions', pre=True, always=True)
    def parse_permissions(cls, value):
        print("TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST ")
        if isinstance(value, int):
            return Permissions(value)
        return value"""


class SmallUser(UserBase):
    id: Decimal
    banned: bool = False
    last_hwid_reset: datetime | None = None
    hwid: str | None = None

    class Config:
        from_attributes = True


class Activate2fa(BaseModel):
    token: str

    class Config:
        from_attributes = True


class Activate2faResponse(BaseModel):
    uri: str

    class Config:
        from_attributes = True


class Deactivate2fa(BaseModel):
    password: str
    token: str

    class Config:
        from_attributes = True


class DeleteUser(BaseModel):
    password: str
    token: str | None = None

    class Config:
        from_attributes = True


class ChangePassword(BaseModel):
    old_password: str
    new_password: str

    token: str | None = None

    class Config:
        from_attributes = True


class UserEdit(BaseModel):
    email: str | None = None
    banned: bool | None = None
