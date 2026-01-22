# API Documentation

## Authentication

All API endpoints require authentication via API key.

### Header

```
X-API-Key: wamcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Scopes

- `read` - View devices, webhooks, messages
- `write` - Create/modify devices, send messages
- `admin` - Manage API keys

---

## Endpoints

### Health Check

```http
GET /health
```

No authentication required.

**Response:**
```json
{
  "status": "ok",
  "service": "api-gateway"
}
```

---

### Devices

#### List Devices

```http
GET /devices
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Main Phone",
    "phone_number": "1234567890",
    "status": "connected",
    "created_at": "2026-01-22T10:00:00Z",
    "connected_at": "2026-01-22T10:05:00Z"
  }
]
```

#### Add Device

```http
POST /devices/add
Content-Type: application/json

{
  "name": "Business Line"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Business Line",
  "status": "qr",
  "qr_code": "data:image/png;base64,...",
  "expires_in": 60
}
```

#### Remove Device

```http
DELETE /devices/{device_id}
```

#### Reconnect Device

```http
POST /devices/{device_id}/reconnect
```

---

### Messages

#### Send Text

```http
POST /send/text
Content-Type: application/json

{
  "device_id": "uuid",
  "recipient": "1234567890",
  "content": "Hello from WhatsApp MCP!"
}
```

**Response:**
```json
{
  "success": true,
  "message_id": "ABCD1234",
  "timestamp": "2026-01-22T10:00:00Z"
}
```

#### Send Image

```http
POST /send/image
Content-Type: application/json

{
  "device_id": "uuid",
  "recipient": "1234567890",
  "media_url": "https://example.com/image.jpg",
  "caption": "Check this out!"
}
```

#### Send Video

```http
POST /send/video
Content-Type: application/json

{
  "device_id": "uuid",
  "recipient": "1234567890",
  "media_url": "https://example.com/video.mp4",
  "caption": "Watch this!"
}
```

#### Send Audio

```http
POST /send/audio
Content-Type: application/json

{
  "device_id": "uuid",
  "recipient": "1234567890",
  "media_url": "https://example.com/audio.mp3"
}
```

#### Send Document

```http
POST /send/document
Content-Type: application/json

{
  "device_id": "uuid",
  "recipient": "1234567890",
  "media_url": "https://example.com/report.pdf",
  "filename": "report.pdf",
  "caption": "Here's the report"
}
```

#### Send Location

```http
POST /send/location
Content-Type: application/json

{
  "device_id": "uuid",
  "recipient": "1234567890",
  "latitude": 25.2760,
  "longitude": 51.5200,
  "name": "Doha, Qatar",
  "address": "West Bay, Doha"
}
```

---

### Webhooks

#### List Webhooks

```http
GET /webhooks
```

#### Create Webhook

```http
POST /webhooks
Content-Type: application/json

{
  "url": "https://your-server.com/webhook",
  "events": ["message.received", "device.connected"]
}
```

**Response includes secret (only shown once):**
```json
{
  "id": "uuid",
  "url": "https://your-server.com/webhook",
  "events": ["message.received", "device.connected"],
  "secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "is_active": true
}
```

#### Delete Webhook

```http
DELETE /webhooks/{webhook_id}
```

#### Toggle Webhook

```http
POST /webhooks/{webhook_id}/toggle
```

---

### Webhook Events

Webhooks receive POST requests with JSON payloads:

```json
{
  "event": "message.received",
  "timestamp": "2026-01-22T10:00:00Z",
  "deviceId": "uuid",
  "data": {
    "messageId": "ABCD1234",
    "sender": "1234567890",
    "senderName": "John Doe",
    "type": "text",
    "content": "Hello!"
  }
}
```

**Signature Verification:**

The `X-Webhook-Signature` header contains: `t=timestamp,v1=signature`

Verify with:
```python
import hmac
import hashlib

def verify_signature(payload, signature_header, secret):
    parts = dict(p.split("=") for p in signature_header.split(","))
    timestamp = parts["t"]
    signature = parts["v1"]
    
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.{payload}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)
```

---

## Rate Limiting

- Default: 100 requests per minute per API key
- Returns `429 Too Many Requests` when exceeded
- `Retry-After` header indicates wait time

---

## Error Responses

```json
{
  "success": false,
  "error": "Error message",
  "detail": "Additional details"
}
```

| Status | Description |
|--------|-------------|
| 400 | Bad request |
| 401 | Invalid API key |
| 403 | Forbidden (scope/expired) |
| 404 | Resource not found |
| 429 | Rate limited |
| 500 | Internal error |
| 503 | WhatsApp engine unavailable |
