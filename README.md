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

## 🏗️ Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Celery
- **Frontend**: JavaScript, HTML/CSS
- **Database**: PostgreSQL 15
- **Cache/Broker**: Redis 6
- **APIs**: Amadeus Flight API, Telegram Bot API
- **Deployment**: Docker, docker-compose

## 📋 Prerequisites

- **Docker & Docker Compose** (recommended)
- OR **Manual Setup**: Python 3.11+, PostgreSQL 14+, Redis 6+

## 🔑 API Keys Setup

Before deployment, obtain these API keys:

### 1. Amadeus Flight API
1. Visit [Amadeus Developer Portal](https://developers.amadeus.com/)
2. Create account and new application
3. Copy **API Key** and **API Secret**
4. Start with Test environment (free 2,000 calls/month)

### 2. Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` command and follow instructions
3. Save the **Bot Token** (format: `123456789:ABCdefGHI...`)
4. Get your Chat ID from [@userinfobot](https://t.me/userinfobot)

### 3. Secret Key
Generate a secure key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 🐳 Quick Start with Docker

1. **Clone Repository**
   ```bash
   git clone https://github.com/ngdbruce/flight-price-tracker.git
   cd flight-price-tracker
   ```

2. **Create Environment File**
   ```bash
   cp .env.example .env
   ```

3. **Configure Environment Variables**
   Edit `.env` file with your API keys:
   ```env
   # Required API Keys
   AMADEUS_API_KEY=your_amadeus_api_key_here
   AMADEUS_API_SECRET=your_amadeus_api_secret_here
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   SECRET_KEY=your_generated_secret_key_here
   
   # Database & Redis (auto-configured)
   DATABASE_URL=postgresql://flight_user:flight_pass@db:5432/flight_tracker
   REDIS_URL=redis://redis:6379/0
   
   # Application Settings
   ENVIRONMENT=production
   DEBUG=false
   PRICE_CHECK_INTERVAL_MINUTES=120
   PRICE_CHANGE_THRESHOLD_PERCENT=5.0
   MAX_TRACKING_REQUESTS_PER_USER=10
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

5. **Access the Application**
   - **Web Interface**: http://localhost
   - **API Documentation**: http://localhost:8000/docs
   - **Health Check**: http://localhost:8000/health

## 🚀 Usage Guide

### Creating Your First Flight Track

1. **Access Web Interface** at http://localhost
2. **Fill the Form**:
   - Origin Airport: Use IATA codes (e.g., `JFK`, `LAX`)
   - Destination Airport: Use IATA codes (e.g., `SFO`, `CDG`)
   - Departure Date: Pick a future date
   - Return Date: Optional for round trips
   - Telegram Chat ID: Your Telegram user ID

3. **Example Request**:
   ```
   Origin: JFK (New York)
   Destination: LAX (Los Angeles) 
   Departure: 2025-12-15
   Return: 2025-12-22
   Chat ID: 123456789
   ```

### Notification Example

When prices change, you'll receive Telegram messages like:
```
✈️ PRICE DROP ALERT!
JFK → LAX on 2025-12-15

Old Price: $299.99
New Price: $249.99  
You Save: $50.00 (16.7% ⬇️)

Tracked since: 2025-09-20 14:30
```

## 🔧 Docker Services

| Service | Description | Port | Health Check |
|---------|-------------|------|--------------|
| **frontend** | Web interface | 80 | `http://localhost/` |
| **backend** | FastAPI REST API | 8000 | `http://localhost:8000/health` |
| **worker** | Celery background tasks | - | Check logs |
| **scheduler** | Celery beat scheduler | - | Check logs |
| **db** | PostgreSQL database | 5432 | Auto-configured |
| **redis** | Redis cache/broker | 6379 | Auto-configured |

### Useful Docker Commands

```bash
# Start services
docker compose up -d

# Stop services  
docker compose down

# Rebuild after code changes
docker compose build && docker compose up -d

# View logs
docker compose logs backend
docker compose logs worker
docker compose logs -f  # Follow all logs

# Restart specific service
docker compose restart backend
```

## 📖 API Documentation

### Key Endpoints

- `GET /health` - System health status
- `GET /api/v1/flights/search` - Search for flights
- `POST /api/v1/tracking/requests` - Create price tracking
- `GET /api/v1/tracking/requests` - List user's tracking requests
- `DELETE /api/v1/tracking/requests/{id}` - Cancel tracking

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Example API Usage

```bash
# Search flights
curl "http://localhost:8000/api/v1/flights/search?origin=JFK&destination=LAX&departure_date=2025-12-15"

# Create tracking request
curl -X POST http://localhost:8000/api/v1/tracking/requests \
  -H "Content-Type: application/json" \
  -d '{
    "origin_iata": "JFK",
    "destination_iata": "LAX", 
    "departure_date": "2025-12-15",
    "telegram_chat_id": 123456789
  }'
```

## 🧪 Testing & Health Checks

### Verify Services

```bash
# API Health
curl http://localhost:8000/health

# Test flight search
curl "http://localhost:8000/api/v1/flights/search?origin=JFK&destination=LAX&departure_date=2025-12-15"

# Send test notification
curl -X POST http://localhost:8000/api/v1/test/notification \
  -H "Content-Type: application/json" \
  -d '{"chat_id": 123456789, "message": "Test notification"}'
```

### Run Tests

```bash
# Backend tests
docker compose exec backend pytest

# With coverage
docker compose exec backend pytest --cov=src
```

## 🐛 Troubleshooting

### Common Issues

1. **Backend Not Starting**: Check logs with `docker compose logs backend`
2. **Database Connection Failed**: Restart with `docker compose restart db`
3. **Telegram Bot Not Working**: Verify bot token format and test manually
4. **Amadeus API Errors**: Check API quota and credentials
5. **Frontend Not Loading**: Check nginx logs with `docker compose logs frontend`

### Debug Mode

Enable detailed logging:
```env
# In .env file
DEBUG=true
LOG_LEVEL=DEBUG
```

Then restart: `docker compose down && docker compose up -d`

## 🔧 Configuration

### Environment Variables

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

## 👨‍💻 Development

### Project Structure

```
flight-price-tracker/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI endpoints
│   │   ├── models/       # Database models
│   │   ├── services/     # Business logic
│   │   ├── tasks/        # Celery background tasks
│   │   └── main.py       # FastAPI app
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── scripts/      # JavaScript files
│   │   └── styles/       # CSS files
│   └── index.html
├── docker-compose.yml    # Service orchestration
├── .env.example         # Environment template
└── README.md
```

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Write tests for new functionality
4. Follow code quality standards (Black, flake8)
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

- **Issues**: [GitHub Issues](https://github.com/ngdbruce/flight-price-tracker/issues)
- **API Docs**: Interactive docs at `/docs` endpoint
- **Email**: ngdluan@outlook.com

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [Amadeus](https://developers.amadeus.com/) for flight data API
- [Telegram](https://core.telegram.org/bots/api) for notification system

---

**🛫 Happy Flight Tracking!**

*Created with ❤️ by [ngdbruce](https://github.com/ngdbruce)*