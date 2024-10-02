import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pyotp
from expiringdict import ExpiringDict
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Security,
    status,
)
from fastapi.security import SecurityScopes
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app import CONFIG
from app.dependencies import (
    OAuth2PasswordRequestForm,
    get_db,
    oauth2_scheme,
)
from app.enums import Permissions
from app.sql import crud, models, schemas

router = APIRouter(
    prefix="/authentication",
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token expired",
    headers={"WWW-Authenticate": "Bearer"},
)
MAIL_NOT_VERIFIED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Email not verified",
    headers={"WWW-Authenticate": "Bearer"},
)
NEW_MAIL = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="New email set",
    headers={"WWW-Authenticate": "Bearer"},
)

DISCORD_STATE_SECRET = secrets.token_hex(16)
PERMS_ME = Permissions.ME

cache = ExpiringDict(
    max_len=200, max_age_seconds=CONFIG.ACCESS_TOKEN_EXPIRE_MINUTES * 60
)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, CONFIG.SECRET_KEY, algorithm=CONFIG.ALGORITHM)
    return encoded_jwt


async def get_current_user(
    security_scopes: SecurityScopes,
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    if cache.get(token):
        raise CREDENTIALS_EXCEPTION
    try:
        payload = jwt.decode(token, CONFIG.SECRET_KEY, algorithms=[CONFIG.ALGORITHM])
        username: str | None = payload.get("sub")
        email: str | None = payload.get("email")
        user_agent: str | None = payload.get("user_agent")
        if user_agent != request.headers.get("User-Agent", "Null"):
            cache[token] = True
            raise CREDENTIALS_EXCEPTION
        if username is None or email is None:
            raise CREDENTIALS_EXCEPTION
        token_scopes = payload.get("scopes", [])
    except JWTError:
        raise CREDENTIALS_EXCEPTION
    user = crud.get_user_by_username(db=db, username=username)
    if user is None:
        raise CREDENTIALS_EXCEPTION
    # if not user.email.verified:
    #    raise MAIL_NOT_VERIFIED
    if user.email.email != email:
        raise NEW_MAIL
    print(token_scopes)
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
        if user.owner:
            continue
        user_scopes = Permissions(user.permissions).get_scopes()
        if scope == "OWNER" and not user.owner:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
        elif scope not in user_scopes and scope != "OWNER":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user


async def get_current_active_user(
    current_user: Annotated[models.User, Security(get_current_user, scopes=[])],
    db: Annotated[Session, Depends(get_db)],
):
    if current_user.banned:
        raise HTTPException(status_code=400, detail="Banned user")
    return current_user


@router.post("/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    background_task: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db=db, username=form_data.username)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="The combination of username/email and passwort is incorrect",
        )
    if not crud.verify_password(db, user.id, form_data.password):
        raise HTTPException(
            status_code=400,
            detail="The combination of username/email and passwort is incorrect",
        )
    # if not user.email.verified:
    #    raise MAIL_NOT_VERIFIED
    if user.mfa:
        if not form_data.mfa:
            raise HTTPException(status_code=401, detail="2FA is required")
        assert user.mfa_secret is not None
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(form_data.mfa):
            f = False
            for c in user.recovery_codes:
                if c.code == form_data.mfa:
                    if c.used:
                        raise HTTPException(
                            status_code=400, detail="Recovery code already used!"
                        )
                    f = True
                    crud.set_recovery_code_used(db=db, code_id=c.id)
            if not f:
                raise HTTPException(status_code=400, detail="Invalid 2fa code")

    access_token_expires = timedelta(minutes=CONFIG.ACCESS_TOKEN_EXPIRE_MINUTES)
    if user.owner:
        form_data.scopes.append("OWNER")
    access_token = create_access_token(
        data={
            "sub": user.username,
            "email": user.email.email,
            "scopes": form_data.scopes,
            "ip": request.client.host if request.client else "Null",
            "user_agent": request.headers.get("User-Agent", "Null"),
        },
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}
