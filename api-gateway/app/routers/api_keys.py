"""API Key management router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_api_key, get_api_key, require_scope
from app.database import get_db
from app.models import APIKey
from app.schemas import APIKeyCreate, APIKeyResponse, APIKeyWithSecret, ErrorResponse, SuccessResponse

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get(
    "",
    response_model=list[APIKeyResponse],
    summary="List API keys",
    description="List all API keys (requires admin scope)",
)
async def list_api_keys(
    api_key: APIKey = Depends(require_scope("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyResponse]:
    """List all API keys."""
    result = await db.execute(select(APIKey))
    keys = result.scalars().all()
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.post(
    "",
    response_model=APIKeyWithSecret,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key. The key is only shown once.",
)
async def create_api_key(
    request: APIKeyCreate,
    api_key: APIKey = Depends(require_scope("admin")),
    db: AsyncSession = Depends(get_db),
) -> APIKeyWithSecret:
    """Create a new API key."""
    full_key, key_prefix, key_hash = generate_api_key()

    new_key = APIKey(
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=request.scopes,
        rate_limit=request.rate_limit,
        expires_at=request.expires_at,
    )

    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return APIKeyWithSecret(
        id=new_key.id,
        name=new_key.name,
        key_prefix=new_key.key_prefix,
        scopes=new_key.scopes,
        rate_limit=new_key.rate_limit,
        is_active=new_key.is_active,
        created_at=new_key.created_at,
        expires_at=new_key.expires_at,
        last_used_at=new_key.last_used_at,
        key=full_key,
    )


@router.get(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Get API key",
    description="Get details of a specific API key",
    responses={404: {"model": ErrorResponse}},
)
async def get_api_key_by_id(
    key_id: UUID,
    api_key: APIKey = Depends(require_scope("admin")),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """Get a specific API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    return APIKeyResponse.model_validate(key)


@router.delete(
    "/{key_id}",
    response_model=SuccessResponse,
    summary="Delete API key",
    description="Delete an API key",
    responses={404: {"model": ErrorResponse}},
)
async def delete_api_key(
    key_id: UUID,
    api_key: APIKey = Depends(require_scope("admin")),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Delete an API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if key.id == api_key.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the API key you are using",
        )

    await db.delete(key)
    await db.commit()

    return SuccessResponse(message="API key deleted successfully")


@router.post(
    "/{key_id}/toggle",
    response_model=APIKeyResponse,
    summary="Toggle API key",
    description="Enable or disable an API key",
    responses={404: {"model": ErrorResponse}},
)
async def toggle_api_key(
    key_id: UUID,
    api_key: APIKey = Depends(require_scope("admin")),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """Toggle API key active status."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if key.id == api_key.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate the API key you are using",
        )

    key.is_active = not key.is_active
    await db.commit()
    await db.refresh(key)

    return APIKeyResponse.model_validate(key)
