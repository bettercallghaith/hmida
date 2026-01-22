"""Message sending router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_api_key, require_scope
from app.database import get_db
from app.models import APIKey, Device
from app.schemas import (
    ErrorResponse,
    MessageResponse,
    SendLocationRequest,
    SendMediaRequest,
    SendTextRequest,
)
from app.services.whatsapp import WhatsAppEngineError, whatsapp_client

router = APIRouter(prefix="/send", tags=["Messages"])


async def verify_device_ownership(
    device_id: UUID,
    api_key: APIKey,
    db: AsyncSession,
) -> Device:
    """Verify the device belongs to the API key and is connected."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.api_key_id == api_key.id,
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    if device.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device is not connected (status: {device.status})",
        )

    return device


@router.post(
    "/text",
    response_model=MessageResponse,
    summary="Send text message",
    description="Send a text message to a WhatsApp number",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def send_text(
    request: SendTextRequest,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a text message."""
    await verify_device_ownership(request.device_id, api_key, db)

    try:
        result = await whatsapp_client.send_text(
            device_id=request.device_id,
            recipient=request.recipient,
            content=request.content,
        )
        data = result.get("data", {})
        return MessageResponse(
            success=result.get("success", False),
            message_id=data.get("messageId"),
            timestamp=data.get("timestamp"),
            error=result.get("error"),
        )
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)


@router.post(
    "/image",
    response_model=MessageResponse,
    summary="Send image",
    description="Send an image message with optional caption",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def send_image(
    request: SendMediaRequest,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send an image message."""
    await verify_device_ownership(request.device_id, api_key, db)

    if not request.media_url and not request.media_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either media_url or media_base64 is required",
        )

    try:
        result = await whatsapp_client.send_image(
            device_id=request.device_id,
            recipient=request.recipient,
            media_url=request.media_url,
            media_base64=request.media_base64,
            caption=request.caption,
        )
        data = result.get("data", {})
        return MessageResponse(
            success=result.get("success", False),
            message_id=data.get("messageId"),
            timestamp=data.get("timestamp"),
            error=result.get("error"),
        )
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)


@router.post(
    "/video",
    response_model=MessageResponse,
    summary="Send video",
    description="Send a video message with optional caption",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def send_video(
    request: SendMediaRequest,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a video message."""
    await verify_device_ownership(request.device_id, api_key, db)

    if not request.media_url and not request.media_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either media_url or media_base64 is required",
        )

    try:
        result = await whatsapp_client.send_video(
            device_id=request.device_id,
            recipient=request.recipient,
            media_url=request.media_url,
            media_base64=request.media_base64,
            caption=request.caption,
            mime_type=request.mime_type,
        )
        data = result.get("data", {})
        return MessageResponse(
            success=result.get("success", False),
            message_id=data.get("messageId"),
            timestamp=data.get("timestamp"),
            error=result.get("error"),
        )
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)


@router.post(
    "/audio",
    response_model=MessageResponse,
    summary="Send audio",
    description="Send an audio message (voice note)",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def send_audio(
    request: SendMediaRequest,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send an audio message."""
    await verify_device_ownership(request.device_id, api_key, db)

    if not request.media_url and not request.media_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either media_url or media_base64 is required",
        )

    try:
        result = await whatsapp_client.send_audio(
            device_id=request.device_id,
            recipient=request.recipient,
            media_url=request.media_url,
            media_base64=request.media_base64,
            mime_type=request.mime_type,
        )
        data = result.get("data", {})
        return MessageResponse(
            success=result.get("success", False),
            message_id=data.get("messageId"),
            timestamp=data.get("timestamp"),
            error=result.get("error"),
        )
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)


@router.post(
    "/document",
    response_model=MessageResponse,
    summary="Send document",
    description="Send a document with filename",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def send_document(
    request: SendMediaRequest,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a document message."""
    await verify_device_ownership(request.device_id, api_key, db)

    if not request.media_url and not request.media_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either media_url or media_base64 is required",
        )

    try:
        result = await whatsapp_client.send_document(
            device_id=request.device_id,
            recipient=request.recipient,
            media_url=request.media_url,
            media_base64=request.media_base64,
            filename=request.filename,
            mime_type=request.mime_type,
            caption=request.caption,
        )
        data = result.get("data", {})
        return MessageResponse(
            success=result.get("success", False),
            message_id=data.get("messageId"),
            timestamp=data.get("timestamp"),
            error=result.get("error"),
        )
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)


@router.post(
    "/location",
    response_model=MessageResponse,
    summary="Send location",
    description="Send a location pin",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def send_location(
    request: SendLocationRequest,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a location message."""
    await verify_device_ownership(request.device_id, api_key, db)

    try:
        result = await whatsapp_client.send_location(
            device_id=request.device_id,
            recipient=request.recipient,
            latitude=request.latitude,
            longitude=request.longitude,
            name=request.name,
            address=request.address,
        )
        data = result.get("data", {})
        return MessageResponse(
            success=result.get("success", False),
            message_id=data.get("messageId"),
            timestamp=data.get("timestamp"),
            error=result.get("error"),
        )
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)
