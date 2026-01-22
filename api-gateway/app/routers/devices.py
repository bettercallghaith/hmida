"""Device management router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_api_key, require_scope
from app.database import get_db
from app.models import APIKey, Device
from app.schemas import DeviceCreate, DeviceResponse, DeviceWithQR, ErrorResponse, SuccessResponse
from app.services.whatsapp import WhatsAppEngineError, whatsapp_client

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get(
    "",
    response_model=list[DeviceResponse],
    summary="List devices",
    description="List all devices for the authenticated API key",
)
async def list_devices(
    api_key: APIKey = Depends(require_scope("read")),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceResponse]:
    """List all devices for the current API key."""
    result = await db.execute(
        select(Device).where(Device.api_key_id == api_key.id, Device.status != "removed")
    )
    devices = result.scalars().all()
    return [DeviceResponse.model_validate(d) for d in devices]


@router.post(
    "/add",
    response_model=DeviceWithQR,
    status_code=status.HTTP_201_CREATED,
    summary="Add device",
    description="Add a new WhatsApp device and get QR code for pairing",
    responses={503: {"model": ErrorResponse}},
)
async def add_device(
    request: DeviceCreate,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> DeviceWithQR:
    """Add a new device and get QR code."""
    try:
        result = await whatsapp_client.add_device(api_key.id, request.name)
        data = result.get("data", {})

        # Fetch the created device from database
        device_result = await db.execute(
            select(Device).where(Device.id == UUID(data.get("deviceId")))
        )
        device = device_result.scalar_one_or_none()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Device created but not found in database",
            )

        return DeviceWithQR(
            id=device.id,
            name=device.name,
            phone_number=device.phone_number,
            status=device.status,
            created_at=device.created_at,
            connected_at=device.connected_at,
            disconnected_at=device.disconnected_at,
            last_seen_at=device.last_seen_at,
            qr_code=data.get("qrCode"),
            expires_in=data.get("expiresIn", 60),
        )
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)


@router.get(
    "/{device_id}",
    response_model=DeviceResponse,
    summary="Get device",
    description="Get details of a specific device",
    responses={404: {"model": ErrorResponse}},
)
async def get_device(
    device_id: UUID,
    api_key: APIKey = Depends(require_scope("read")),
    db: AsyncSession = Depends(get_db),
) -> DeviceResponse:
    """Get a specific device."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.api_key_id == api_key.id,
            Device.status != "removed",
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    return DeviceResponse.model_validate(device)


@router.delete(
    "/{device_id}",
    response_model=SuccessResponse,
    summary="Remove device",
    description="Remove a WhatsApp device and disconnect session",
    responses={404: {"model": ErrorResponse}},
)
async def remove_device(
    device_id: UUID,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Remove a device."""
    # Verify device belongs to this API key
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.api_key_id == api_key.id,
            Device.status != "removed",
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    try:
        await whatsapp_client.remove_device(device_id)
        return SuccessResponse(message="Device removed successfully")
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)


@router.post(
    "/{device_id}/reconnect",
    response_model=SuccessResponse,
    summary="Reconnect device",
    description="Force reconnection of a disconnected device",
    responses={404: {"model": ErrorResponse}},
)
async def reconnect_device(
    device_id: UUID,
    api_key: APIKey = Depends(require_scope("write")),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Reconnect a device."""
    # Verify device belongs to this API key
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.api_key_id == api_key.id,
            Device.status != "removed",
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    try:
        await whatsapp_client.reconnect_device(device_id)
        return SuccessResponse(message="Reconnection initiated")
    except WhatsAppEngineError as e:
        raise HTTPException(status_code=e.status_code or 503, detail=e.message)
