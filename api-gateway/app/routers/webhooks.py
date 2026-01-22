"""Webhook management router."""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_api_key, require_scope
from app.database import get_db
from app.models import APIKey, Webhook
from app.schemas import ErrorResponse, SuccessResponse, WebhookCreate, WebhookResponse, WebhookWithSecret

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.get(
    "",
    response_model=list[WebhookResponse],
    summary="List webhooks",
    description="List all webhooks for the authenticated API key",
)
async def list_webhooks(
    api_key: APIKey = Depends(require_scope("read")),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookResponse]:
    """List all webhooks."""
    result = await db.execute(select(Webhook).where(Webhook.api_key_id == api_key.id))
    webhooks = result.scalars().all()
    return [WebhookResponse.model_validate(w) for w in webhooks]


@router.post(
    "",
    response_model=WebhookWithSecret,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Create a new webhook endpoint. The secret is only shown once.",
)
async def create_webhook(
    request: WebhookCreate,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> WebhookWithSecret:
    """Create a new webhook."""
    # Generate secret
    webhook_secret = secrets.token_urlsafe(32)

    webhook = Webhook(
        api_key_id=api_key.id,
        url=str(request.url),
        events=request.events,
        secret=webhook_secret,
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return WebhookWithSecret(
        id=webhook.id,
        url=webhook.url,
        events=webhook.events,
        is_active=webhook.is_active,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
        secret=webhook_secret,
    )


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook",
    description="Get details of a specific webhook",
    responses={404: {"model": ErrorResponse}},
)
async def get_webhook(
    webhook_id: UUID,
    api_key: APIKey = Depends(require_scope("read")),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Get a specific webhook."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == api_key.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    return WebhookResponse.model_validate(webhook)


@router.delete(
    "/{webhook_id}",
    response_model=SuccessResponse,
    summary="Delete webhook",
    description="Delete a webhook",
    responses={404: {"model": ErrorResponse}},
)
async def delete_webhook(
    webhook_id: UUID,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Delete a webhook."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == api_key.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()

    return SuccessResponse(message="Webhook deleted successfully")


@router.post(
    "/{webhook_id}/toggle",
    response_model=WebhookResponse,
    summary="Toggle webhook",
    description="Enable or disable a webhook",
    responses={404: {"model": ErrorResponse}},
)
async def toggle_webhook(
    webhook_id: UUID,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Toggle webhook active status."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == api_key.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    webhook.is_active = not webhook.is_active
    await db.commit()
    await db.refresh(webhook)

    return WebhookResponse.model_validate(webhook)
