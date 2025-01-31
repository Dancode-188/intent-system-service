# Prediction Service Deployment Guide

## Overview
This guide covers the deployment of the Prediction Service, including both development and production environments, with detailed instructions for container orchestration, database setup, and monitoring configuration.

## Deployment Architecture

```mermaid
graph TB
    LB[Load Balancer] --> S1[Service Instance 1]
    LB --> S2[Service Instance 2]
    LB --> S3[Service Instance N]
    
    subgraph Data Layer
        S1 --> DB[(TimescaleDB)]
        S1 --> RC[(Redis Cache)]
        S2 --> DB
        S2 --> RC
        S3 --> DB
        S3 --> RC
    end
    
    subgraph Monitoring
        S1 --> P[Prometheus]
        S2 --> P
        S3 --> P
        P --> G[Grafana]
    end
```

## Container Configuration

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose Configuration
```yaml
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg14
    environment:
      - POSTGRES_USER=prediction_user
      - POSTGRES_PASSWORD=prediction_pass
      - POSTGRES_DB=prediction_db
      - TIMESCALEDB_TELEMETRY=off
    ports:
      - "5432:5432"
    volumes:
      - timescale_data:/var/lib/postgresql/data
      - ./scripts/db_setup.sql:/docker-entrypoint-initdb.d/db_setup.sql
    networks:
      - prediction_network
    command: ["postgres", "-c", "listen_addresses=*"]

  redis:
    image: redis:latest
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - prediction_network

  prediction_service:
    build: .
    depends_on:
      - timescaledb
      - redis
    environment:
      - PREDICTION_TIMESCALE_URL=postgresql://prediction_user:prediction_pass@timescaledb:5432/prediction_db
      - PREDICTION_REDIS_URL=redis://redis:6379/0
      - PREDICTION_MODEL_PATH=/app/models
    ports:
      - "8002:8000"
    volumes:
      - ./models:/app/models
    networks:
      - prediction_network
    restart: on-failure
```

## Deployment Environments

### 1. Development Environment
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Initialize database
./scripts/init.sh

# Start service with hot reload
uvicorn app.main:app --reload --port 8002
```

### 2. Staging Environment
```bash
# Deploy to staging
docker-compose -f docker-compose.staging.yml up -d

# Run database migrations
./scripts/migrate.sh staging

# Verify deployment
./scripts/healthcheck.sh
```

### 3. Production Environment
```bash
# Deploy to production
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale prediction_service=3

# Monitor deployment
docker-compose -f docker-compose.prod.yml logs -f
```

## Database Setup

### 1. TimescaleDB Configuration
```sql
-- Initialize TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create hypertable
SELECT create_hypertable('prediction_metrics', 'time');

-- Set retention policy
SELECT add_retention_policy(
    'prediction_metrics',
    INTERVAL '30 days'
);
```

### 2. Database Initialization
```bash
#!/bin/bash
# init.sh

# Wait for TimescaleDB
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "timescaledb" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  echo "TimescaleDB is unavailable - sleeping"
  sleep 1
done

# Run schema setup
PGPASSWORD=$POSTGRES_PASSWORD psql -h "timescaledb" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/db_setup.sql
```

## Monitoring Setup

### 1. Prometheus Configuration
`prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prediction_service'
    static_configs:
      - targets: ['prediction_service:8002']
    metrics_path: '/metrics'
```

### 2. Grafana Dashboard
```json
{
  "dashboard": {
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(prediction_service_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, prediction_service_request_duration_seconds)"
          }
        ]
      }
    ]
  }
}
```

## Scaling Strategy

### 1. Horizontal Scaling
```yaml
# docker-compose.prod.yml
services:
  prediction_service:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
```

### 2. Load Balancer Configuration
```nginx
# nginx.conf
upstream prediction_backend {
    server prediction_service:8002;
    server prediction_service:8003;
    server prediction_service:8004;
}

server {
    location /api/ {
        proxy_pass http://prediction_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Backup and Recovery

### 1. Database Backup
```bash
#!/bin/bash
# backup.sh

# Set variables
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
pg_dump -h timescaledb -U prediction_user -d prediction_db \
    -F c -f "${BACKUP_DIR}/prediction_db_${TIMESTAMP}.dump"

# Rotate old backups
find ${BACKUP_DIR} -type f -mtime +7 -delete
```

### 2. Recovery Procedure
```bash
#!/bin/bash
# restore.sh

# Restore from backup
pg_restore -h timescaledb -U prediction_user -d prediction_db \
    --clean --if-exists "${BACKUP_FILE}"

# Verify restore
psql -h timescaledb -U prediction_user -d prediction_db \
    -c "SELECT count(*) FROM predictions;"
```

## Security Configuration

### 1. SSL/TLS Setup
```nginx
# nginx-ssl.conf
server {
    listen 443 ssl;
    server_name prediction-service.example.com;

    ssl_certificate /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;
    
    location /api/ {
        proxy_pass http://prediction_backend;
    }
}
```

### 2. Environment Security
```yaml
# Production environment settings
environment:
  - PREDICTION_API_KEY=${API_KEY}
  - PREDICTION_JWT_SECRET=${JWT_SECRET}
  - PREDICTION_SSL_CERT=/etc/ssl/certs/service.crt
```

## CI/CD Pipeline

### 1. GitHub Actions Deployment
`.github/workflows/deploy.yml`:
```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build and test
        run: |
          docker-compose -f docker-compose.test.yml up --build -d
          docker-compose -f docker-compose.test.yml run test
      
      - name: Deploy to production
        if: success()
        run: |
          docker-compose -f docker-compose.prod.yml build
          docker-compose -f docker-compose.prod.yml up -d
```

## Performance Tuning

### 1. TimescaleDB Tuning
```sql
ALTER SYSTEM SET max_connections = '200';
ALTER SYSTEM SET shared_buffers = '1GB';
ALTER SYSTEM SET work_mem = '32MB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
```

### 2. Redis Configuration
```conf
maxmemory 2gb
maxmemory-policy allkeys-lru
timeout 300
tcp-keepalive 60
```

## Monitoring Checklist

### 1. System Health
- [ ] CPU Usage < 80%
- [ ] Memory Usage < 80%
- [ ] Disk Space > 20% free
- [ ] Network I/O within limits

### 2. Application Metrics
- [ ] Response Time < 200ms (p95)
- [ ] Error Rate < 0.1%
- [ ] Request Success Rate > 99.9%
- [ ] Cache Hit Rate > 80%

## Troubleshooting Guide

### 1. Common Issues
```bash
# Check service logs
docker-compose logs -f prediction_service

# Check database connectivity
docker-compose exec prediction_service python -c "
import asyncio
import asyncpg

async def test_db():
    try:
        conn = await asyncpg.connect('postgresql://prediction_user:prediction_pass@timescaledb/prediction_db')
        await conn.execute('SELECT 1')
        print('Database connection successful')
    except Exception as e:
        print(f'Database connection failed: {e}')

asyncio.run(test_db())
"
```

### 2. Health Checks
```bash
# Check service health
curl http://localhost:8002/health

# Check database health
docker-compose exec timescaledb pg_isready

# Check Redis health
docker-compose exec redis redis-cli ping
```

## Rollback Procedures

### 1. Service Rollback
```bash
# Rollback to previous version
docker-compose -f docker-compose.prod.yml down
docker image tag prediction-service:latest prediction-service:rollback
docker image tag prediction-service:previous prediction-service:latest
docker-compose -f docker-compose.prod.yml up -d
```

### 2. Database Rollback
```bash
# Rollback database changes
psql -h timescaledb -U prediction_user -d prediction_db -f rollback.sql
```