// Session Manager - Multi-device WhatsApp session management using Baileys

import makeWASocket, {
    DisconnectReason,
    useMultiFileAuthState,
    WASocket,
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore,
    proto,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import path from 'path';
import fs from 'fs/promises';
import { EventEmitter } from 'events';
import { Pool } from 'pg';
import Redis from 'ioredis';
import QRCode from 'qrcode';
import { v4 as uuidv4 } from 'uuid';
import { DeviceConfig, SessionState, QRResponse } from './types.js';

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

interface ActiveSession {
    socket: WASocket;
    state: SessionState;
    retryCount: number;
    reconnectTimeout?: NodeJS.Timeout;
}

export class SessionManager extends EventEmitter {
    private sessions: Map<string, ActiveSession> = new Map();
    private sessionsDir: string;
    private db: Pool;
    private redis: Redis;
    private maxRetries = 5;
    private baseRetryDelay = 1000;

    constructor(db: Pool, redis: Redis, sessionsDir: string = './sessions') {
        super();
        this.db = db;
        this.redis = redis;
        this.sessionsDir = sessionsDir;
    }

    async initialize(): Promise<void> {
        // Ensure sessions directory exists
        await fs.mkdir(this.sessionsDir, { recursive: true });

        // Load existing sessions from database
        const result = await this.db.query(
            `SELECT id, api_key_id, name, phone_number, session_path 
       FROM devices 
       WHERE status != 'removed'`
        );

        for (const row of result.rows) {
            const sessionPath = path.join(this.sessionsDir, row.id);
            try {
                await fs.access(sessionPath);
                // Session files exist, attempt to reconnect
                await this.connectDevice({
                    id: row.id,
                    apiKeyId: row.api_key_id,
                    name: row.name,
                    phoneNumber: row.phone_number,
                });
            } catch {
                logger.info(`Session files not found for device ${row.id}, skipping auto-connect`);
            }
        }
    }

    async addDevice(apiKeyId: string, name: string): Promise<QRResponse> {
        const deviceId = uuidv4();
        const sessionPath = path.join(this.sessionsDir, deviceId);

        // Create device record in database
        await this.db.query(
            `INSERT INTO devices (id, api_key_id, name, status, session_path)
       VALUES ($1, $2, $3, 'pending', $4)`,
            [deviceId, apiKeyId, name, sessionPath]
        );

        // Initialize session and get QR code
        const qrCode = await this.initializeSession({
            id: deviceId,
            apiKeyId,
            name,
        });

        return {
            deviceId,
            qrCode,
            expiresIn: 60,
        };
    }

    private async initializeSession(config: DeviceConfig): Promise<string> {
        return new Promise(async (resolve, reject) => {
            const sessionPath = path.join(this.sessionsDir, config.id);
            await fs.mkdir(sessionPath, { recursive: true });

            const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
            const { version } = await fetchLatestBaileysVersion();

            const socket = makeWASocket({
                version,
                auth: {
                    creds: state.creds,
                    keys: makeCacheableSignalKeyStore(state.keys, logger),
                },
                printQRInTerminal: false,
                logger: logger.child({ device: config.id }),
                browser: ['WhatsApp MCP', 'Chrome', '120.0.0'],
                connectTimeoutMs: 60000,
                qrTimeout: 60000,
                defaultQueryTimeoutMs: 60000,
            });

            const sessionState: SessionState = {
                deviceId: config.id,
                status: 'pending',
            };

            const activeSession: ActiveSession = {
                socket,
                state: sessionState,
                retryCount: 0,
            };

            this.sessions.set(config.id, activeSession);

            // Handle credentials update
            socket.ev.on('creds.update', saveCreds);

            // Handle QR code
            socket.ev.on('connection.update', async (update) => {
                const { connection, lastDisconnect, qr } = update;

                if (qr) {
                    // Generate QR code as base64
                    const qrBase64 = await QRCode.toDataURL(qr);
                    sessionState.qrCode = qrBase64;
                    sessionState.status = 'qr';

                    await this.db.query(
                        `UPDATE devices SET qr_code = $1, status = 'qr' WHERE id = $2`,
                        [qrBase64, config.id]
                    );

                    this.emit('qr', { deviceId: config.id, qrCode: qrBase64 });
                    resolve(qrBase64);
                }

                if (connection === 'close') {
                    const statusCode = (lastDisconnect?.error as Boom)?.output?.statusCode;
                    const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

                    sessionState.status = 'disconnected';
                    sessionState.disconnectedAt = new Date();

                    await this.db.query(
                        `UPDATE devices SET status = 'disconnected', disconnected_at = NOW() WHERE id = $1`,
                        [config.id]
                    );

                    this.emit('device.disconnected', {
                        deviceId: config.id,
                        reason: DisconnectReason[statusCode] || 'unknown',
                    });

                    if (shouldReconnect && activeSession.retryCount < this.maxRetries) {
                        activeSession.retryCount++;
                        const delay = this.baseRetryDelay * Math.pow(2, activeSession.retryCount - 1);

                        logger.info(`Reconnecting device ${config.id} in ${delay}ms (attempt ${activeSession.retryCount})`);

                        activeSession.reconnectTimeout = setTimeout(async () => {
                            await this.connectDevice(config);
                        }, delay);
                    } else if (statusCode === DisconnectReason.loggedOut) {
                        // Clean up session on logout
                        await this.removeSession(config.id);
                    }
                } else if (connection === 'open') {
                    const phoneNumber = socket.user?.id?.split(':')[0] || socket.user?.id;

                    sessionState.status = 'connected';
                    sessionState.phoneNumber = phoneNumber;
                    sessionState.connectedAt = new Date();
                    activeSession.retryCount = 0;

                    await this.db.query(
                        `UPDATE devices 
             SET status = 'connected', 
                 phone_number = $1, 
                 connected_at = NOW(),
                 last_seen_at = NOW(),
                 qr_code = NULL
             WHERE id = $2`,
                        [phoneNumber, config.id]
                    );

                    this.emit('device.connected', {
                        deviceId: config.id,
                        phoneNumber,
                    });

                    logger.info(`Device ${config.id} connected: ${phoneNumber}`);
                }
            });

            // Handle incoming messages
            socket.ev.on('messages.upsert', async ({ messages, type }) => {
                if (type !== 'notify') return;

                for (const msg of messages) {
                    if (msg.key.fromMe) continue; // Skip our own messages

                    const sender = msg.key.remoteJid;
                    const messageType = this.getMessageType(msg.message);
                    const content = this.extractMessageContent(msg.message);

                    this.emit('message.received', {
                        deviceId: config.id,
                        messageId: msg.key.id,
                        sender,
                        senderName: msg.pushName,
                        type: messageType,
                        content: content.text,
                        caption: content.caption,
                        mediaUrl: content.mediaUrl,
                        timestamp: new Date((msg.messageTimestamp as number) * 1000),
                        isGroup: sender?.endsWith('@g.us') || false,
                    });
                }
            });

            // Handle message status updates
            socket.ev.on('messages.update', async (updates) => {
                for (const update of updates) {
                    if (update.update.status) {
                        const status = update.update.status;
                        let statusName = 'unknown';

                        if (status === 2) statusName = 'sent';
                        else if (status === 3) statusName = 'delivered';
                        else if (status === 4) statusName = 'read';

                        this.emit('message.status', {
                            deviceId: config.id,
                            messageId: update.key.id,
                            recipient: update.key.remoteJid,
                            status: statusName,
                        });
                    }
                }
            });
        });
    }

    async connectDevice(config: DeviceConfig): Promise<void> {
        const existing = this.sessions.get(config.id);
        if (existing?.reconnectTimeout) {
            clearTimeout(existing.reconnectTimeout);
        }

        await this.initializeSession(config);
    }

    async removeDevice(deviceId: string): Promise<boolean> {
        const session = this.sessions.get(deviceId);

        if (session) {
            if (session.reconnectTimeout) {
                clearTimeout(session.reconnectTimeout);
            }

            try {
                await session.socket.logout();
            } catch (error) {
                logger.error({ err: error }, `Error logging out device ${deviceId}`);
            }

            session.socket.end(undefined);
        }

        await this.removeSession(deviceId);
        return true;
    }

    private async removeSession(deviceId: string): Promise<void> {
        this.sessions.delete(deviceId);

        // Remove session files
        const sessionPath = path.join(this.sessionsDir, deviceId);
        try {
            await fs.rm(sessionPath, { recursive: true, force: true });
        } catch (error) {
            logger.error({ err: error }, `Error removing session files for ${deviceId}`);
        }

        // Update database
        await this.db.query(
            `UPDATE devices SET status = 'removed' WHERE id = $1`,
            [deviceId]
        );
    }

    getSession(deviceId: string): ActiveSession | undefined {
        return this.sessions.get(deviceId);
    }

    getSocket(deviceId: string): WASocket | undefined {
        return this.sessions.get(deviceId)?.socket;
    }

    async getDeviceStatus(deviceId: string): Promise<SessionState | null> {
        const session = this.sessions.get(deviceId);
        if (session) {
            return session.state;
        }

        // Check database
        const result = await this.db.query(
            `SELECT id, status, phone_number, connected_at, disconnected_at
       FROM devices WHERE id = $1`,
            [deviceId]
        );

        if (result.rows.length === 0) return null;

        const row = result.rows[0];
        return {
            deviceId: row.id,
            status: row.status,
            phoneNumber: row.phone_number,
            connectedAt: row.connected_at,
            disconnectedAt: row.disconnected_at,
        };
    }

    async listDevices(apiKeyId?: string): Promise<SessionState[]> {
        let query = `SELECT id, status, phone_number, connected_at, disconnected_at, name
                 FROM devices WHERE status != 'removed'`;
        const params: string[] = [];

        if (apiKeyId) {
            query += ` AND api_key_id = $1`;
            params.push(apiKeyId);
        }

        const result = await this.db.query(query, params);

        return result.rows.map((row) => ({
            deviceId: row.id,
            status: row.status,
            phoneNumber: row.phone_number,
            connectedAt: row.connected_at,
            disconnectedAt: row.disconnected_at,
        }));
    }

    private getMessageType(message: proto.IMessage | null | undefined): string {
        if (!message) return 'unknown';

        if (message.conversation || message.extendedTextMessage) return 'text';
        if (message.imageMessage) return 'image';
        if (message.videoMessage) return 'video';
        if (message.audioMessage) return 'audio';
        if (message.documentMessage) return 'document';
        if (message.locationMessage) return 'location';
        if (message.contactMessage) return 'contact';
        if (message.stickerMessage) return 'sticker';

        return 'unknown';
    }

    private extractMessageContent(message: proto.IMessage | null | undefined): {
        text?: string;
        caption?: string;
        mediaUrl?: string;
    } {
        if (!message) return {};

        if (message.conversation) {
            return { text: message.conversation };
        }
        if (message.extendedTextMessage) {
            return { text: message.extendedTextMessage.text || undefined };
        }
        if (message.imageMessage) {
            return { caption: message.imageMessage.caption || undefined };
        }
        if (message.videoMessage) {
            return { caption: message.videoMessage.caption || undefined };
        }
        if (message.documentMessage) {
            return { caption: message.documentMessage.fileName || undefined };
        }

        return {};
    }

    async shutdown(): Promise<void> {
        logger.info('Shutting down session manager...');

        for (const [deviceId, session] of this.sessions) {
            if (session.reconnectTimeout) {
                clearTimeout(session.reconnectTimeout);
            }

            try {
                session.socket.end(undefined);
            } catch (error) {
                logger.error({ err: error }, `Error closing socket for ${deviceId}`);
            }
        }

        this.sessions.clear();
    }
}
