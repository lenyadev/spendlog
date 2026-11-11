from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError

from spendlog.crud import user as user_crud
from spendlog.dependencies import CurrentUserDep, SessionDep
from spendlog.models import User
from spendlog.schemas.auth import Token, UserCreate, UserRead
from spendlog.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password_async,
    verify_password_async,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
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

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUserDep) -> User:
    return user
