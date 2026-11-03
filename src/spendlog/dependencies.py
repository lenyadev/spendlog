from typing import Annotated

from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, status
from fastapi import Depends

from spendlog.session import SessionDep
from spendlog.security import decode_access_token
from spendlog.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="Not authorized",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise unauthorized()
    
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized()

    return user

CurrentUserDep = Annotated[User, Depends(get_current_user)]
    
    