# Deployment Guide

## Prerequisites

- Docker & Docker Compose
- 2GB+ RAM
- 10GB+ disk space

---

## Quick Start

### 1. Clone and Configure

```bash
cd /Volumes/PortableSSD/PROJECTS/MCPWHATSAPP

# Create environment file
cp .env.example .env

# Edit with your settings
nano .env
```

**Required changes:**
```env
POSTGRES_PASSWORD=your_secure_password
API_SECRET_KEY=generate_random_64_char_string
MCP_API_KEY=your_mcp_service_key
```

### 2. Start Services

```bash
docker-compose up -d
```

### 3. Create Admin API Key

```bash
docker-compose exec api-gateway python -m app.cli create-api-key --name "Admin"
```

**Save the key shown** - it won't be displayed again.

### 4. Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# List devices (with your API key)
curl -H "X-API-Key: wamcp_xxx" http://localhost:8000/devices
```

---

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| API Gateway | 8000 | REST API |
| MCP Server | 8001 | AI tools |
| WhatsApp Engine | 3001 | Internal |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |

---

## Adding a WhatsApp Device

1. Create device via API:
```bash
curl -X POST http://localhost:8000/devices/add \
  -H "X-API-Key: wamcp_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Phone"}'
```

2. Response includes QR code (base64 image)

3. Open WhatsApp on phone → Settings → Linked Devices → Link a Device

4. Scan the QR code

5. Device status changes to `connected`

---

## Production Configuration

### Environment Variables

```env
# Database (use strong passwords)
POSTGRES_PASSWORD=super_secure_password_here

# API Security
API_SECRET_KEY=64_character_random_string

# Rate Limiting (adjust as needed)
RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Logging
LOG_LEVEL=WARNING
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Firewall

Only expose ports 80/443. Internal ports should be blocked:
```bash
# Example UFW rules
ufw allow 80
ufw allow 443
ufw deny 5432
ufw deny 6379
ufw deny 3001
ufw deny 8001
```

---

## Scaling

### Horizontal Scaling

For 100+ devices, consider:

1. **Multiple WhatsApp engines:**
   - Add more `whatsapp-engine` replicas
   - Use load balancer for distribution

2. **Database optimization:**
   - Enable connection pooling (PgBouncer)
   - Add read replicas

3. **Redis cluster:**
   - Use Redis Sentinel or Cluster mode

### Resource Limits

Add to `docker-compose.yml`:
```yaml
services:
  whatsapp-engine:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
```

---

## Backup & Recovery

### Database Backup

```bash
# Backup
docker-compose exec postgres pg_dump -U whatsapp whatsapp_mcp > backup.sql

# Restore
docker-compose exec -T postgres psql -U whatsapp whatsapp_mcp < backup.sql
```

### Session Backup

Sessions are stored in Docker volume `whatsapp_sessions`. Backup with:
```bash
docker run --rm -v whatsapp_sessions:/data -v $(pwd):/backup alpine \
  tar czf /backup/sessions.tar.gz /data
```

---

## Monitoring

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api-gateway
```

### Health Checks

```bash
# API Gateway
curl http://localhost:8000/health

# WhatsApp Engine
curl http://localhost:3001/health
```

---

## Troubleshooting

### Device won't connect

1. Check engine logs: `docker-compose logs whatsapp-engine`
2. Ensure phone has internet
3. Try removing and re-adding device

### Rate limit errors

Increase limit in `.env`:
```env
RATE_LIMIT_REQUESTS_PER_MINUTE=500
```

### Database connection issues

```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready

# Reset if needed
docker-compose down -v
docker-compose up -d
```
