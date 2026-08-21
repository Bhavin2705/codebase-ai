import secrets
from fastapi import Header, HTTPException, status
from app.config import settings


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """FastAPI dependency to verify API access key using constant-time comparison against timing attacks."""
    expected = (settings.API_ACCESS_KEY or "").strip()
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
