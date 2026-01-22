// WhatsApp Engine - Main Entry Point

import express, { Request, Response, NextFunction } from 'express';
import { Pool } from 'pg';
import Redis from 'ioredis';
import pino from 'pino';
import { SessionManager } from './session-manager.js';
import { MessageHandler } from './message-handler.js';
import { WebhookEmitter } from './webhook-emitter.js';
import { MessagePayload } from './types.js';

const logger = pino({
    level: process.env.LOG_LEVEL || 'info',
});

// Database connection
const db = new Pool({
    host: process.env.POSTGRES_HOST || 'localhost',
    port: parseInt(process.env.POSTGRES_PORT || '5432'),
    database: process.env.POSTGRES_DB || 'whatsapp_mcp',
    user: process.env.POSTGRES_USER || 'whatsapp',
    password: process.env.POSTGRES_PASSWORD || 'change_me_in_production',
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
});

// Redis connection
const redis = new Redis({
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD || undefined,
    maxRetriesPerRequest: 3,
});

// Initialize managers
const sessionManager = new SessionManager(db, redis, './sessions');
const messageHandler = new MessageHandler(sessionManager, db, './media');
const webhookEmitter = new WebhookEmitter(db, redis);

// Express app
const app = express();
app.use(express.json({ limit: '100mb' }));

// Request logging middleware
app.use((req: Request, res: Response, next: NextFunction) => {
    const start = Date.now();
    res.on('finish', () => {
        const duration = Date.now() - start;
        logger.info({
            method: req.method,
            path: req.path,
            status: res.statusCode,
            duration: `${duration}ms`,
        });
    });
    next();
});

// Health check
app.get('/health', (req: Request, res: Response) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Add device and get QR code
app.post('/devices/add', async (req: Request, res: Response) => {
    try {
        const { apiKeyId, name } = req.body;

        if (!apiKeyId || !name) {
            res.status(400).json({
                success: false,
                error: 'apiKeyId and name are required'
            });
            return;
        }

        const result = await sessionManager.addDevice(apiKeyId, name);
        res.json({ success: true, data: result });
    } catch (error) {
        logger.error({ err: error }, 'Failed to add device');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Remove device
app.delete('/devices/:id', async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const result = await sessionManager.removeDevice(id);
        res.json({ success: result });
    } catch (error) {
        logger.error({ err: error }, 'Failed to remove device');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// List devices
app.get('/devices', async (req: Request, res: Response) => {
    try {
        const apiKeyId = req.query.apiKeyId as string | undefined;
        const devices = await sessionManager.listDevices(apiKeyId);
        res.json({ success: true, data: devices });
    } catch (error) {
        logger.error({ err: error }, 'Failed to list devices');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Get device status
app.get('/devices/:id/status', async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const status = await sessionManager.getDeviceStatus(id);

        if (!status) {
            res.status(404).json({ success: false, error: 'Device not found' });
            return;
        }

        res.json({ success: true, data: status });
    } catch (error) {
        logger.error({ err: error }, 'Failed to get device status');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Reconnect device
app.post('/devices/:id/reconnect', async (req: Request, res: Response) => {
    try {
        const { id } = req.params;
        const status = await sessionManager.getDeviceStatus(id);

        if (!status) {
            res.status(404).json({ success: false, error: 'Device not found' });
            return;
        }

        // Get device config from database
        const result = await db.query(
            `SELECT id, api_key_id, name, phone_number FROM devices WHERE id = $1`,
            [id]
        );

        if (result.rows.length === 0) {
            res.status(404).json({ success: false, error: 'Device not found' });
            return;
        }

        const device = result.rows[0];
        await sessionManager.connectDevice({
            id: device.id,
            apiKeyId: device.api_key_id,
            name: device.name,
            phoneNumber: device.phone_number,
        });

        res.json({ success: true, message: 'Reconnection initiated' });
    } catch (error) {
        logger.error({ err: error }, 'Failed to reconnect device');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Send text message
app.post('/send/text', async (req: Request, res: Response) => {
    try {
        const payload: MessagePayload = {
            deviceId: req.body.deviceId,
            recipient: req.body.recipient,
            type: 'text',
            content: req.body.content,
        };

        const result = await messageHandler.sendMessage(payload);

        if (result.success) {
            res.json({ success: true, data: result });
        } else {
            res.status(400).json({ success: false, error: result.error });
        }
    } catch (error) {
        logger.error({ err: error }, 'Failed to send text');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Send image
app.post('/send/image', async (req: Request, res: Response) => {
    try {
        const payload: MessagePayload = {
            deviceId: req.body.deviceId,
            recipient: req.body.recipient,
            type: 'image',
            mediaUrl: req.body.mediaUrl,
            mediaBase64: req.body.mediaBase64,
            caption: req.body.caption,
        };

        const result = await messageHandler.sendMessage(payload);

        if (result.success) {
            res.json({ success: true, data: result });
        } else {
            res.status(400).json({ success: false, error: result.error });
        }
    } catch (error) {
        logger.error({ err: error }, 'Failed to send image');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Send video
app.post('/send/video', async (req: Request, res: Response) => {
    try {
        const payload: MessagePayload = {
            deviceId: req.body.deviceId,
            recipient: req.body.recipient,
            type: 'video',
            mediaUrl: req.body.mediaUrl,
            mediaBase64: req.body.mediaBase64,
            caption: req.body.caption,
            mimeType: req.body.mimeType,
        };

        const result = await messageHandler.sendMessage(payload);

        if (result.success) {
            res.json({ success: true, data: result });
        } else {
            res.status(400).json({ success: false, error: result.error });
        }
    } catch (error) {
        logger.error({ err: error }, 'Failed to send video');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Send audio
app.post('/send/audio', async (req: Request, res: Response) => {
    try {
        const payload: MessagePayload = {
            deviceId: req.body.deviceId,
            recipient: req.body.recipient,
            type: 'audio',
            mediaUrl: req.body.mediaUrl,
            mediaBase64: req.body.mediaBase64,
            mimeType: req.body.mimeType,
        };

        const result = await messageHandler.sendMessage(payload);

        if (result.success) {
            res.json({ success: true, data: result });
        } else {
            res.status(400).json({ success: false, error: result.error });
        }
    } catch (error) {
        logger.error({ err: error }, 'Failed to send audio');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Send document
app.post('/send/document', async (req: Request, res: Response) => {
    try {
        const payload: MessagePayload = {
            deviceId: req.body.deviceId,
            recipient: req.body.recipient,
            type: 'document',
            mediaUrl: req.body.mediaUrl,
            mediaBase64: req.body.mediaBase64,
            filename: req.body.filename,
            mimeType: req.body.mimeType,
            caption: req.body.caption,
        };

        const result = await messageHandler.sendMessage(payload);

        if (result.success) {
            res.json({ success: true, data: result });
        } else {
            res.status(400).json({ success: false, error: result.error });
        }
    } catch (error) {
        logger.error({ err: error }, 'Failed to send document');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Send location
app.post('/send/location', async (req: Request, res: Response) => {
    try {
        const payload: MessagePayload = {
            deviceId: req.body.deviceId,
            recipient: req.body.recipient,
            type: 'location',
            latitude: req.body.latitude,
            longitude: req.body.longitude,
            locationName: req.body.name,
            locationAddress: req.body.address,
        };

        const result = await messageHandler.sendMessage(payload);

        if (result.success) {
            res.json({ success: true, data: result });
        } else {
            res.status(400).json({ success: false, error: result.error });
        }
    } catch (error) {
        logger.error({ err: error }, 'Failed to send location');
        res.status(500).json({
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
        });
    }
});

// Wire up session events to webhooks
sessionManager.on('device.connected', async (data) => {
    await webhookEmitter.emit(data.deviceId, 'device.connected', data);
});

sessionManager.on('device.disconnected', async (data) => {
    await webhookEmitter.emit(data.deviceId, 'device.disconnected', data);
});

sessionManager.on('message.received', async (data) => {
    await webhookEmitter.emit(data.deviceId, 'message.received', data);
});

sessionManager.on('message.status', async (data) => {
    const eventType = data.status === 'delivered' ? 'message.delivered' : 'message.sent';
    await webhookEmitter.emit(data.deviceId, eventType, data);
});

// Start server
const PORT = parseInt(process.env.PORT || '3001');

async function start(): Promise<void> {
    try {
        // Test database connection
        await db.query('SELECT 1');
        logger.info('Database connected');

        // Test Redis connection
        await redis.ping();
        logger.info('Redis connected');

        // Initialize handlers
        await messageHandler.initialize();
        await sessionManager.initialize();
        await webhookEmitter.start();

        // Start HTTP server
        app.listen(PORT, '0.0.0.0', () => {
            logger.info(`WhatsApp Engine running on port ${PORT}`);
        });
    } catch (error) {
        logger.error({ err: error }, 'Failed to start server');
        process.exit(1);
    }
}

// Graceful shutdown
async function shutdown(): Promise<void> {
    logger.info('Shutting down...');

    await webhookEmitter.shutdown();
    await sessionManager.shutdown();
    await db.end();
    redis.disconnect();

    process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

start();
