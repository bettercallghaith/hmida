// Message Handler - Send various message types via WhatsApp

import { WASocket, AnyMessageContent, downloadMediaMessage } from '@whiskeysockets/baileys';
import axios from 'axios';
import sharp from 'sharp';
import path from 'path';
import fs from 'fs/promises';
import { Pool } from 'pg';
import pino from 'pino';
import { v4 as uuidv4 } from 'uuid';
import { MessagePayload, MessageResult } from './types.js';
import { SessionManager } from './session-manager.js';

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

export class MessageHandler {
    private sessionManager: SessionManager;
    private db: Pool;
    private mediaDir: string;

    constructor(sessionManager: SessionManager, db: Pool, mediaDir: string = './media') {
        this.sessionManager = sessionManager;
        this.db = db;
        this.mediaDir = mediaDir;
    }

    async initialize(): Promise<void> {
        await fs.mkdir(this.mediaDir, { recursive: true });
    }

    async sendMessage(payload: MessagePayload): Promise<MessageResult> {
        const socket = this.sessionManager.getSocket(payload.deviceId);

        if (!socket) {
            return {
                success: false,
                error: 'Device not connected',
            };
        }

        const jid = this.formatJid(payload.recipient);

        try {
            let message: AnyMessageContent;
            let messageId: string | undefined;

            switch (payload.type) {
                case 'text':
                    message = { text: payload.content || '' };
                    break;

                case 'image':
                    message = await this.prepareImageMessage(payload);
                    break;

                case 'video':
                    message = await this.prepareVideoMessage(payload);
                    break;

                case 'audio':
                    message = await this.prepareAudioMessage(payload);
                    break;

                case 'document':
                    message = await this.prepareDocumentMessage(payload);
                    break;

                case 'location':
                    message = this.prepareLocationMessage(payload);
                    break;

                default:
                    return {
                        success: false,
                        error: `Unsupported message type: ${payload.type}`,
                    };
            }

            const result = await socket.sendMessage(jid, message);
            messageId = result?.key?.id;

            // Log message to database
            await this.logMessage(payload, messageId, 'sent');

            return {
                success: true,
                messageId,
                timestamp: new Date(),
            };
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            logger.error({ err: error }, 'Failed to send message');

            // Log failed message
            await this.logMessage(payload, undefined, 'failed', errorMessage);

            return {
                success: false,
                error: errorMessage,
            };
        }
    }

    private formatJid(recipient: string): string {
        // Remove any non-numeric characters except @
        let cleaned = recipient.replace(/[^\d@gs.u]/g, '');

        // If it's already a full JID, return as-is
        if (cleaned.includes('@')) {
            return cleaned;
        }

        // Add @s.whatsapp.net for individual chats
        return `${cleaned}@s.whatsapp.net`;
    }

    private async prepareImageMessage(payload: MessagePayload): Promise<AnyMessageContent> {
        const imageBuffer = await this.fetchMedia(payload);

        // Optimize image
        const optimized = await sharp(imageBuffer)
            .resize(1280, 1280, { fit: 'inside', withoutEnlargement: true })
            .jpeg({ quality: 80 })
            .toBuffer();

        return {
            image: optimized,
            caption: payload.caption,
            mimetype: 'image/jpeg',
        };
    }

    private async prepareVideoMessage(payload: MessagePayload): Promise<AnyMessageContent> {
        const videoBuffer = await this.fetchMedia(payload);

        return {
            video: videoBuffer,
            caption: payload.caption,
            mimetype: payload.mimeType || 'video/mp4',
        };
    }

    private async prepareAudioMessage(payload: MessagePayload): Promise<AnyMessageContent> {
        const audioBuffer = await this.fetchMedia(payload);

        return {
            audio: audioBuffer,
            mimetype: payload.mimeType || 'audio/mpeg',
            ptt: true, // Voice note
        };
    }

    private async prepareDocumentMessage(payload: MessagePayload): Promise<AnyMessageContent> {
        const documentBuffer = await this.fetchMedia(payload);

        return {
            document: documentBuffer,
            fileName: payload.filename || 'document',
            mimetype: payload.mimeType || 'application/octet-stream',
            caption: payload.caption,
        };
    }

    private prepareLocationMessage(payload: MessagePayload): AnyMessageContent {
        return {
            location: {
                degreesLatitude: payload.latitude || 0,
                degreesLongitude: payload.longitude || 0,
                name: payload.locationName,
                address: payload.locationAddress,
            },
        };
    }

    private async fetchMedia(payload: MessagePayload): Promise<Buffer> {
        if (payload.mediaBase64) {
            // Handle base64 encoded media
            const base64Data = payload.mediaBase64.replace(/^data:[^;]+;base64,/, '');
            return Buffer.from(base64Data, 'base64');
        }

        if (payload.mediaUrl) {
            // Fetch from URL
            const response = await axios.get(payload.mediaUrl, {
                responseType: 'arraybuffer',
                timeout: 30000,
                maxContentLength: 100 * 1024 * 1024, // 100MB max
            });
            return Buffer.from(response.data);
        }

        throw new Error('No media source provided');
    }

    private async logMessage(
        payload: MessagePayload,
        messageId: string | undefined,
        status: string,
        errorMessage?: string
    ): Promise<void> {
        try {
            await this.db.query(
                `INSERT INTO messages 
         (device_id, message_id, direction, type, recipient, content, status, error_message, sent_at)
         VALUES ($1, $2, 'outbound', $3, $4, $5, $6, $7, NOW())`,
                [
                    payload.deviceId,
                    messageId,
                    payload.type,
                    payload.recipient,
                    payload.content || payload.caption,
                    status,
                    errorMessage,
                ]
            );
        } catch (error) {
            logger.error({ err: error }, 'Failed to log message');
        }
    }

    async downloadMedia(
        deviceId: string,
        message: any,
        messageType: string
    ): Promise<{ buffer: Buffer; filename: string; mimetype: string } | null> {
        const socket = this.sessionManager.getSocket(deviceId);
        if (!socket) return null;

        try {
            const buffer = await downloadMediaMessage(
                message,
                'buffer',
                {},
                {
                    logger,
                    reuploadRequest: socket.updateMediaMessage,
                }
            );

            const mediaId = uuidv4();
            let extension = 'bin';
            let mimetype = 'application/octet-stream';

            switch (messageType) {
                case 'image':
                    extension = 'jpg';
                    mimetype = 'image/jpeg';
                    break;
                case 'video':
                    extension = 'mp4';
                    mimetype = 'video/mp4';
                    break;
                case 'audio':
                    extension = 'mp3';
                    mimetype = 'audio/mpeg';
                    break;
                case 'document':
                    extension = message.message?.documentMessage?.fileName?.split('.').pop() || 'pdf';
                    mimetype = message.message?.documentMessage?.mimetype || 'application/pdf';
                    break;
            }

            const filename = `${mediaId}.${extension}`;
            const filePath = path.join(this.mediaDir, filename);

            await fs.writeFile(filePath, buffer as Buffer);

            return {
                buffer: buffer as Buffer,
                filename,
                mimetype,
            };
        } catch (error) {
            logger.error({ err: error }, 'Failed to download media');
            return null;
        }
    }
}
