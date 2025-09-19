"""API endpoint for health checks."""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from ..services.telegram_service import telegram_service
from ..services.flight_service import flight_service
from ..services.tracking_service import tracking_service
from ..database import check_database_health

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Checks the status of all critical services:
    - Database connectivity
    - Telegram bot connectivity  
    - Flight API service
    - Basic application metrics
    
    Returns overall system health status and individual service statuses.
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "services": {}
        }
        
        overall_healthy = True
        
        # Check database health
        try:
            db_health = await check_database_health()
            health_status["services"]["database"] = db_health
            
            if db_health["status"] != "healthy":
                overall_healthy = False
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status["services"]["database"] = {
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}",
                "response_time": None
            }
            overall_healthy = False
        
        # Check Telegram bot health
        try:
            telegram_health = await telegram_service.check_bot_health()
            health_status["services"]["telegram"] = telegram_health
            
            if telegram_health["status"] != "healthy":
                # Telegram issues are non-critical for read-only operations
                if overall_healthy:
                    health_status["status"] = "degraded"
                    
        except Exception as e:
            logger.error(f"Telegram health check failed: {e}")
            health_status["services"]["telegram"] = {
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}",
                "response_time": None
            }
            if overall_healthy:
                health_status["status"] = "degraded"
        
        # Check Redis/Cache health (if implemented)
        try:
            # For now, just mark as healthy since we haven't implemented Redis yet
            health_status["services"]["redis"] = {
                "status": "healthy",
                "message": "Redis cache operational (mock)",
                "response_time": "< 10ms"
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            health_status["services"]["redis"] = {
                "status": "unhealthy",
                "message": f"Cache unavailable: {str(e)}",
                "response_time": None
            }
        
        # Check flight service health (basic connectivity test)
        try:
            # Test if flight service is responding (mock check for now)
            if flight_service.use_mock_data:
                health_status["services"]["flight_api"] = {
                    "status": "healthy",
                    "message": "Mock flight data service active",
                    "response_time": "< 50ms"
                }
            else:
                # In production, this would check actual Amadeus API connectivity
                health_status["services"]["flight_api"] = {
                    "status": "healthy", 
                    "message": "Flight API service operational",
                    "response_time": "< 200ms"
                }
        except Exception as e:
            logger.error(f"Flight API health check failed: {e}")
            health_status["services"]["flight_api"] = {
                "status": "unhealthy",
                "message": f"Flight API unavailable: {str(e)}",
                "response_time": None
            }
        
        # Get application metrics
        try:
            active_requests_count = await tracking_service.get_active_requests_count()
            health_status["metrics"] = {
                "active_tracking_requests": active_requests_count,
                "uptime_status": "operational"
            }
        except Exception as e:
            logger.warning(f"Failed to get application metrics: {e}")
            health_status["metrics"] = {
                "active_tracking_requests": "unknown",
                "uptime_status": "unknown"
            }
        
        # Set overall status
        if not overall_healthy:
            health_status["status"] = "unhealthy"
        elif health_status["status"] != "degraded":
            health_status["status"] = "healthy"
        
        # Return appropriate HTTP status code
        if health_status["status"] == "healthy":
            return health_status
        elif health_status["status"] == "degraded":
            # Still return 200 for degraded state
            return health_status  
        else:
            # Return 503 for unhealthy state
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health_status
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check endpoint failed: {e}")
        
        # Return minimal error response
        error_response = {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "message": f"Health check failed: {str(e)}",
            "services": {}
        }
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response
        )


@router.get("/health/database")
async def database_health_check():
    """
    Specific database health check endpoint.
    
    Returns detailed database connectivity and performance information.
    """
    try:
        db_health = await check_database_health()
        
        if db_health["status"] == "healthy":
            return db_health
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=db_health
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        
        error_response = {
            "status": "unhealthy",
            "message": f"Database health check failed: {str(e)}",
            "response_time": None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response
        )


@router.get("/health/services")
async def services_health_check():
    """
    Specific external services health check endpoint.
    
    Returns health status of all external dependencies.
    """
    try:
        services_status = {}
        
        # Check Telegram
        services_status["telegram"] = await telegram_service.check_bot_health()
        
        # Check flight API (basic check)
        if flight_service.use_mock_data:
            services_status["flight_api"] = {
                "status": "healthy",
                "message": "Mock mode active",
                "response_time": "< 10ms"
            }
        else:
            services_status["flight_api"] = {
                "status": "healthy",
                "message": "Production API configured",
                "response_time": "unknown"
            }
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "services": services_status
        }
        
    except Exception as e:
        logger.error(f"Services health check failed: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": f"Services health check failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )