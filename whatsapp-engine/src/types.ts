// Type definitions for WhatsApp Engine

export interface DeviceConfig {
    id: string;
    apiKeyId: string;
    name: string;
    phoneNumber?: string;
}

export interface SessionState {
    deviceId: string;
    status: 'pending' | 'qr' | 'connecting' | 'connected' | 'disconnected';
    qrCode?: string;
    phoneNumber?: string;
    connectedAt?: Date;
    disconnectedAt?: Date;
}

export interface MessagePayload {
    deviceId: string;
    recipient: string;
    type: 'text' | 'image' | 'video' | 'audio' | 'document' | 'location';
    content?: string;
    caption?: string;
    mediaUrl?: string;
    mediaBase64?: string;
    mimeType?: string;
    filename?: string;
    latitude?: number;
    longitude?: number;
    locationName?: string;
    locationAddress?: string;
}

export interface MessageResult {
    success: boolean;
    messageId?: string;
    error?: string;
    timestamp?: Date;
}

export interface WebhookEvent {
    event: string;
    timestamp: string;
    deviceId: string;
    data: Record<string, unknown>;
}

export interface InboundMessage {
    messageId: string;
    deviceId: string;
    sender: string;
    senderName?: string;
    type: string;
    content?: string;
    caption?: string;
    mediaUrl?: string;
    timestamp: Date;
    isGroup: boolean;
    groupId?: string;
    groupName?: string;
    quotedMessage?: {
        messageId: string;
        content?: string;
    };
}

export interface DeviceStatus {
    id: string;
    name: string;
    phoneNumber?: string;
    status: string;
    connectedAt?: Date;
    lastSeenAt?: Date;
}

export interface QRResponse {
    deviceId: string;
    qrCode: string;
    expiresIn: number;
}

export interface ApiResponse<T = unknown> {
    success: boolean;
    data?: T;
    error?: string;
}
