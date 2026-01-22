# WhatsApp MCP Infrastructure Platform

A production-grade, self-hosted WhatsApp multi-device gateway with MCP server, REST API, and webhook support.

## Features

- 🔌 **Multi-Device WhatsApp** - Unlimited parallel WhatsApp sessions via Baileys
- 🤖 **MCP Server** - AI-callable tools for Claude and other AI agents
- 🔑 **API Key Auth** - Per-client authentication with rate limiting
- 📡 **Webhooks** - HMAC-signed event delivery with retry queue
- 📱 **Full Media Support** - Text, image, video, audio, document, location
- 🐳 **Docker First** - One-command deployment

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  AI Agents  │────▶│  MCP Server │────▶│                 │
└─────────────┘     └─────────────┘     │   API Gateway   │
                                        │    (FastAPI)    │
┌─────────────┐     ┌─────────────┐     │                 │
│  Webhooks   │◀────│   Events    │◀────│                 │
└─────────────┘     └─────────────┘     └────────┬────────┘
                                                 │
                                        ┌────────▼────────┐
                                        │ WhatsApp Engine │
                                        │    (Baileys)    │
                                        └────────┬────────┘
                                                 │
                                        ┌────────▼────────┐
                                        │  WhatsApp Web   │
                                        └─────────────────┘
```


Once running, access OpenAPI docs at: http://localhost:8000/docs

## MCP Tools

| Tool | Description |
|------|-------------|
| `add_whatsapp_device` | Add device, returns QR code |
| `remove_whatsapp_device` | Remove device by ID |
| `list_devices` | List all connected devices |
| `send_whatsapp_text` | Send text message |
| `send_whatsapp_image` | Send image with caption |
| `send_whatsapp_video` | Send video file |
| `send_whatsapp_audio` | Send audio file |
| `send_whatsapp_document` | Send document file |
| `send_whatsapp_location` | Send location pin |
