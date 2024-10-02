import secrets
import string
import typing
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import and_, cast, or_
from sqlalchemy.orm import Session, aliased
from sqlalchemy.types import String
from starlette.requests import Request

from app.enums import Permissions

from . import models, schemas


def get_user(db: Session, user_id: int) -> models.User | None:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    db.expire(user)
    return user


def get_email_by_email(db: Session, email: str) -> models.Email | None:
    email = db.query(models.Email).filter(models.Email.email == email).first()
    return email


def get_user_by_email(db: Session, email: str):
    email = get_email_by_email(db, email)
    if not email:
        return None
    user = get_user(db, email.user_id)
    return user


def get_user_by_username(db: Session, username: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    return user


def verify_password(db: Session, user_id: int, password: str) -> bool:
    user = get_user(db, user_id)
    assert user is not None
    hashed_input_password = bcrypt.hashpw(password.encode("utf-8"), user.salt)
    return hashed_input_password == user.password


def verify_email(db: Session, user_id: int):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.email.verified = True
    db.commit()
    return user


def add_2fa_secret(db: Session, user_id: int, mfa_secret: str):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.mfa_secret = mfa_secret
    db.commit()
    return user


def generate_recovery_codes(db: Session, user_id: int):
    characters = characters = string.ascii_letters + string.digits
    codes = [
        "".join(secrets.choice(characters) for _ in range(4))
        + " "
        + "".join(secrets.choice(characters) for _ in range(4))
        for _ in range(8)
    ]
    for code in codes:
        code = models.RecoveryCode(code=code, user_id=user_id)
        db.add(code)
        db.commit()
        db.refresh(code)
    return codes


def activate_2fa(db: Session, user_id: int):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.mfa = True
    db.commit()
    for code in user.recovery_codes:
        db.refresh(code)
        db.delete(code)
        db.commit()
    db.refresh(user)
    return generate_recovery_codes(db, user_id)


def deactivate_2fa(db: Session, user_id: int):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.mfa = False
    user.mfa_secret = None
    db.commit()
    for code in user.recovery_codes:
        db.refresh(code)
        db.delete(code)
        db.commit()
    db.refresh(user)
    return user


def get_recovery_code(db: Session, code_id) -> models.RecoveryCode | None:
    code = (
        db.query(models.RecoveryCode).filter(models.RecoveryCode.id == code_id).first()
    )
    return code


def set_recovery_code_used(db: Session, code_id):
    code = get_recovery_code(db, code_id)
    assert code is not None
    code.used = True
    db.add(code)
    db.commit()
    db.refresh(code)
    return code


def create_user(db: Session, user: schemas.UserCreate):
    salt: bytes = bcrypt.gensalt()
    user_dump = user.model_dump()
    hashed_password = bcrypt.hashpw(user_dump.pop("password").encode("utf-8"), salt)
    email = user_dump.pop("email")
    db_user = models.User(**user_dump, salt=salt, password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    db_email = models.Email(user_id=db_user.id, email=email)
    db.add(db_email)
    db.commit()
    db.refresh(db_email)
    db.refresh(db_user)
    return db_user, db_email


def delete_user(db: Session, user_id: int):
    user = get_user(db, user_id)
    assert user is not None
    db.delete(user.email)
    for code in user.recovery_codes:
        db.delete(code)
    for var in user.variables:
        db.delete(var)
    db.delete(user)
    db.commit()
    return user


def change_password(db: Session, user_id: int, password: str):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), user.salt)
    user.password = hashed_password
    db.commit()
    return user


def has_permission(permission_field, required_permission):
    return permission_field.bitwise_and(required_permission.value) != 0


def get_users(
    db: Session,
    page: int,
    limit: int,
    search: str | None = None,
    permissions: Permissions | None = None,
) -> typing.List[models.User]:
    query = db.query(models.User)

    if search:
        query = query.join(models.Email)

        # Filter by either email or username
        query = query.filter(
            or_(
                models.Email.email.contains(search),
                models.User.username.contains(search),
            )
        )

    if permissions is not None:
        query = query.filter(has_permission(models.User.permissions, permissions))

    # Implement pagination
    offset = page * limit
    users = query.offset(offset).limit(limit).all()

    return users


def edit_user_email(db: Session, user_id: int, email: str):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.email.email = email
    user.email.verified = False
    db.commit()
    return user


def set_user_banned(db: Session, user_id: int, banned: bool):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.banned = banned
    db.commit()
    return user


def update_user_permissions(
    db: Session, user_id: int, permissions: schemas.EditPermissions
):
    user = get_user(db, user_id)
    assert user is not None
    db.add(user)
    user.permissions = permissions.permissions
    db.commit()
    return user
