"""WhatsApp Engine client service."""

from typing import Any, Optional
from uuid import UUID

import httpx

from app.config import get_settings

settings = get_settings()


class WhatsAppEngineError(Exception):
    """Exception raised when WhatsApp engine request fails."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class WhatsAppClient:
    """Client for communicating with WhatsApp Engine."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.whatsapp_engine_url
        self.timeout = 60.0

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make a request to the WhatsApp engine."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    json=json,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_body = e.response.json() if e.response.content else {}
                raise WhatsAppEngineError(
                    message=error_body.get("error", str(e)),
                    status_code=e.response.status_code,
                )
            except httpx.RequestError as e:
                raise WhatsAppEngineError(
                    message=f"Connection error: {e}",
                    status_code=503,
                )

    async def add_device(self, api_key_id: UUID, name: str) -> dict[str, Any]:
        """Add a new device and get QR code."""
        return await self._request(
            "POST",
            "/devices/add",
            json={"apiKeyId": str(api_key_id), "name": name},
        )

    async def remove_device(self, device_id: UUID) -> dict[str, Any]:
        """Remove a device."""
        return await self._request("DELETE", f"/devices/{device_id}")

    async def list_devices(self, api_key_id: Optional[UUID] = None) -> dict[str, Any]:
        """List all devices."""
        params = {}
        if api_key_id:
            params["apiKeyId"] = str(api_key_id)
        return await self._request("GET", "/devices", params=params)

    async def get_device_status(self, device_id: UUID) -> dict[str, Any]:
        """Get device status."""
        return await self._request("GET", f"/devices/{device_id}/status")

    async def reconnect_device(self, device_id: UUID) -> dict[str, Any]:
        """Reconnect a device."""
        return await self._request("POST", f"/devices/{device_id}/reconnect")

    async def send_text(
        self,
        device_id: UUID,
        recipient: str,
        content: str,
    ) -> dict[str, Any]:
        """Send a text message."""
        return await self._request(
            "POST",
            "/send/text",
            json={
                "deviceId": str(device_id),
                "recipient": recipient,
                "content": content,
            },
        )

    async def send_image(
        self,
        device_id: UUID,
        recipient: str,
        media_url: Optional[str] = None,
        media_base64: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send an image message."""
        payload = {
            "deviceId": str(device_id),
            "recipient": recipient,
        }
        if media_url:
            payload["mediaUrl"] = media_url
        if media_base64:
            payload["mediaBase64"] = media_base64
        if caption:
            payload["caption"] = caption

        return await self._request("POST", "/send/image", json=payload)

    async def send_video(
        self,
        device_id: UUID,
        recipient: str,
        media_url: Optional[str] = None,
        media_base64: Optional[str] = None,
        caption: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send a video message."""
        payload = {
            "deviceId": str(device_id),
            "recipient": recipient,
        }
        if media_url:
            payload["mediaUrl"] = media_url
        if media_base64:
            payload["mediaBase64"] = media_base64
        if caption:
            payload["caption"] = caption
        if mime_type:
            payload["mimeType"] = mime_type

        return await self._request("POST", "/send/video", json=payload)

    async def send_audio(
        self,
        device_id: UUID,
        recipient: str,
        media_url: Optional[str] = None,
        media_base64: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send an audio message."""
        payload = {
            "deviceId": str(device_id),
            "recipient": recipient,
        }
        if media_url:
            payload["mediaUrl"] = media_url
        if media_base64:
            payload["mediaBase64"] = media_base64
        if mime_type:
            payload["mimeType"] = mime_type

        return await self._request("POST", "/send/audio", json=payload)

    async def send_document(
        self,
        device_id: UUID,
        recipient: str,
        media_url: Optional[str] = None,
        media_base64: Optional[str] = None,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send a document message."""
        payload = {
            "deviceId": str(device_id),
            "recipient": recipient,
        }
        if media_url:
            payload["mediaUrl"] = media_url
        if media_base64:
            payload["mediaBase64"] = media_base64
        if filename:
            payload["filename"] = filename
        if mime_type:
            payload["mimeType"] = mime_type
        if caption:
            payload["caption"] = caption

        return await self._request("POST", "/send/document", json=payload)

    async def send_location(
        self,
        device_id: UUID,
        recipient: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send a location message."""
        payload = {
            "deviceId": str(device_id),
            "recipient": recipient,
            "latitude": latitude,
            "longitude": longitude,
        }
        if name:
            payload["name"] = name
        if address:
            payload["address"] = address

        return await self._request("POST", "/send/location", json=payload)


# Singleton client instance
whatsapp_client = WhatsAppClient()
