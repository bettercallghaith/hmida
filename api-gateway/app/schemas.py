"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# === API Key Schemas ===


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str = Field(..., min_length=1, max_length=255, description="Name for the API key")
    scopes: list[str] = Field(default=["read", "write"], description="Permission scopes")
    rate_limit: int = Field(default=100, ge=1, le=10000, description="Requests per minute")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")


class APIKeyResponse(BaseModel):
    """Schema for API key response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit: int
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]


class APIKeyWithSecret(APIKeyResponse):
    """Schema for API key response with the secret (only shown once)."""

    key: str = Field(..., description="The full API key (only shown once)")


# === Device Schemas ===


class DeviceCreate(BaseModel):
    """Schema for creating a new device."""

    name: str = Field(..., min_length=1, max_length=255, description="Device name")


class DeviceResponse(BaseModel):
    """Schema for device response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone_number: Optional[str]
    status: str
    created_at: datetime
    connected_at: Optional[datetime]
    disconnected_at: Optional[datetime]
    last_seen_at: Optional[datetime]


class DeviceWithQR(DeviceResponse):
    """Schema for device response with QR code."""

    qr_code: Optional[str] = Field(None, description="Base64 encoded QR code image")
    expires_in: int = Field(60, description="QR code expiration in seconds")


# === Message Schemas ===


class SendTextRequest(BaseModel):
    """Schema for sending a text message."""

    device_id: UUID = Field(..., description="Device ID to send from")
    recipient: str = Field(..., min_length=1, description="Recipient phone number or JID")
    content: str = Field(..., min_length=1, description="Message text content")


class SendMediaRequest(BaseModel):
    """Schema for sending media messages."""

    device_id: UUID = Field(..., description="Device ID to send from")
    recipient: str = Field(..., min_length=1, description="Recipient phone number or JID")
    media_url: Optional[str] = Field(None, description="URL to media file")
    media_base64: Optional[str] = Field(None, description="Base64 encoded media")
    caption: Optional[str] = Field(None, description="Caption for media")
    filename: Optional[str] = Field(None, description="Filename for documents")
    mime_type: Optional[str] = Field(None, description="MIME type of media")


class SendLocationRequest(BaseModel):
    """Schema for sending location messages."""

    device_id: UUID = Field(..., description="Device ID to send from")
    recipient: str = Field(..., min_length=1, description="Recipient phone number or JID")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    name: Optional[str] = Field(None, description="Location name")
    address: Optional[str] = Field(None, description="Location address")


class MessageResponse(BaseModel):
    """Schema for message send response."""

    success: bool
    message_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    error: Optional[str] = None


# === Webhook Schemas ===


class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""

    url: HttpUrl = Field(..., description="Webhook URL")
    events: list[str] = Field(
        default=["message.received", "message.sent", "device.connected", "device.disconnected"],
        description="Events to subscribe to",
    )


class WebhookResponse(BaseModel):
    """Schema for webhook response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WebhookWithSecret(WebhookResponse):
    """Schema for webhook response with secret (only shown once)."""

    secret: str = Field(..., description="HMAC secret for signature verification")


# === Generic Response Schemas ===


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Generic error response."""

    success: bool = False
    error: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    items: list
    total: int
    page: int
    page_size: int
    pages: int
