# Flight Price Tracking System 🛫

A comprehensive flight price monitoring and notification system with Telegram integration. Track flight prices and get instant notifications when prices change!

## 🚀 Features

- **Real-time Flight Price Tracking**: Monitor flight prices from major airlines
- **Telegram Notifications**: Get instant alerts when prices drop or change
- **Web Interface**: Easy-to-use web form for creating tracking requests
- **Background Monitoring**: Automated price checking every 2 hours
- **Price History**: Track price trends over time
- **Multi-user Support**: Multiple users can track different flights
- **Docker Deployment**: One-command deployment with Docker Compose

## 🏗️ Architecture

### Tech Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Celery
- **Frontend**: React, JavaScript, HTML/CSS
- **Database**: PostgreSQL 15
- **Cache/Broker**: Redis 6
- **APIs**: Amadeus Flight API, Telegram Bot API
- **Deployment**: Docker, docker-compose

### System Components
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Frontend  │────│  FastAPI Backend │────│   PostgreSQL    │
│   (React UI)    │    │  (Python API)    │    │   (Database)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │      Redis      │
                       │  (Cache/Broker) │
                       └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │   Celery Tasks  │
                       │ (Price Monitor) │
                       └─────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
            ┌───────▼──────┐       ┌───────▼──────┐
            │ Amadeus API  │       │ Telegram API │
            │ (Flight Data)│       │(Notifications)│
            └──────────────┘       └──────────────┘
```

## 📋 Prerequisites

- **Docker & Docker Compose** (recommended - easiest setup)
- OR **Manual Setup**: Python 3.11+, PostgreSQL 14+, Redis 6+

## � API Keys Setup (Required)

Before deployment, you'll need to obtain API keys from external services. Follow these steps carefully:

### 1. Amadeus Flight API Setup

The Amadeus API provides real-time flight data and pricing.

#### Step-by-Step Instructions:

1. **Visit Amadeus Developer Portal**
   - Go to: https://developers.amadeus.com/
   - Click "Register" in the top-right corner

2. **Create Account**
   - Fill out the registration form with your details
   - Verify your email address
   - Complete profile setup

3. **Create Application**
   - After login, go to "My Applications"
   - Click "Create New App"
   - Fill in application details:
     - **App Name**: `Flight Price Tracker`
     - **Description**: `Personal flight price monitoring system`
     - **App Type**: Choose "Personal" or "Hobby"

4. **Get API Credentials**
   - Once created, click on your application
   - Copy the **API Key** and **API Secret**
   - These will look like:
     ```
     API Key: AbCdEf123456789
     API Secret: XyZ987654321
     ```

5. **Test Environment vs Production**
   - **Test API**: Free, limited data (perfect for development)
   - **Production API**: Paid, real-time data (for production use)
   - Start with Test API: `https://test.api.amadeus.com`

#### Amadeus API Limits:
- **Test Environment**: 2,000 API calls/month (Free)
- **Production**: Pay-per-use pricing
- **Rate Limits**: 10 requests/second

### 2. Telegram Bot Setup

The Telegram Bot sends price change notifications to users.

#### Step-by-Step Instructions:

1. **Open Telegram**
   - Install Telegram on your phone/computer
   - Create account if needed

2. **Create Bot with BotFather**
   - Search for `@BotFather` in Telegram
   - Start chat with BotFather
   - Send `/newbot` command

3. **Configure Your Bot**
   - BotFather will ask for bot name: `FlightPriceTracker` (or any name)
   - BotFather will ask for username: `your_flight_tracker_bot` (must end with 'bot')
   - **Save the Bot Token** - looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

4. **Get Your Chat ID** (for testing)
   - Search for `@userinfobot` in Telegram
   - Send `/start` to get your Chat ID
   - Save this number (looks like: `987654321`)

#### Telegram Bot Configuration:
```bash
# Your bot token from BotFather
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# Your chat ID for testing (optional)
TEST_TELEGRAM_CHAT_ID=987654321
```

### 3. Generate Secret Key

For application security, generate a strong secret key:

```bash
# Method 1: Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Method 2: Using OpenSSL  
openssl rand -base64 32

# Method 3: Online generator (for development only)
# Visit: https://generate-secret.vercel.app/32
```

Save the generated key - looks like: `Kx7SmD9vF2nP8qR3tY6wE9rT2uI5oP1sA4dF7gH0jK3l`

## 🐳 Docker Deployment (Recommended)

The easiest way to run the entire system with one command.

### Quick Start

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd flight-price-tracker
   ```

2. **Create Environment File**
   ```bash
   cp .env.example .env
   ```

3. **Configure Environment Variables**
   Edit `.env` file with your API keys:
   ```env
   # ===== REQUIRED API KEYS =====
   # Get from: https://developers.amadeus.com/
   AMADEUS_API_KEY=your_amadeus_api_key_here
   AMADEUS_API_SECRET=your_amadeus_api_secret_here
   
   # Get from: @BotFather on Telegram
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   
   # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
   SECRET_KEY=your_generated_secret_key_here
   
   # ===== DATABASE & REDIS (Auto-configured) =====
   DATABASE_URL=postgresql://flight_user:flight_pass@db:5432/flight_tracker
   REDIS_URL=redis://redis:6379/0
   
   # ===== APPLICATION SETTINGS =====
   ENVIRONMENT=production
   DEBUG=false
   LOG_LEVEL=INFO
   
   # CORS settings for frontend access
   ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
   CORS_ORIGINS=http://localhost,http://127.0.0.1
   
   # Price monitoring settings
   PRICE_CHECK_INTERVAL_MINUTES=120
   PRICE_CHANGE_THRESHOLD_PERCENT=5.0
   MAX_TRACKING_REQUESTS_PER_USER=10
   
   # Rate limiting
   API_RATE_LIMIT=100
   MAX_NOTIFICATIONS_PER_DAY=50
   
   # Cache settings
   CACHE_TTL_MINUTES=15
   
   # Amadeus API settings
   AMADEUS_BASE_URL=https://test.api.amadeus.com
   AMADEUS_TIMEOUT=30
   
   # Telegram settings
   TELEGRAM_API_TIMEOUT=30
   TELEGRAM_MAX_RETRIES=3
   
   # Testing (optional)
   USE_MOCK_FLIGHT_DATA=false
   ```

4. **Deploy with Docker Compose**
   ```bash
   # Build and start all services
   docker compose up -d
   
   # Check service status
   docker compose ps
   
   # View logs
   docker compose logs -f
   ```

5. **Verify Deployment**
   ```bash
   # Test API health
   curl http://localhost:8000/health
   
   # Access web interface
   open http://localhost
   ```

### Docker Services

The deployment includes these containers:

| Service | Description | Port | Health Check |
|---------|-------------|------|--------------|
| **frontend** | React web interface | 80 | `http://localhost/` |
| **backend** | FastAPI REST API | 8000 | `http://localhost:8000/health` |
| **worker** | Celery background tasks | - | Check logs |
| **scheduler** | Celery beat scheduler | - | Check logs |
| **db** | PostgreSQL database | 5432 | Auto-configured |
| **redis** | Redis cache/broker | 6379 | Auto-configured |

### Docker Commands

```bash
# Start services
docker compose up -d

# Stop services  
docker compose down

# Rebuild after code changes
docker compose build
docker compose up -d

# View logs
docker compose logs backend
docker compose logs worker
docker compose logs -f  # Follow all logs

# Database operations
docker compose exec db psql -U flight_user -d flight_tracker

# Redis operations
docker compose exec redis redis-cli

# Backend shell access
docker compose exec backend bash

# Restart specific service
docker compose restart backend
```

## 🚀 Usage Guide

### Getting Started

1. **Access the Web Interface**
   - Open your browser to `http://localhost` (Docker) or `http://localhost:3000` (manual)
   - You'll see the flight tracking form

2. **Create Your First Tracking Request**

   Fill out the form:
   - **Origin Airport**: Use IATA codes (e.g., `JFK`, `LAX`, `LHR`)
   - **Destination Airport**: Use IATA codes (e.g., `SFO`, `CDG`, `NRT`)  
   - **Departure Date**: Pick a future date
   - **Return Date**: Optional for round trips
   - **Telegram Chat ID**: Your Telegram user ID

3. **Get Your Telegram Chat ID**
   - Open Telegram and message `@userinfobot`
   - Send `/start` command
   - Bot will reply with your Chat ID (e.g., `123456789`)
   - Use this number in the form

### Example Flight Tracking

```
✈️ Example tracking request:
Origin: JFK (New York)
Destination: LAX (Los Angeles) 
Departure: 2025-12-15
Return: 2025-12-22
Chat ID: 123456789
```

### Notification Examples

When prices change, you'll receive Telegram messages like:

```
✈️ PRICE DROP ALERT!
JFK → LAX on 2025-12-15

Old Price: $299.99
New Price: $249.99  
You Save: $50.00 (16.7% ⬇️)

Book now: https://amadeus.com/booking/xyz123
Tracked since: 2025-09-20 14:30
```

### API Usage

The system provides a REST API for programmatic access:

```bash
# Create tracking request
curl -X POST http://localhost:8000/api/v1/tracking/requests \
  -H "Content-Type: application/json" \
  -d '{
    "origin_iata": "JFK",
    "destination_iata": "LAX", 
    "departure_date": "2025-12-15",
    "return_date": "2025-12-22",
    "telegram_chat_id": 123456789
  }'

# Get user's tracking requests  
curl "http://localhost:8000/api/v1/tracking/requests?telegram_chat_id=123456789"

# Get specific tracking request
curl "http://localhost:8000/api/v1/tracking/requests/{request_id}"

# Cancel tracking
curl -X DELETE "http://localhost:8000/api/v1/tracking/requests/{request_id}"
```

### API Documentation

- **OpenAPI Docs**: `http://localhost:8000/docs` (Interactive Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc` (Alternative documentation)

## 🧪 Testing & Validation

### Health Checks

Verify all services are running:

```bash
# API Health
curl http://localhost:8000/health
# Should return: {"status": "healthy", "services": {...}}

# Database Check
curl http://localhost:8000/health | jq '.services.database'
# Should return: {"status": "healthy"}

# Redis Check  
curl http://localhost:8000/health | jq '.services.redis'
# Should return: {"status": "healthy"}

# Telegram Bot Check
curl http://localhost:8000/health | jq '.services.telegram'  
# Should return: {"status": "healthy"} (if bot token is valid)
```

### Test Flight Search

```bash
# Search flights (test Amadeus API)
curl "http://localhost:8000/api/v1/flights/search?origin=JFK&destination=LAX&departure_date=2025-12-15"
```

### Test Notifications

```bash
# Send test notification
curl -X POST http://localhost:8000/api/v1/test/notification \
  -H "Content-Type: application/json" \
  -d '{"chat_id": 123456789, "message": "Test notification"}'
```

### Run Test Suite

```bash
# Docker environment
docker compose exec backend pytest

# Manual environment  
cd backend && pytest
```

## 🔧 Configuration Options

### Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AMADEUS_API_KEY` | Amadeus API key | - | ✅ |
| `AMADEUS_API_SECRET` | Amadeus API secret | - | ✅ |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - | ✅ |
| `SECRET_KEY` | App security key | - | ✅ |
| `DATABASE_URL` | PostgreSQL connection | - | ✅ |
| `REDIS_URL` | Redis connection | - | ✅ |
| `PRICE_CHECK_INTERVAL_MINUTES` | How often to check prices | 120 | ❌ |
| `PRICE_CHANGE_THRESHOLD_PERCENT` | Min % change for notification | 5.0 | ❌ |
| `MAX_TRACKING_REQUESTS_PER_USER` | Max requests per user | 10 | ❌ |
| `API_RATE_LIMIT` | API requests per minute | 100 | ❌ |
| `ENVIRONMENT` | Environment mode | development | ❌ |
| `DEBUG` | Enable debug mode | false | ❌ |
| `LOG_LEVEL` | Logging level | INFO | ❌ |

### Advanced Configuration

```env
# Performance tuning
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
REDIS_MAX_CONNECTIONS=20
CACHE_TTL_MINUTES=15

# Monitoring  
ENABLE_METRICS=true
METRICS_PORT=9090
SENTRY_DSN=https://your-sentry-dsn

# Security
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
CORS_ORIGINS=http://localhost,https://yourdomain.com

# External API settings
AMADEUS_BASE_URL=https://test.api.amadeus.com
AMADEUS_TIMEOUT=30
TELEGRAM_API_TIMEOUT=30
TELEGRAM_MAX_RETRIES=3
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Backend API Not Starting

**Symptom**: `docker compose ps` shows backend as unhealthy

**Solutions**:
```bash
# Check logs
docker compose logs backend

# Common fixes:
# - Verify API keys in .env file
# - Check database connection
# - Ensure Redis is running

# Restart backend
docker compose restart backend
```

#### 2. Database Connection Failed

**Symptom**: Error: `could not connect to server`

**Solutions**:
```bash
# Check database container
docker compose logs db

# Restart database
docker compose restart db

# Manual connection test
docker compose exec db psql -U flight_user -d flight_tracker
```

#### 3. Telegram Bot Not Working  

**Symptom**: Health check shows telegram service unhealthy

**Solutions**:
```bash
# Verify bot token format
echo $TELEGRAM_BOT_TOKEN
# Should look like: 123456789:ABCdefGHI...

# Test bot manually
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"

# Create new bot if needed (@BotFather)
```

#### 4. Amadeus API Errors

**Symptom**: Flight search fails or returns errors

**Solutions**:
```bash
# Check API quota
curl "https://test.api.amadeus.com/v1/reference-data/airlines" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Verify credentials at https://developers.amadeus.com/
# Check rate limits (10 requests/second)
# Switch to production API if needed
```

#### 5. Frontend Not Loading

**Symptom**: Browser shows "This site can't be reached"

**Solutions**:
```bash
# Check frontend container
docker compose logs frontend

# Verify nginx configuration  
docker compose exec frontend cat /etc/nginx/nginx.conf
# Or check the source config
cat nginx/nginx.conf

# Access backend directly
curl http://localhost:8000/health
```

### Debug Mode

Enable detailed logging:

```env
# In .env file
DEBUG=true
LOG_LEVEL=DEBUG

# Restart services
docker compose down
docker compose up -d
```

### Service Status Dashboard

Check all services at once:

```bash
#!/bin/bash
echo "=== Flight Tracker System Status ==="
echo "Frontend: $(curl -s -o /dev/null -w "%{http_code}" http://localhost)"
echo "Backend:  $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)"
echo "Database: $(docker compose exec -T db pg_isready -U flight_user)"
echo "Redis:    $(docker compose exec -T redis redis-cli ping)"
```

### Getting Help

1. **Check Logs**: Always start with `docker compose logs -f`
2. **Health Endpoint**: Use `/health` to diagnose service issues  
3. **API Docs**: Visit `/docs` for API testing
4. **GitHub Issues**: Report bugs with logs and configuration  
docker compose logs worker | grep "Price check failed"

# Notification failures
docker compose logs worker | grep "Notification failed"

# Database connection issues
docker compose logs backend | grep "database"
```

## 👨‍💻 Development Guide

### Project Structure

```
flight-price-tracker/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI endpoints
│   │   ├── models/       # Database models
│   │   ├── services/     # Business logic
│   │   ├── tasks/        # Celery background tasks
│   │   ├── config.py     # Configuration
│   │   └── main.py       # FastAPI app
│   ├── tests/            # Test suite
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   └── services/     # API clients
│   ├── public/           # Static assets
│   └── Dockerfile
├── docker-compose.yml    # Service orchestration
├── .env.example         # Environment template
└── README.md
```

### Contributing

1. **Fork Repository**: Create your own fork
2. **Create Branch**: `git checkout -b feature/your-feature`
3. **Write Tests**: Add tests for new functionality
4. **Follow Standards**: Use Black formatting, type hints
5. **Submit PR**: Create pull request with description

### Code Quality

```bash
# Python formatting
black backend/src/
isort backend/src/

# Type checking
mypy backend/src/

# Linting
flake8 backend/src/

# Testing
pytest backend/tests/
```

### Adding New Features

1. **API Endpoints**: Add to `backend/src/api/`
2. **Database Models**: Add to `backend/src/models/`
3. **Background Tasks**: Add to `backend/src/tasks/`
4. **Frontend Pages**: Add to `frontend/src/pages/`
5. **Tests**: Add comprehensive tests

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

- **Documentation**: This README and `/docs` endpoint
- **Issues**: GitHub Issues for bug reports
- **Discussions**: GitHub Discussions for questions
- **API Docs**: Interactive docs at `/docs` endpoint

## 🔄 Changelog

### v1.0.0 (2025-09-20)
- ✅ Initial release with complete Docker deployment
- ✅ FastAPI backend with comprehensive API
- ✅ React frontend with responsive design  
- ✅ PostgreSQL database with migrations
- ✅ Redis caching and Celery background processing
- ✅ Amadeus Flight API integration
- ✅ Telegram Bot notifications
- ✅ Comprehensive test suite
- ✅ Production-ready Docker configuration
- ✅ Health monitoring and metrics
- ✅ WCAG 2.1 AA accessibility compliance

---

**🛫 Happy Flight Tracking!** 

Need help? Check the troubleshooting section or open an issue!
```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d
```

#### 3. Initialize Database
```bash
# Run database migrations
docker-compose exec backend alembic upgrade head
```

## 🔧 Configuration

### Environment Variables

#### Required Variables
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `AMADEUS_API_KEY`: Amadeus API key for flight data
- `AMADEUS_API_SECRET`: Amadeus API secret
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for notifications

#### Optional Variables
- `SECRET_KEY`: Application secret key (auto-generated if not provided)
- `DEBUG`: Enable debug mode (default: false)
- `LOG_LEVEL`: Logging level (default: INFO)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `CORS_ORIGINS`: Comma-separated list of CORS origins

### API Keys Setup

#### Amadeus API
1. Register at [Amadeus for Developers](https://developers.amadeus.com/)
2. Create a new application
3. Copy your API Key and API Secret to the environment variables

#### Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token to the environment variables

## 📖 API Documentation

### Endpoints Overview

#### Health Check
- `GET /api/v1/health` - System health status

#### Flight Operations
- `GET /api/v1/flights/search` - Search for flights
- `GET /api/v1/flights/offers/{offer_id}` - Get specific flight offer

#### Tracking Operations
- `POST /api/v1/tracking/requests` - Create price tracking request
- `GET /api/v1/tracking/requests` - List user's tracking requests
- `GET /api/v1/tracking/requests/{request_id}` - Get specific tracking request
- `PUT /api/v1/tracking/requests/{request_id}` - Update tracking request
- `DELETE /api/v1/tracking/requests/{request_id}` - Delete tracking request
- `GET /api/v1/tracking/requests/{request_id}/history` - Get price history

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Example API Requests

#### Search Flights
```bash
curl -X GET \"http://localhost:8000/api/v1/flights/search\" \\
  -H \"Content-Type: application/json\" \\
  -G \\
  -d \"origin=JFK\" \\
  -d \"destination=LAX\" \\
  -d \"departure_date=2024-02-15\" \\
  -d \"passengers=1\"
```

#### Create Tracking Request
```bash
curl -X POST \"http://localhost:8000/api/v1/tracking/requests\" \\
  -H \"Content-Type: application/json\" \\
  -H \"X-User-ID: user123\" \\
  -d '{
    \"user_id\": \"user123\",
    \"origin_airport\": \"JFK\",
    \"destination_airport\": \"LAX\", 
    \"departure_date\": \"2024-02-15\",
    \"passengers\": 1,
    \"cabin_class\": \"economy\",
    \"max_price\": 400.0,
    \"telegram_chat_id\": 123456789
  }'
```

## 🖥️ Frontend Usage

### Accessing the Application
- **Development**: http://localhost:3000
- **Production**: http://localhost:8000 (served by FastAPI)

### Key Features

#### Flight Search
1. Enter departure and destination airports
2. Select travel dates
3. Choose number of passengers and cabin class
4. View real-time flight results with prices

#### Price Tracking
1. Search for flights
2. Click \"Track Price\" on any flight
3. Set maximum acceptable price
4. Provide Telegram chat ID for notifications
5. Monitor price changes in your dashboard

#### Price History
1. View historical price data for tracked flights
2. Analyze price trends over time
3. Identify optimal booking windows

## 🧪 Testing

### Backend Tests
```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
pytest tests/performance/   # Performance tests
```

### Frontend Tests
```bash
cd frontend

# Run unit tests
npm run test

# Run with coverage
npm run test:coverage

# Run e2e tests
npm run test:e2e
```

## 🤝 Contributing

### Code Quality Standards
- Follow PEP 8 for Python code  
- Use TypeScript for frontend development
- Maintain test coverage above 80%
- Add documentation for new features
- Follow conventional commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support & Contact

- **Email**: [ngdluan@outlook.com](mailto:ngdluan@outlook.com)
- **Website**: [ngdluan.com](https://ngdluan.com)
- **Documentation**: [API Docs](http://localhost:8000/docs)
- **Issues**: [GitHub Issues](https://github.com/ngdluan/flight-price-tracker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ngdluan/flight-price-tracker/discussions)

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [Amadeus](https://developers.amadeus.com/) for flight data API
- [Telegram](https://core.telegram.org/bots/api) for notification system
- All contributors who help improve this project

---

**Happy Flight Tracking!** ✈️

*Created with ❤️ by [ngdluan](https://ngdluan.com)*