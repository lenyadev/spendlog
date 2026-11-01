from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from spendlog.models import User
from spendlog.schemas.auth import UserCreate, UserRead
from spendlog.security import hash_password
from spendlog.session import SessionDep

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
