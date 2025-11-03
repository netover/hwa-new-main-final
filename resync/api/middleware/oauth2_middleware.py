from __future__ import annotations

from collections.abc import Callable

from fastapi import Request
from fastapi.exceptions import HTTPException
from jose import JWTError
from resync.security.oauth2 import verify_oauth2_token


# --- OAuth2 Middleware ---
async def oauth2_middleware(request: Request, call_next: Callable):
    """
    Middleware to enforce OAuth2/JWT authentication for all routes.
    """
    try:
        # Get token from Authorization header
        token = request.headers.get("Authorization")
        if not token or not token.startswith("Bearer "):
            raise HTTPException(
                status_code=401, detail="Missing Authorization header"
            )

        # Verify token
        token_value = token.split(" ")[1]
        user = await verify_oauth2_token(token_value)

        # Add user to request state for downstream use
        request.state.user = user

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    # Proceed to next middleware or route handler
    return await call_next(request)




