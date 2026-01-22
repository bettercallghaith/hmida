# MCP Tools Documentation

## Overview

The WhatsApp MCP Server exposes 9 tools for AI agents to interact with WhatsApp.

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "docker",
      "args": ["exec", "-i", "whatsapp-mcp-server", "python", "-m", "src.server"],
      "env": {
        "API_GATEWAY_URL": "http://api-gateway:8000",
        "MCP_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Standalone

```bash
cd mcp-server
pip install -r requirements.txt
MCP_API_KEY=your-key python -m src.server
```

---

## Available Tools

### 1. `add_whatsapp_device`

Add a new WhatsApp device and get QR code for pairing.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| name | string | Yes | Name for the device |

**Example:**
```
Add a WhatsApp device named "Business Line"
```

**Returns:** Device ID and base64 QR code image

---

### 2. `remove_whatsapp_device`

Remove a WhatsApp device and disconnect its session.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| device_id | string (UUID) | Yes | Device ID to remove |

---

### 3. `list_devices`

List all WhatsApp devices with their connection status.

**Parameters:** None

**Returns:** Array of devices with status

---

### 4. `send_whatsapp_text`

Send a text message via WhatsApp.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| device_id | string (UUID) | Yes | Device to send from |
| recipient | string | Yes | Phone number with country code |
| content | string | Yes | Message text |

**Example:**
```
Send "Hello!" to +1234567890 using device abc-123
```

---

### 5. `send_whatsapp_image`

Send an image with optional caption.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| device_id | string (UUID) | Yes | Device to send from |
| recipient | string | Yes | Phone number |
| media_url | string (URL) | Yes | Image URL |
| caption | string | No | Image caption |

---

### 6. `send_whatsapp_video`

Send a video with optional caption.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| device_id | string (UUID) | Yes | Device to send from |
| recipient | string | Yes | Phone number |
| media_url | string (URL) | Yes | Video URL |
| caption | string | No | Video caption |

---

### 7. `send_whatsapp_audio`

Send an audio message (voice note).

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| device_id | string (UUID) | Yes | Device to send from |
| recipient | string | Yes | Phone number |
| media_url | string (URL) | Yes | Audio file URL |

---

### 8. `send_whatsapp_document`

Send a document file.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| device_id | string (UUID) | Yes | Device to send from |
| recipient | string | Yes | Phone number |
| media_url | string (URL) | Yes | Document URL |
| filename | string | Yes | Display filename |
| caption | string | No | Document caption |

---

### 9. `send_whatsapp_location`

Send a location pin.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| device_id | string (UUID) | Yes | Device to send from |
| recipient | string | Yes | Phone number |
| latitude | number | Yes | Latitude (-90 to 90) |
| longitude | number | Yes | Longitude (-180 to 180) |
| name | string | No | Location name |
| address | string | No | Location address |

---

## Example Conversation

**User:** Send a message to John at +1234567890 saying "Meeting at 3pm"

**AI uses:** `list_devices` → finds connected device → `send_whatsapp_text`

**Response:** Message sent successfully with ID ABC123

---

## Error Handling

All tools return JSON with:

```json
{
  "success": true|false,
  "data": {...},
  "error": "Error message if failed"
}
```

Common errors:
- Device not connected
- Invalid phone number format
- Media URL inaccessible
- Rate limit exceeded
