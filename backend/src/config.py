"""Configuration management for Flight Price Tracker."""

import os
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings:
    """Database configuration."""

    def __init__(self, url: str, echo_queries: bool = False, pool_size: int = 5, max_overflow: int = 10):
        self.url = url
        self.echo_queries = echo_queries
        self.pool_size = pool_size
        self.max_overflow = max_overflow


class RedisSettings:
    """Redis configuration."""

    def __init__(self, url: str, max_connections: int = 20):
        self.url = url
        self.max_connections = max_connections


class TelegramSettings:
    """Telegram Bot configuration."""

    def __init__(self, bot_token: str, api_timeout: int = 30, max_retries: int = 3):
        self.bot_token = bot_token
        self.api_timeout = api_timeout
        self.max_retries = max_retries


class AmadeusSettings:
    """Amadeus Flight API configuration."""

    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://test.api.amadeus.com", timeout: int = 30):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.timeout = timeout


class AppSettings:
    """Application configuration."""

    def __init__(self, environment: str = "development", debug: bool = False, log_level: str = "INFO", 
                 secret_key: str = None, api_rate_limit: int = 100, 
                 price_check_interval_minutes: int = 120, max_tracking_requests_per_user: int = 10,
                 cache_ttl_minutes: int = 15, allowed_hosts: List[str] = None,
                 price_change_threshold_percent: float = 5.0, max_notifications_per_day: int = 50,
                 cors_origins: List[str] = None, enable_metrics: bool = True,
                 metrics_port: int = 9090, sentry_dsn: str = None,
                 use_mock_flight_data: bool = False):
        self.environment = environment
        self.debug = debug
        self.log_level = log_level
        self.secret_key = secret_key
        self.api_rate_limit = api_rate_limit
        self.price_check_interval_minutes = price_check_interval_minutes
        self.max_tracking_requests_per_user = max_tracking_requests_per_user
        self.cache_ttl_minutes = cache_ttl_minutes
        self.allowed_hosts = allowed_hosts or ["localhost", "127.0.0.1", "*"]
        self.price_change_threshold_percent = price_change_threshold_percent
        self.max_notifications_per_day = max_notifications_per_day
        self.cors_origins = cors_origins or ["http://localhost:3000"]
        self.enable_metrics = enable_metrics
        self.metrics_port = metrics_port
        self.sentry_dsn = sentry_dsn
        self.use_mock_flight_data = use_mock_flight_data

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"


class Settings(BaseSettings):
    """Main settings container."""

    # Database configuration
    database_url: str = Field(..., env="DATABASE_URL")
    database_echo: bool = Field(False, env="DATABASE_ECHO")
    database_pool_size: int = Field(5, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(10, env="DATABASE_MAX_OVERFLOW")

    # Redis configuration
    redis_url: str = Field(..., env="REDIS_URL")
    redis_max_connections: int = Field(20, env="REDIS_MAX_CONNECTIONS")

    # Telegram configuration
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_api_timeout: int = Field(30, env="TELEGRAM_API_TIMEOUT")
    telegram_max_retries: int = Field(3, env="TELEGRAM_MAX_RETRIES")

    # Amadeus configuration
    amadeus_api_key: str = Field(..., env="AMADEUS_API_KEY")
    amadeus_api_secret: str = Field(..., env="AMADEUS_API_SECRET")
    amadeus_base_url: str = Field("https://test.api.amadeus.com", env="AMADEUS_BASE_URL")
    amadeus_timeout: int = Field(30, env="AMADEUS_TIMEOUT")

    # Application configuration
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    secret_key: str = Field(..., env="SECRET_KEY")
    api_rate_limit: int = Field(100, env="API_RATE_LIMIT")
    price_check_interval_minutes: int = Field(120, env="PRICE_CHECK_INTERVAL_MINUTES")
    max_tracking_requests_per_user: int = Field(10, env="MAX_TRACKING_REQUESTS_PER_USER")
    cache_ttl_minutes: int = Field(15, env="CACHE_TTL_MINUTES")
    allowed_hosts: List[str] = Field(default=["localhost", "127.0.0.1", "*"], env="ALLOWED_HOSTS")
    
    # Notification settings
    price_change_threshold_percent: float = Field(5.0, env="PRICE_CHANGE_THRESHOLD_PERCENT")
    max_notifications_per_day: int = Field(50, env="MAX_NOTIFICATIONS_PER_DAY")
    
    # Security settings
    cors_origins: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    
    # Monitoring
    enable_metrics: bool = Field(True, env="ENABLE_METRICS")
    metrics_port: int = Field(9090, env="METRICS_PORT")
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    
    # Testing
    use_mock_flight_data: bool = Field(False, env="USE_MOCK_FLIGHT_DATA")

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"

    @property
    def database(self) -> DatabaseSettings:
        """Get database settings."""
        return DatabaseSettings(
            url=self.database_url,
            echo_queries=self.database_echo,
            pool_size=self.database_pool_size,
            max_overflow=self.database_max_overflow
        )

    @property
    def redis(self) -> RedisSettings:
        """Get Redis settings."""
        return RedisSettings(
            url=self.redis_url,
            max_connections=self.redis_max_connections
        )

    @property
    def telegram(self) -> TelegramSettings:
        """Get Telegram settings."""
        return TelegramSettings(
            bot_token=self.telegram_bot_token,
            api_timeout=self.telegram_api_timeout,
            max_retries=self.telegram_max_retries
        )

    @property
    def amadeus(self) -> AmadeusSettings:
        """Get Amadeus settings."""
        return AmadeusSettings(
            api_key=self.amadeus_api_key,
            api_secret=self.amadeus_api_secret,
            base_url=self.amadeus_base_url,
            timeout=self.amadeus_timeout
        )

    @property
    def app(self) -> AppSettings:
        """Get app settings."""
        return AppSettings(
            environment=self.environment,
            debug=self.debug,
            log_level=self.log_level,
            secret_key=self.secret_key,
            api_rate_limit=self.api_rate_limit,
            price_check_interval_minutes=self.price_check_interval_minutes,
            max_tracking_requests_per_user=self.max_tracking_requests_per_user,
            cache_ttl_minutes=self.cache_ttl_minutes,
            allowed_hosts=self.allowed_hosts,
            price_change_threshold_percent=self.price_change_threshold_percent,
            max_notifications_per_day=self.max_notifications_per_day,
            cors_origins=self.cors_origins,
            enable_metrics=self.enable_metrics,
            metrics_port=self.metrics_port,
            sentry_dsn=self.sentry_dsn,
            use_mock_flight_data=self.use_mock_flight_data
        )


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()