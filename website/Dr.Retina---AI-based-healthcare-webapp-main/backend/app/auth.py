from dataclasses import dataclass
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .db import one, transaction

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    session_id: UUID
    email: str


async def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication required")
    cfg = settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{cfg.supabase_url}/auth/v1/user",
                headers={
                    "apikey": cfg.supabase_publishable_key,
                    "Authorization": f"Bearer {credentials.credentials}",
                },
            )
        if response.status_code != 200:
            raise HTTPException(401, "Session expired or invalid")
        user = response.json()
        # Only decode after Supabase has verified this exact token. Never authorize from metadata.
        claims = jwt.decode(credentials.credentials, options={"verify_signature": False})
        if claims.get("sub") != user["id"] or not user.get("email_confirmed_at"):
            raise HTTPException(401, "Verified email and valid session required")
        return Identity(UUID(user["id"]), UUID(claims["session_id"]), user.get("email", ""))
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError, jwt.PyJWTError):
        raise HTTPException(401, "Unable to validate session") from None


async def context(who: Identity = Depends(identity)):
    async with transaction(who.user_id, who.session_id) as conn:
        member = await one(conn, "select * from retina.members where user_id=%s and active", (who.user_id,))
        if not member:
            raise HTTPException(403, "No active organization membership")
        yield conn, member, who


def require(member, *roles):
    if member["role"] not in roles:
        raise HTTPException(403, "This action is not permitted for your role")
