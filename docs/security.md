# Security Hardening Guide

## Overview

This document outlines security measures implemented in the WhatsApp MCP Infrastructure Platform.

---

## Authentication

### API Keys

| Feature | Implementation |
|---------|----------------|
| Storage | SHA-256 hashed, never plaintext |
| Format | Prefixed with `wamcp_` for identification |
| Rotation | Support for multiple keys per client |
| Expiration | Optional expiry dates |
| Revocation | Immediate via `is_active` flag |

**Best Practices:**
- Rotate keys every 90 days
- Use separate keys for different environments
- Never commit keys to source control

---

## Rate Limiting

**Implementation:** Redis-backed sliding window

| Default | Limit |
|---------|-------|
| Requests | 100/minute per API key |
| Configurable | Per-key via database |

**Headers returned on limit:**
```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

---

## Webhook Security

### HMAC Signatures

All webhooks are signed with HMAC-SHA256:

```
X-Webhook-Signature: t=1706000000,v1=abc123...
```

**Verification:**
1. Extract timestamp and signature
2. Compute expected signature: `HMAC-SHA256(timestamp + "." + payload, secret)`
3. Compare using constant-time comparison
4. Reject if timestamp > 5 minutes old (replay protection)

---

## Network Security

### Internal Network

All services communicate via Docker internal network:
- PostgreSQL: Not exposed externally
- Redis: Not exposed externally  
- WhatsApp Engine: Internal only

### Recommended Firewall Rules

```bash
# Allow only HTTPS
ufw default deny incoming
ufw allow 443/tcp

# Block internal ports
ufw deny 5432  # PostgreSQL
ufw deny 6379  # Redis
ufw deny 3001  # WhatsApp Engine
ufw deny 8001  # MCP Server
```

---

## Data Protection

### At Rest

| Data | Protection |
|------|------------|
| API Keys | SHA-256 hashed |
| Sessions | Encrypted by Baileys |
| Media | Local storage with UUID naming |
| Database | PostgreSQL encryption available |

### In Transit

- Use HTTPS/TLS for all external communication
- Internal Docker network for service-to-service

---

## Session Security

### WhatsApp Sessions

- Stored in isolated directories per device
- Baileys uses encrypted auth state
- Sessions tied to specific API keys
- Automatic cleanup on device removal

### Session Isolation

Each API key can only access its own:
- Devices
- Messages
- Webhooks

---

## Input Validation

### API Layer

- Pydantic schema validation
- UUID format enforcement
- Phone number sanitization
- URL validation for webhooks

### Database Layer

- Parameterized queries (SQLAlchemy)
- No raw SQL execution
- Foreign key constraints

---

## Logging & Auditing

### Logged Events

- API key usage (last_used_at)
- Authentication failures
- Message deliveries
- Webhook attempts

### Sensitive Data Handling

- API keys never logged in full
- Message content redacted in logs
- Phone numbers partially masked

---

## Environment Security

### Secrets Management

```bash
# Never in code
POSTGRES_PASSWORD=xxx
API_SECRET_KEY=xxx

# Generate secure values
openssl rand -base64 48
```

### Docker Security

```yaml
# Run as non-root (add to services)
security_opt:
  - no-new-privileges:true
read_only: true
```

---

## Compliance Notes

### Data Retention

- Messages logged for delivery tracking
- Configure retention policies as needed
- GDPR: Implement user data deletion endpoint

### Legal Considerations

⚠️ **Warning:** Automated WhatsApp messaging may violate WhatsApp Terms of Service.

This platform is intended for:
- Internal business communication
- Authorized automation use cases
- Educational purposes

Ensure compliance with:
- WhatsApp Business Policy
- Local communication regulations
- Data protection laws (GDPR, etc.)

---

## Security Checklist

- [ ] Strong passwords in `.env`
- [ ] API keys rotated regularly
- [ ] HTTPS enabled
- [ ] Firewall configured
- [ ] Logs monitored
- [ ] Regular backups
- [ ] Dependency updates scheduled
