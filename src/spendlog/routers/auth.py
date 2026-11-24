from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.crud import user as user_crud
from spendlog.dependencies import CurrentUserDep, SessionDep
from spendlog.models import RefreshToken, User
from spendlog.schemas.auth import Token, UserCreate, UserRead
from spendlog.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    hash_password_async,
    hash_refresh_token,
    verify_password_async,
)
from spendlog.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE_KEY = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"


@dataclass(frozen=True)
class _RefreshTokenData:
    raw_token: str
    token_hash: str
    expires_at: datetime


def _build_refresh_token_data() -> _RefreshTokenData:
    settings = get_settings()
    raw_token, token_hash = create_refresh_token()
    expires_at = datetime.now(tz=UTC) + settings.refresh_token_ttl
    return _RefreshTokenData(raw_token, token_hash, expires_at)


async def _issue_refresh_token(
    session: AsyncSession, user_id: int, family_id: UUID
) -> str:
    token_data = _build_refresh_token_data()
    await refresh_token_crud.create(
        session=session,
        user_id=user_id,
        expires_at=token_data.expires_at,
        family_id=family_id,
        token_hash=token_data.token_hash,
    )
    return token_data.raw_token


async def _rotate_refresh_token(
    session: AsyncSession, old_refresh_token: RefreshToken
) -> str:
    new_token_data = _build_refresh_token_data()
    await refresh_token_crud.rotate(
        session,
        old_refresh_token,
        new_token_data.expires_at,
        new_token_data.token_hash,
    )
    return new_token_data.raw_token


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_KEY,
        value=raw_token,
        max_age=settings.cookie_max_age,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid"
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def register(data: UserCreate, session: SessionDep) -> User:
    hashed_password = await hash_password_async(data.password)
    try:
        return await user_crud.create(
            session=session, email=data.email, password_hash=hashed_password
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from None


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
    response: Response,
) -> Token:
    user = await user_crud.get_by_email(session=session, email=form.username)
    hashed = user.password_hash if user else DUMMY_HASH
    password_ok = await verify_password_async(form.password, hashed)

    if user is None or not password_ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = await _issue_refresh_token(session, user.id, uuid4())
    await session.commit()
    _set_refresh_cookie(response, raw_token)
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUserDep) -> User:
    return user


@router.post("/refresh", response_model=Token)
async def refresh(
    session: SessionDep,
    response: Response,
    raw_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_KEY)] = None,
) -> Token:
    if raw_token is None:
        raise _invalid_refresh_token()

    old_refresh_token = await refresh_token_crud.get_by_hash(
        session, hash_refresh_token(raw_token)
    )
    if old_refresh_token is None:
        raise _invalid_refresh_token()

    if old_refresh_token.used_at is not None:
        await refresh_token_crud.revoke_family(session, old_refresh_token.family_id)
        await session.commit()
        raise _invalid_refresh_token()

    if not refresh_token_crud.is_valid(old_refresh_token):
        raise _invalid_refresh_token()

    new_refresh_token = await _rotate_refresh_token(session, old_refresh_token)
    await session.commit()
    _set_refresh_cookie(response, new_refresh_token)
    return Token(access_token=create_access_token(old_refresh_token.user_id))
