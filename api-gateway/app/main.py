"""FastAPI Gateway - Main Application Entry Point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.auth import set_redis_client
from app.config import get_settings
from app.routers import api_keys, devices, messages, webhooks

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting WhatsApp MCP API Gateway...")

    # Initialize Redis for rate limiting
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        set_redis_client(redis)
        logger.info("Redis connected for rate limiting")
    except Exception as e:
        logger.warning(f"Redis not available, rate limiting disabled: {e}")

    yield

    # Shutdown
    logger.info("Shutting down API Gateway...")
    await redis.close()


# Create FastAPI app
app = FastAPI(
    title="WhatsApp MCP API Gateway",
    description="""
## WhatsApp MCP Infrastructure Platform

A production-grade, self-hosted WhatsApp multi-device gateway with:

- **Multi-Device Support**: Unlimited parallel WhatsApp sessions
- **AI Integration**: MCP tools for Claude and AI agents  
- **Webhooks**: HMAC-signed event delivery
- **Full Media Support**: Text, image, video, audio, document, location

### Authentication

All endpoints require an API key passed in the `X-API-Key` header.

### Rate Limiting

Requests are rate-limited per API key (default: 100 req/min).
    """,
    version="1.0.0",
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if hasattr(settings, "cors_origins") else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )


# Health check
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "api-gateway"}


# Include routers
app.include_router(devices.router)
app.include_router(messages.router)
app.include_router(webhooks.router)
app.include_router(api_keys.router)
