from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from spendlog.models import User
from spendlog.schemas.auth import Token, UserCreate, UserRead
from spendlog.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from spendlog.session import SessionDep
from spendlog.dependencies import CurrentUserDep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def register(data: UserCreate, session: SessionDep) -> User:
    user = User(email=data.email, password_hash=hash_password(data.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    return user


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> Token:
    user = await session.scalar(select(User).where(User.email == form.username))
    hashed = user.password_hash if user else DUMMY_HASH
    password_ok = verify_password(form.password, hashed)

    if user is None or not password_ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.id))

@router.get("/me", response_model=UserRead)
async def me(user: CurrentUserDep) -> User:
    return user