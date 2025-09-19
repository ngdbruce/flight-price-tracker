"""FastAPI main application."""

import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.app.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import API routers with absolute imports for testing compatibility
try:
    from .api.tracking import router as tracking_router
    from .api.flights import router as flights_router  
    from .api.health import router as health_router
    from .api.docs import setup_openapi_documentation, custom_openapi_generator
    from .database import create_all_tables_async, db_manager
    from .cache import cache_manager
    from .middleware import ErrorHandlingMiddleware, AdvancedRateLimitMiddleware
except ImportError:
    # Fallback to absolute imports when run directly
    from api.tracking import router as tracking_router
    from api.flights import router as flights_router  
    from api.health import router as health_router
    from api.docs import setup_openapi_documentation, custom_openapi_generator
    from database import create_all_tables_async, db_manager
    from cache import cache_manager
    from middleware import ErrorHandlingMiddleware, AdvancedRateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Flight Price Tracking API...")
    
    try:
        # Create database tables
        await create_all_tables_async()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Continue anyway for development
    
    try:
        # Initialize cache connection
        await cache_manager.connect()
        logger.info("Cache manager connected")
    except Exception as e:
        logger.error(f"Failed to initialize cache: {e}")
        # Continue anyway for development
    
    yield
    
    # Shutdown
    logger.info("Shutting down Flight Price Tracking API...")
    try:
        await db_manager.close_connections()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    try:
        await cache_manager.disconnect()
        logger.info("Cache manager disconnected")
    except Exception as e:
        logger.error(f"Error closing cache connections: {e}")


# Create FastAPI application
app = FastAPI(
    title="Flight Price Tracking API",
    description="API for tracking flight prices and sending Telegram notifications",
    version="1.0.0",
    docs_url="/docs" if settings.app.is_development else None,
    redoc_url="/redoc" if settings.app.is_development else None,
    debug=settings.app.debug,
    lifespan=lifespan
)

# Setup comprehensive OpenAPI documentation
setup_openapi_documentation(app)
app.openapi = lambda: custom_openapi_generator(app)

# Custom middleware (order matters - last added runs first)
# Error handling middleware (should be first to catch all errors)
app.add_middleware(ErrorHandlingMiddleware)

# Rate limiting middleware
app.add_middleware(AdvancedRateLimitMiddleware)

# Security middleware - Trusted hosts  
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=settings.app.allowed_hosts
)

# CORS middleware (T050)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests."""
    start_time = time.time()
    
    # Log request
    logger.info(f"{request.method} {request.url.path} - Start")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s"
    )
    
    return response

# Include API routers
app.include_router(tracking_router, prefix="/api/v1/tracking", tags=["tracking"])
app.include_router(flights_router, prefix="/api/v1/flights", tags=["flights"])
app.include_router(health_router, tags=["health"])

# Static files serving (T053)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "src")), name="static")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.get("/api")
async def api_root():
    """API root endpoint."""
    return {
        "message": "Flight Price Tracking API",
        "version": "1.0.0",
        "docs": "/docs" if settings.app.is_development else None,
        "health": "/api/v1/health",
        "endpoints": {
            "tracking": "/api/v1/tracking",
            "flights": "/api/v1/flights"
        }
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    
    if settings.app.is_development:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=settings.app.is_development,
        log_level=settings.app.log_level.lower()
    )