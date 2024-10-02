from datetime import datetime, timedelta
from typing import Annotated

import pyotp
from email_validator import EmailNotValidError, validate_email
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
)
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.enums import Permissions
from app.sql import crud, models, schemas

from .authentication import get_current_active_user

router = APIRouter(
    prefix="/users", tags=["users"], responses={404: {"description": "Not found"}}
)

PERMS_ME = Permissions.ME


def is_valid_2fa_token(token: str, user: models.User, db: Session):
    assert user.mfa_secret is not None
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(token):
        f = False
        for c in user.recovery_codes:
            if c.code == token:
                if c.used:
                    raise HTTPException(
                        status_code=400, detail="Recovery code already used!"
                    )
                f = True
                crud.set_recovery_code_used(db=db, code_id=c.id)
        return f
    else:
        return True


@router.get(
    "/@me",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=2, seconds=1))],
)
def read_user_me(
    current_user: Annotated[
        schemas.User, Security(get_current_active_user, scopes=PERMS_ME.gs())
    ],
):
    return current_user


@router.post(
    "/",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    try:
        email_info = validate_email(user.email)
        user.email = email_info.normalized
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Email not valid")
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password too short")
    user, email = crud.create_user(db=db, user=user)

    return user


@router.get("/@me/2fa")
def activate_own_2fa(
    current_user: Annotated[
        schemas.User, Security(get_current_active_user, scopes=PERMS_ME.gs())
    ],
    db: Session = Depends(get_db),
):
    if current_user.mfa:
        raise HTTPException(status_code=400, detail="You already have 2fa enabled!")
    mfa_secret = pyotp.random_base32()
    crud.add_2fa_secret(db=db, user_id=int(current_user.id), mfa_secret=mfa_secret)
    uri = pyotp.TOTP(mfa_secret).provisioning_uri(
        name=current_user.username, issuer_name="Synccord"
    )
    return {"uri": uri}


@router.post("/@me/2fa")
def activate_2fa(
    activate2fa: schemas.Activate2fa,
    request: Request,
    current_user: Annotated[
        models.User, Security(get_current_active_user, scopes=PERMS_ME.gs())
    ],
    db: Session = Depends(get_db),
):
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=400, detail="You need to register a 2fa to activate"
        )
    if current_user.mfa:
        raise HTTPException(status_code=400, detail="You already have 2fa activated")
    totp = pyotp.TOTP(current_user.mfa_secret)
    if not totp.verify(activate2fa.token):
        raise HTTPException(status_code=400, detail="Wrong 2fa code")
    backup_codes = crud.activate_2fa(db=db, user_id=int(current_user.id))
    return {"status": "2fa activated", "backup_codes": backup_codes}


@router.delete("/@me/2fa")
def deactivate_2fa(
    deactivate2fa: schemas.Deactivate2fa,
    request: Request,
    current_user: Annotated[
        models.User, Security(get_current_active_user, scopes=PERMS_ME.gs())
    ],
    db: Session = Depends(get_db),
):
    if not current_user.mfa_secret or not current_user.mfa:
        raise HTTPException(status_code=400, detail="You don't have 2fa activated")
    if not crud.verify_password(
        db=db, user_id=int(current_user.id), password=deactivate2fa.password
    ):
        raise HTTPException(status_code=400, detail="Wrong Password")
    totp = pyotp.TOTP(current_user.mfa_secret)
    if not totp.verify(deactivate2fa.token):
        raise HTTPException(status_code=400, detail="Wrong 2fa code")

    crud.deactivate_2fa(db=db, user_id=int(current_user.id))
    return {"status": "2fa deactivated"}


@router.delete(
    "/@me",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=1, seconds=7))],
)
def delete_own_user_route(
    delete_user: schemas.DeleteUser,
    request: Request,
    current_user: Annotated[
        models.User, Security(get_current_active_user, scopes=PERMS_ME.gs())
    ],
    db: Session = Depends(get_db),
):
    if not crud.verify_password(
        db=db, user_id=int(current_user.id), password=delete_user.password
    ):
        raise HTTPException(status_code=400, detail="Wrong Password")
    if current_user.mfa and not delete_user.token:
        raise HTTPException(status_code=400, detail="2fa is required")
    if current_user.mfa:
        if delete_user.token is None:
            raise HTTPException(status_code=400, detail="2fa code is required")
        if not is_valid_2fa_token(delete_user.token, current_user, db):
            raise HTTPException(status_code=400, detail="Invalid 2fa code")

    res = crud.delete_user(db=db, user_id=int(current_user.id))
    return res


@router.patch(
    "/@me/password",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=1, seconds=7))],
)
def change_password(
    change_password: schemas.ChangePassword,
    request: Request,
    current_user: Annotated[
        models.User, Security(get_current_active_user, scopes=PERMS_ME.gs())
    ],
    db: Session = Depends(get_db),
):
    if not crud.verify_password(
        db=db, user_id=int(current_user.id), password=change_password.old_password
    ):
        raise HTTPException(status_code=400, detail="Wrong Password")
    if current_user.mfa and not change_password.token:
        raise HTTPException(status_code=400, detail="2fa is required")
    if current_user.mfa:
        if change_password.token is None:
            raise HTTPException(status_code=400, detail="2fa code is required")
        if not is_valid_2fa_token(change_password.token, current_user, db):
            raise HTTPException(status_code=400, detail="Invalid 2fa code")

    if change_password.old_password == change_password.new_password:
        raise HTTPException(
            status_code=400, detail="Old password and new password are the same"
        )
    if len(change_password.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password too short")

    res = crud.change_password(
        db=db, user_id=int(current_user.id), password=change_password.new_password
    )
    return res


PERMS_VIEW_USERS = Permissions.VIEW_USERS


@router.get(
    "/",
    response_model=list[schemas.User],
    dependencies=[Depends(RateLimiter(times=1, seconds=2))],
)
def get_users(
    current_user: Annotated[
        schemas.User, Security(get_current_active_user, scopes=PERMS_VIEW_USERS.gs())
    ],
    search: str = Query(None, title="Search string"),
    page: int = Query(0, ge=0),
    limit: int = Query(25, ge=1),
    db: Session = Depends(get_db),
):
    return crud.get_users(db=db, search=search, page=page, limit=limit)


@router.get(
    "/{user_id}",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=1, seconds=2))],
)
def get_user(
    user_id: int,
    current_user: Annotated[
        schemas.User, Security(get_current_active_user, scopes=PERMS_VIEW_USERS.gs())
    ],
    db: Session = Depends(get_db),
):
    user = crud.get_user(db=db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


PERMS_DELETE_USERS = Permissions.DELETE_USERS


@router.delete(
    "/{user_id}",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=1, seconds=10))],
)
def delete_user(
    user_id: int,
    request: Request,
    current_user: Annotated[
        schemas.User, Security(get_current_active_user, scopes=PERMS_VIEW_USERS.gs())
    ],
    db: Session = Depends(get_db),
):
    user = crud.get_user(db=db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    res = crud.delete_user(db=db, user_id=user_id)
    return res


PERMS_EDIT_USERS = Permissions.EDIT_USERS


@router.patch(
    "/{user_id}",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=1, seconds=5))],
)
def edit_user(
    user_id: int,
    user: schemas.UserEdit,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[
        schemas.User, Security(get_current_active_user, scopes=PERMS_EDIT_USERS.gs())
    ],
    db: Session = Depends(get_db),
):
    db_user = crud.get_user(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.banned is not None:
        crud.set_user_banned(db=db, user_id=user_id, banned=user.banned)
    if user.email:
        try:
            email_info = validate_email(user.email)
            user.email = email_info.normalized
        except EmailNotValidError:
            raise HTTPException(status_code=400, detail="Email not valid")
        email_user = crud.get_user_by_email(db, email=user.email)
        if email_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        crud.edit_user_email(db=db, user_id=user_id, email=user.email)
    return crud.get_user(db=db, user_id=user_id)


PERMS_DISABLE_2FA = Permissions.DISABLE_2FA


@router.delete(
    "/{user_id}/2fa",
    response_model=schemas.User,
    dependencies=[Depends(RateLimiter(times=1, seconds=5))],
)
def deactivate_user_2fa(
    user_id: int,
    request: Request,
    current_user: Annotated[
        schemas.User, Security(get_current_active_user, scopes=PERMS_DISABLE_2FA.gs())
    ],
    db: Session = Depends(get_db),
):
    db_user = crud.get_user(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not db_user.mfa:
        raise HTTPException(status_code=400, detail="User does not have 2fa activated")
    crud.deactivate_2fa(db=db, user_id=user_id)
    return db_user


@router.patch("/{user_id}/permissions")
async def update_permissions(
    user_id: int,
    permissions: schemas.EditPermissions,
    request: Request,
    db: Session = Depends(get_db),
    current_user: schemas.User = Security(get_current_active_user, scopes=["OWNER"]),
):
    user = crud.get_user(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="User not found")
    crud.update_user_permissions(db=db, user_id=user_id, permissions=permissions)
    return {"detail": "Permissions updated"}
