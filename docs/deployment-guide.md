# Resync Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Getting the Code](#getting-the-code)
3. [Environment Configuration](#environment-configuration)
4. [Building Docker Images](#building-docker-images)
5. [Starting the System](#starting-the-system)
6. [Verifying the Deployment](#verifying-the-deployment)
7. [Stopping the System](#stopping-the-system)
8. [Troubleshooting](#troubleshooting)

## Prerequisites
Before proceeding, ensure you have:
- Docker Engine 20.10+
- Docker Compose v2.x
- Python 3.13+ (for local development only)
- Basic understanding of Docker concepts

## Getting the Code
```bash
# Clone the repository
git clone https://github.com/netover/hwa-new-1.git
cd hwa-new-1
```

## Environment Configuration
1. Create a `.env` file from the example:
```bash
cp .env.example .env
```

2. Configure required variables:
   - `TWS_HOST` - TWS server IP/hostname
   - `TWS_PORT` - TWS API port
   - `TWS_USER` - TWS username
   - `TWS_PASSWORD` - TWS password
   - `LLM_ENDPOINT` - LLM service endpoint
   - `LLM_API_KEY` - LLM service API key

## Building Docker Images
```bash
# Build the Resync application image
docker build -t resync:latest .
```

## Starting the System
For development with mock data:
```bash
# Start with mock TWS and all dependencies
docker-compose -f docker-compose.test.yml up -d
```

For production with real TWS:
1. Update `.env` with production credentials
2. Use the standard Docker Compose:
```bash
docker-compose up -d
```

## Verifying the Deployment
Check running containers:
```bash
docker ps
```

Access key services:
- Dashboard: http://localhost:8000/dashboard
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health/app

## Stopping the System
```bash
# Stop containers and remove networks
docker-compose down

# To also remove images:
docker-compose down -rmi all
```

## Troubleshooting
### Common Issues
| Symptom | Possible Cause | Solution |
|---------|----------------|----------|
| Containers not starting | Image build failed | Check Dockerfile syntax |
| Connection refused | Service not running | Verify container status |
| TWS connection errors | Incorrect credentials | Check `.env` settings |
| Memory issues | Insufficient resources | Adjust Docker memory limits |

### Logs
View container logs:
```bash
docker logs resync-worker
```

### Model Issues
If using LLM services:
- Verify `LLM_ENDPOINT` and `LLM_API_KEY`
- Check network connectivity to LLM provider
- Increase timeouts in `resync/core/utils/llm.py` if needed

## Next Steps
After successful deployment:
1. Review system metrics at http://localhost:8000/api/metrics
2. Test chatbot functionality
3. Implement monitoring using Prometheus
4. Set up logging aggregation



