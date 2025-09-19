"""
Celery beat scheduler configuration.

This module configures the periodic task scheduling for the flight price
tracking system using Celery Beat.
"""

import logging
from datetime import timedelta
from celery.schedules import crontab

from .price_check import celery_app

logger = logging.getLogger(__name__)

# Celery Beat Schedule Configuration
celery_app.conf.beat_schedule = {
    # Price checking tasks
    'check-all-prices-every-hour': {
        'task': 'tasks.price_check.check_all_active_prices',
        'schedule': crontab(minute=0),  # Every hour at minute 0
        'options': {'queue': 'price_checks'}
    },
    
    'check-high-priority-prices': {
        'task': 'tasks.price_check.check_all_active_prices', 
        'schedule': timedelta(minutes=30),  # Every 30 minutes
        'options': {'queue': 'priority_price_checks'},
        'kwargs': {'priority_only': True}
    },
    
    # Cleanup and maintenance tasks
    'cleanup-expired-requests': {
        'task': 'tasks.price_check.cleanup_expired_requests',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM UTC
        'options': {'queue': 'maintenance'}
    },
    
    'send-expiry-warnings': {
        'task': 'tasks.scheduler.send_expiry_warnings',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10 AM UTC
        'options': {'queue': 'notifications'}
    },
    
    # System health and monitoring
    'system-health-check': {
        'task': 'tasks.scheduler.system_health_check',
        'schedule': timedelta(minutes=15),  # Every 15 minutes
        'options': {'queue': 'monitoring'}
    },
    
    'generate-daily-stats': {
        'task': 'tasks.scheduler.generate_daily_stats',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM UTC
        'options': {'queue': 'reporting'}
    }
}

# Queue Configuration
celery_app.conf.task_routes = {
    'tasks.price_check.*': {'queue': 'price_checks'},
    'tasks.notifications.*': {'queue': 'notifications'},
    'tasks.scheduler.*': {'queue': 'maintenance'},
}

# Additional Celery configuration for scheduling
celery_app.conf.update(
    # Timezone settings
    timezone='UTC',
    enable_utc=True,
    
    # Task execution settings
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Beat settings
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler' if False else 'celery.beat:PersistentScheduler',
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    
    # Task routing
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
    
    # Queue definitions
    task_queues={
        'default': {
            'exchange': 'default',
            'routing_key': 'default',
        },
        'price_checks': {
            'exchange': 'price_checks',
            'routing_key': 'price_checks',
        },
        'priority_price_checks': {
            'exchange': 'priority',
            'routing_key': 'priority',
        },
        'notifications': {
            'exchange': 'notifications',
            'routing_key': 'notifications',
        },
        'maintenance': {
            'exchange': 'maintenance', 
            'routing_key': 'maintenance',
        },
        'monitoring': {
            'exchange': 'monitoring',
            'routing_key': 'monitoring',
        },
        'reporting': {
            'exchange': 'reporting',
            'routing_key': 'reporting',
        }
    }
)


@celery_app.task
def send_expiry_warnings() -> dict:
    """
    Send expiry warnings for requests that will expire soon.
    
    This task runs daily to notify users about tracking requests
    that will expire within the next 2 days.
    
    Returns:
        dict: Summary of warnings sent
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from database import get_db
        from models.tracking_request import FlightTrackingRequestDB
        from .notifications import send_expiry_warning_notification
        
        logger.info("Starting expiry warning batch job")
        
        # Calculate the warning threshold (2 days from now)
        warning_threshold = datetime.utcnow() + timedelta(days=2)
        
        with Session(get_db()) as db:
            # Find requests that will expire soon
            expiring_requests = db.execute(
                select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.is_active == True,
                    FlightTrackingRequestDB.expires_at <= warning_threshold,
                    FlightTrackingRequestDB.expires_at > datetime.utcnow()
                )
            ).scalars().all()
            
            if not expiring_requests:
                logger.info("No requests expiring soon")
                return {"status": "no_expiring", "warnings_sent": 0}
            
            warnings_sent = 0
            for request in expiring_requests:
                try:
                    # Send expiry warning
                    send_expiry_warning_notification.delay(
                        chat_id=request.telegram_chat_id,
                        request_id=str(request.id),
                        expires_at=request.expires_at
                    )
                    warnings_sent += 1
                except Exception as e:
                    logger.error(f"Failed to send expiry warning for {request.id}: {e}")
            
            return {
                "status": "success",
                "warnings_sent": warnings_sent,
                "total_expiring": len(expiring_requests)
            }
            
    except Exception as exc:
        logger.error(f"Error in expiry warnings task: {exc}")
        raise


@celery_app.task
def system_health_check() -> dict:
    """
    Perform system health checks.
    
    Monitors system components and sends alerts if issues are detected.
    
    Returns:
        dict: Health check results
    """
    try:
        from datetime import datetime
        from database import get_async_session
        from services.flight_service import flight_service
        from services.telegram_service import telegram_service
        
        logger.info("Starting system health check")
        
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": "unknown",
            "flight_api": "unknown", 
            "telegram_api": "unknown",
            "overall": "unknown"
        }
        
        # Check database connectivity
        try:
            import asyncio
            
            async def check_db():
                async with get_async_session() as db:
                    # Simple query to test connection
                    await db.execute("SELECT 1")
                    return True
            
            # Run async code in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(check_db())
                health_status["database"] = "healthy"
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status["database"] = "unhealthy"
        
        # Check flight API (basic connectivity test)
        try:
            # This should be a lightweight API test call
            flight_service.test_connection()
            health_status["flight_api"] = "healthy"
        except Exception as e:
            logger.warning(f"Flight API health check failed: {e}")
            health_status["flight_api"] = "degraded"
        
        # Check Telegram API
        try:
            telegram_service.test_connection()
            health_status["telegram_api"] = "healthy"
        except Exception as e:
            logger.warning(f"Telegram API health check failed: {e}")
            health_status["telegram_api"] = "degraded"
        
        # Determine overall health
        if all(status == "healthy" for status in [health_status["database"], health_status["flight_api"], health_status["telegram_api"]]):
            health_status["overall"] = "healthy"
        elif health_status["database"] == "unhealthy":
            health_status["overall"] = "critical"
        else:
            health_status["overall"] = "degraded"
        
        # Log critical issues
        if health_status["overall"] == "critical":
            logger.critical(f"System health critical: {health_status}")
        elif health_status["overall"] == "degraded":
            logger.warning(f"System health degraded: {health_status}")
        
        return health_status
        
    except Exception as exc:
        logger.error(f"Error in system health check: {exc}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall": "error",
            "error": str(exc)
        }


@celery_app.task
def generate_daily_stats() -> dict:
    """
    Generate daily statistics and metrics.
    
    Compiles usage statistics, performance metrics, and system health
    data for monitoring and reporting.
    
    Returns:
        dict: Daily statistics summary
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import select, func
        from sqlalchemy.orm import Session
        from database import get_db
        from models.tracking_request import FlightTrackingRequestDB
        from models.price_history import PriceHistoryDB
        from models.notification_log import NotificationLogDB
        
        logger.info("Generating daily statistics")
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        today = datetime.utcnow()
        
        stats = {
            "date": yesterday.strftime("%Y-%m-%d"),
            "generated_at": today.isoformat()
        }
        
        with Session(get_db()) as db:
            # Active tracking requests
            active_requests = db.execute(
                select(func.count(FlightTrackingRequestDB.id)).where(
                    FlightTrackingRequestDB.is_active == True
                )
            ).scalar()
            stats["active_requests"] = active_requests
            
            # New requests created yesterday
            new_requests = db.execute(
                select(func.count(FlightTrackingRequestDB.id)).where(
                    FlightTrackingRequestDB.created_at >= yesterday,
                    FlightTrackingRequestDB.created_at < today
                )
            ).scalar()
            stats["new_requests_yesterday"] = new_requests
            
            # Price checks performed yesterday
            price_checks = db.execute(
                select(func.count(PriceHistoryDB.id)).where(
                    PriceHistoryDB.checked_at >= yesterday,
                    PriceHistoryDB.checked_at < today
                )
            ).scalar()
            stats["price_checks_yesterday"] = price_checks
            
            # Notifications sent yesterday
            notifications_sent = db.execute(
                select(func.count(NotificationLogDB.id)).where(
                    NotificationLogDB.sent_at >= yesterday,
                    NotificationLogDB.sent_at < today,
                    NotificationLogDB.status == 'sent'
                )
            ).scalar()
            stats["notifications_sent_yesterday"] = notifications_sent
            
        logger.info(f"Daily stats: {stats}")
        return stats
        
    except Exception as exc:
        logger.error(f"Error generating daily stats: {exc}")
        raise


if __name__ == "__main__":
    # For debugging - print the current schedule
    print("Celery Beat Schedule:")
    for task_name, config in celery_app.conf.beat_schedule.items():
        print(f"  {task_name}: {config['schedule']} -> {config['task']}")