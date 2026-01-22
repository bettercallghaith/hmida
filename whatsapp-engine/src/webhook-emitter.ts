// Webhook Emitter - Send events to configured webhook URLs

import axios, { AxiosError } from 'axios';
import crypto from 'crypto';
import { Pool } from 'pg';
import Redis from 'ioredis';
import pino from 'pino';
import { WebhookEvent } from './types.js';

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

interface WebhookConfig {
    id: string;
    apiKeyId: string;
    url: string;
    secret: string;
    events: string[];
    isActive: boolean;
}

interface DeliveryTask {
    webhookId: string;
    event: WebhookEvent;
    attempt: number;
    deliveryLogId: string;
}

export class WebhookEmitter {
    private db: Pool;
    private redis: Redis;
    private maxRetries: number;
    private baseDelay: number;
    private timeout: number;
    private webhookCache: Map<string, WebhookConfig[]> = new Map();
    private cacheTimeout = 60000; // 1 minute cache
    private shutdownRequested = false;

    constructor(
        db: Pool,
        redis: Redis,
        options?: {
            maxRetries?: number;
            baseDelay?: number;
            timeout?: number;
        }
    ) {
        this.db = db;
        this.redis = redis;
        this.maxRetries = options?.maxRetries || 5;
        this.baseDelay = options?.baseDelay || 1000;
        this.timeout = options?.timeout || 30000;
    }

    async start(): Promise<void> {
        // Start processing retry queue
        this.processRetryQueue();
    }

    async emit(deviceId: string, eventType: string, data: Record<string, unknown>): Promise<void> {
        // Get API key ID for this device
        const deviceResult = await this.db.query(
            `SELECT api_key_id FROM devices WHERE id = $1`,
            [deviceId]
        );

        if (deviceResult.rows.length === 0) {
            logger.warn(`Device ${deviceId} not found, cannot emit webhook`);
            return;
        }

        const apiKeyId = deviceResult.rows[0].api_key_id;
        const webhooks = await this.getWebhooksForApiKey(apiKeyId, eventType);

        const event: WebhookEvent = {
            event: eventType,
            timestamp: new Date().toISOString(),
            deviceId,
            data,
        };

        for (const webhook of webhooks) {
            await this.dispatchWebhook(webhook, event);
        }
    }

    private async getWebhooksForApiKey(apiKeyId: string, eventType: string): Promise<WebhookConfig[]> {
        // Check cache
        const cacheKey = `webhooks:${apiKeyId}`;
        const cached = this.webhookCache.get(cacheKey);

        if (cached) {
            return cached.filter((w) => w.events.includes(eventType) || w.events.includes('*'));
        }

        // Query database
        const result = await this.db.query(
            `SELECT id, api_key_id, url, secret, events, is_active
       FROM webhooks
       WHERE api_key_id = $1 AND is_active = true`,
            [apiKeyId]
        );

        const webhooks: WebhookConfig[] = result.rows.map((row) => ({
            id: row.id,
            apiKeyId: row.api_key_id,
            url: row.url,
            secret: row.secret,
            events: row.events,
            isActive: row.is_active,
        }));

        // Cache for 1 minute
        this.webhookCache.set(cacheKey, webhooks);
        setTimeout(() => this.webhookCache.delete(cacheKey), this.cacheTimeout);

        return webhooks.filter((w) => w.events.includes(eventType) || w.events.includes('*'));
    }

    private async dispatchWebhook(webhook: WebhookConfig, event: WebhookEvent): Promise<void> {
        const payload = JSON.stringify(event);
        const signature = this.generateSignature(payload, webhook.secret);

        // Create delivery log
        const logResult = await this.db.query(
            `INSERT INTO delivery_logs (webhook_id, event_type, payload, status)
       VALUES ($1, $2, $3, 'pending')
       RETURNING id`,
            [webhook.id, event.event, event]
        );
        const deliveryLogId = logResult.rows[0].id;

        const task: DeliveryTask = {
            webhookId: webhook.id,
            event,
            attempt: 1,
            deliveryLogId,
        };

        try {
            await this.deliverWebhook(webhook.url, payload, signature);

            // Update delivery log as success
            await this.db.query(
                `UPDATE delivery_logs 
         SET status = 'success', response_status = 200, completed_at = NOW()
         WHERE id = $1`,
                [deliveryLogId]
            );

            logger.info(`Webhook delivered successfully to ${webhook.url}`);
        } catch (error) {
            await this.handleDeliveryError(task, webhook, error);
        }
    }

    private async deliverWebhook(url: string, payload: string, signature: string): Promise<void> {
        await axios.post(url, payload, {
            headers: {
                'Content-Type': 'application/json',
                'X-Webhook-Signature': signature,
                'X-Webhook-Timestamp': new Date().toISOString(),
                'User-Agent': 'WhatsApp-MCP-Webhook/1.0',
            },
            timeout: this.timeout,
            validateStatus: (status) => status >= 200 && status < 300,
        });
    }

    private generateSignature(payload: string, secret: string): string {
        const timestamp = Math.floor(Date.now() / 1000);
        const signaturePayload = `${timestamp}.${payload}`;
        const signature = crypto
            .createHmac('sha256', secret)
            .update(signaturePayload)
            .digest('hex');
        return `t=${timestamp},v1=${signature}`;
    }

    private async handleDeliveryError(
        task: DeliveryTask,
        webhook: WebhookConfig,
        error: unknown
    ): Promise<void> {
        const axiosError = error as AxiosError;
        const responseStatus = axiosError.response?.status || 0;
        const responseBody = axiosError.response?.data
            ? JSON.stringify(axiosError.response.data).slice(0, 1000)
            : axiosError.message;

        if (task.attempt >= this.maxRetries) {
            // Mark as dead letter
            await this.db.query(
                `UPDATE delivery_logs 
         SET status = 'dead', 
             response_status = $1, 
             response_body = $2, 
             attempt_count = $3,
             completed_at = NOW()
         WHERE id = $4`,
                [responseStatus, responseBody, task.attempt, task.deliveryLogId]
            );

            logger.error(`Webhook delivery to ${webhook.url} failed after ${this.maxRetries} attempts`);
            return;
        }

        // Calculate next retry time
        const delay = this.baseDelay * Math.pow(2, task.attempt - 1);
        const nextRetryAt = new Date(Date.now() + delay);

        // Update delivery log for retry
        await this.db.query(
            `UPDATE delivery_logs 
       SET status = 'pending', 
           response_status = $1, 
           response_body = $2, 
           attempt_count = $3,
           next_retry_at = $4
       WHERE id = $5`,
            [responseStatus, responseBody, task.attempt, nextRetryAt, task.deliveryLogId]
        );

        // Add to retry queue
        await this.redis.zadd(
            'webhook:retry_queue',
            nextRetryAt.getTime(),
            JSON.stringify({
                ...task,
                webhookUrl: webhook.url,
                webhookSecret: webhook.secret,
                attempt: task.attempt + 1,
            })
        );

        logger.warn(`Webhook delivery to ${webhook.url} failed, retry ${task.attempt + 1} scheduled`);
    }

    private async processRetryQueue(): Promise<void> {
        if (this.shutdownRequested) return;

        try {
            const now = Date.now();
            const tasks = await this.redis.zrangebyscore('webhook:retry_queue', 0, now, 'LIMIT', 0, 10);

            for (const taskJson of tasks) {
                if (this.shutdownRequested) break;

                const task = JSON.parse(taskJson) as DeliveryTask & {
                    webhookUrl: string;
                    webhookSecret: string;
                };

                // Remove from queue
                await this.redis.zrem('webhook:retry_queue', taskJson);

                const payload = JSON.stringify(task.event);
                const signature = this.generateSignature(payload, task.webhookSecret);

                try {
                    await this.deliverWebhook(task.webhookUrl, payload, signature);

                    // Update delivery log as success
                    await this.db.query(
                        `UPDATE delivery_logs 
             SET status = 'success', response_status = 200, completed_at = NOW()
             WHERE id = $1`,
                        [task.deliveryLogId]
                    );

                    logger.info(`Webhook retry delivered successfully to ${task.webhookUrl}`);
                } catch (error) {
                    // Get webhook config for retry
                    const webhookResult = await this.db.query(
                        `SELECT id, api_key_id, url, secret, events, is_active FROM webhooks WHERE id = $1`,
                        [task.webhookId]
                    );

                    if (webhookResult.rows.length > 0) {
                        const webhook: WebhookConfig = {
                            id: webhookResult.rows[0].id,
                            apiKeyId: webhookResult.rows[0].api_key_id,
                            url: webhookResult.rows[0].url,
                            secret: webhookResult.rows[0].secret,
                            events: webhookResult.rows[0].events,
                            isActive: webhookResult.rows[0].is_active,
                        };
                        await this.handleDeliveryError(task, webhook, error);
                    }
                }
            }
        } catch (error) {
            logger.error({ err: error }, 'Error processing retry queue');
        }

        // Schedule next check
        if (!this.shutdownRequested) {
            setTimeout(() => this.processRetryQueue(), 1000);
        }
    }

    async shutdown(): Promise<void> {
        this.shutdownRequested = true;
        logger.info('Webhook emitter shutting down...');
    }

    clearCache(): void {
        this.webhookCache.clear();
    }
}
