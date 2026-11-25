from http.cookies import Morsel, SimpleCookie

from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from spendlog.crud import refresh_token as refresh_token_crud
from spendlog.models import RefreshToken
from spendlog.routers.auth import REFRESH_COOKIE_KEY
from spendlog.security import hash_refresh_token


def parse_set_cookie(response: Response) -> Morsel:
    cookie = SimpleCookie()
    set_cookie_headers = response.headers.get_list("set-cookie")[0]
    cookie.load(set_cookie_headers)
    return cookie[REFRESH_COOKIE_KEY]


async def get_refresh_token_record(
    session: AsyncSession, raw_token: str
) -> RefreshToken | None:
    return await refresh_token_crud.get_by_hash(session, hash_refresh_token(raw_token))


def raw_token_from(response: Response) -> str:
    return response.cookies[REFRESH_COOKIE_KEY]
