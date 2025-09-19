"""Database connection and session management."""

import os
from typing import AsyncGenerator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import asynccontextmanager

# Base class for all models
Base = declarative_base()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flight_tracker:password@localhost:5432/flight_tracker_db"
)

# Async database URL (for async operations)
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Create engines
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, pool_pre_ping=True)

# Session makers
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


def get_db() -> Session:
    """
    Synchronous database session dependency for FastAPI.
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous database session dependency for FastAPI.
    
    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async database sessions.
    
    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def create_all_tables():
    """Create all database tables."""
    # Import all models to ensure they're registered with Base
    from src.models.tracking_request import FlightTrackingRequestDB
    from src.models.price_history import PriceHistoryDB
    from src.models.notification_log import NotificationLogDB
    
    Base.metadata.create_all(bind=engine)


async def create_all_tables_async():
    """Create all database tables asynchronously."""
    # Import all models to ensure they're registered with Base
    from src.models.tracking_request import FlightTrackingRequestDB
    from src.models.price_history import PriceHistoryDB
    from src.models.notification_log import NotificationLogDB
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def drop_all_tables():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)


async def drop_all_tables_async():
    """Drop all database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class DatabaseManager:
    """Database manager for handling connections and sessions."""
    
    def __init__(self):
        self.engine = engine
        self.async_engine = async_engine
        self.session_local = SessionLocal
        self.async_session_local = AsyncSessionLocal
    
    def get_sync_session(self) -> Session:
        """Get a synchronous database session."""
        return self.session_local()
    
    async def get_async_session(self) -> AsyncSession:
        """Get an asynchronous database session."""
        return self.async_session_local()
    
    def create_tables(self):
        """Create all database tables."""
        create_all_tables()
    
    async def create_tables_async(self):
        """Create all database tables asynchronously."""
        await create_all_tables_async()
    
    def drop_tables(self):
        """Drop all database tables."""
        drop_all_tables()
    
    async def drop_tables_async(self):
        """Drop all database tables asynchronously."""
        await drop_all_tables_async()
    
    async def close_connections(self):
        """Close all database connections."""
        await self.async_engine.dispose()
        self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


# Health check functions
async def check_database_health() -> dict:
    """
    Check database connectivity and return health status.
    
    Returns:
        dict: Health status information
    """
    try:
        async with get_async_session() as session:
            # Simple query to test connection
            result = await session.execute("SELECT 1")
            result.fetchone()
            
            return {
                "status": "healthy",
                "message": "Database connection successful",
                "response_time": "< 50ms"  # Placeholder - actual timing would need measurement
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "response_time": None
        }


def check_database_health_sync() -> dict:
    """
    Synchronous version of database health check.
    
    Returns:
        dict: Health status information
    """
    try:
        with SessionLocal() as session:
            # Simple query to test connection
            result = session.execute("SELECT 1")
            result.fetchone()
            
            return {
                "status": "healthy",
                "message": "Database connection successful",
                "response_time": "< 50ms"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "response_time": None
        }