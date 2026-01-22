"""Authentication middleware and utilities."""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import APIKey

settings = get_settings()

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Redis client for rate limiting (initialized in main.py)
redis_client: Optional[Redis] = None


def set_redis_client(client: Redis) -> None:
    """Set the Redis client for rate limiting."""
    global redis_client
    redis_client = client


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
    """
    # Generate random key
    random_part = secrets.token_urlsafe(32)
    full_key = f"{settings.api_key_prefix}{random_part}"

    # Create prefix for identification (first 8 chars after prefix)
    key_prefix = full_key[: len(settings.api_key_prefix) + 8]

    # Hash the key for storage
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    return full_key, key_prefix, key_hash


def hash_api_key(key: str) -> str:
    """Hash an API key for comparison."""
    return hashlib.sha256(key.encode()).hexdigest()


async def check_rate_limit(api_key_id: str, limit: int) -> bool:
    """Check if the request is within rate limits.

    Args:
        api_key_id: The API key ID
        limit: Requests per minute allowed

    Returns:
        True if within limits, False if exceeded
    """
    if redis_client is None:
        return True

    key = f"rate_limit:{api_key_id}"
    current_minute = int(datetime.now(timezone.utc).timestamp() / 60)
    rate_key = f"{key}:{current_minute}"

    try:
        # Increment counter
        count = await redis_client.incr(rate_key)

        # Set expiry on first request
        if count == 1:
            await redis_client.expire(rate_key, 120)  # 2 minutes TTL

        return count <= limit
    except Exception:
        # If Redis fails, allow the request
        return True


async def get_api_key(
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Validate API key and return the APIKey model.

    Args:
        api_key: The API key from header
        db: Database session

    Returns:
        The validated APIKey model

    Raises:
        HTTPException: If key is invalid, expired, or rate limited
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Hash the provided key
    key_hash = hash_api_key(api_key)

    # Look up the key
    result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
    db_key = result.scalar_one_or_none()

    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not db_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is deactivated",
        )

    if db_key.expires_at and db_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has expired",
        )

    # Check rate limit
    if not await check_rate_limit(str(db_key.id), db_key.rate_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    # Update last used timestamp
    db_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return db_key


def require_scope(required_scope: str):
    """Dependency to check if API key has required scope."""

    async def check_scope(api_key: APIKey = Depends(get_api_key)) -> APIKey:
        if required_scope not in api_key.scopes and "*" not in api_key.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required_scope}' required",
            )
        return api_key

    return check_scope
