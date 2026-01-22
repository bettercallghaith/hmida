"""MCP Server - WhatsApp tools for AI agents."""

import asyncio
import logging
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic_settings import BaseSettings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """MCP Server settings."""

    api_gateway_url: str = "http://localhost:8000"
    mcp_api_key: str = "internal_service_key_change_me"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Create MCP server
server = Server("whatsapp-mcp")

# HTTP client for API gateway
http_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    """Get or create HTTP client."""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(
            base_url=settings.api_gateway_url,
            headers={"X-API-Key": settings.mcp_api_key},
            timeout=60.0,
        )
    return http_client


async def call_api(method: str, path: str, json: dict | None = None) -> dict[str, Any]:
    """Call the API gateway."""
    client = await get_client()
    try:
        response = await client.request(method, path, json=json)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        error_body = e.response.json() if e.response.content else {}
        return {"success": False, "error": error_body.get("detail", str(e))}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Define tools
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available WhatsApp tools."""
    return [
        Tool(
            name="add_whatsapp_device",
            description="Add a new WhatsApp device and get QR code for pairing",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the device (e.g., 'Main Phone', 'Business Line')",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="remove_whatsapp_device",
            description="Remove a WhatsApp device and disconnect its session",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "UUID of the device to remove",
                    },
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="list_devices",
            description="List all WhatsApp devices with their connection status",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="send_whatsapp_text",
            description="Send a text message via WhatsApp",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "UUID of the device to send from",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Recipient phone number with country code (e.g., '1234567890')",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text message content",
                    },
                },
                "required": ["device_id", "recipient", "content"],
            },
        ),
        Tool(
            name="send_whatsapp_image",
            description="Send an image via WhatsApp with optional caption",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "UUID of the device to send from",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Recipient phone number with country code",
                    },
                    "media_url": {
                        "type": "string",
                        "description": "URL of the image to send",
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption for the image",
                    },
                },
                "required": ["device_id", "recipient", "media_url"],
            },
        ),
        Tool(
            name="send_whatsapp_video",
            description="Send a video via WhatsApp with optional caption",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "UUID of the device to send from",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Recipient phone number with country code",
                    },
                    "media_url": {
                        "type": "string",
                        "description": "URL of the video to send",
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption for the video",
                    },
                },
                "required": ["device_id", "recipient", "media_url"],
            },
        ),
        Tool(
            name="send_whatsapp_audio",
            description="Send an audio message (voice note) via WhatsApp",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "UUID of the device to send from",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Recipient phone number with country code",
                    },
                    "media_url": {
                        "type": "string",
                        "description": "URL of the audio file to send",
                    },
                },
                "required": ["device_id", "recipient", "media_url"],
            },
        ),
        Tool(
            name="send_whatsapp_document",
            description="Send a document via WhatsApp",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "UUID of the device to send from",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Recipient phone number with country code",
                    },
                    "media_url": {
                        "type": "string",
                        "description": "URL of the document to send",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Filename for the document (e.g., 'report.pdf')",
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption for the document",
                    },
                },
                "required": ["device_id", "recipient", "media_url", "filename"],
            },
        ),
        Tool(
            name="send_whatsapp_location",
            description="Send a location pin via WhatsApp",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "UUID of the device to send from",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Recipient phone number with country code",
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Latitude coordinate",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude coordinate",
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the location",
                    },
                    "address": {
                        "type": "string",
                        "description": "Address of the location",
                    },
                },
                "required": ["device_id", "recipient", "latitude", "longitude"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a WhatsApp tool."""
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "add_whatsapp_device":
            result = await call_api("POST", "/devices/add", {"name": arguments["name"]})

        elif name == "remove_whatsapp_device":
            result = await call_api("DELETE", f"/devices/{arguments['device_id']}")

        elif name == "list_devices":
            result = await call_api("GET", "/devices")

        elif name == "send_whatsapp_text":
            result = await call_api(
                "POST",
                "/send/text",
                {
                    "device_id": arguments["device_id"],
                    "recipient": arguments["recipient"],
                    "content": arguments["content"],
                },
            )

        elif name == "send_whatsapp_image":
            result = await call_api(
                "POST",
                "/send/image",
                {
                    "device_id": arguments["device_id"],
                    "recipient": arguments["recipient"],
                    "media_url": arguments["media_url"],
                    "caption": arguments.get("caption"),
                },
            )

        elif name == "send_whatsapp_video":
            result = await call_api(
                "POST",
                "/send/video",
                {
                    "device_id": arguments["device_id"],
                    "recipient": arguments["recipient"],
                    "media_url": arguments["media_url"],
                    "caption": arguments.get("caption"),
                },
            )

        elif name == "send_whatsapp_audio":
            result = await call_api(
                "POST",
                "/send/audio",
                {
                    "device_id": arguments["device_id"],
                    "recipient": arguments["recipient"],
                    "media_url": arguments["media_url"],
                },
            )

        elif name == "send_whatsapp_document":
            result = await call_api(
                "POST",
                "/send/document",
                {
                    "device_id": arguments["device_id"],
                    "recipient": arguments["recipient"],
                    "media_url": arguments["media_url"],
                    "filename": arguments["filename"],
                    "caption": arguments.get("caption"),
                },
            )

        elif name == "send_whatsapp_location":
            result = await call_api(
                "POST",
                "/send/location",
                {
                    "device_id": arguments["device_id"],
                    "recipient": arguments["recipient"],
                    "latitude": arguments["latitude"],
                    "longitude": arguments["longitude"],
                    "name": arguments.get("name"),
                    "address": arguments.get("address"),
                },
            )

        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}

        # Format response
        import json

        response_text = json.dumps(result, indent=2, default=str)
        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        import json

        return [TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}))]


async def main():
    """Run the MCP server."""
    logger.info("Starting WhatsApp MCP Server...")
    logger.info(f"API Gateway URL: {settings.api_gateway_url}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
