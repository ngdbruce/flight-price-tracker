"""
Celery task for price checking.

This module contains the background task that periodically checks flight prices
for active tracking requests and updates price history.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from decimal import Decimal

from celery import Celery
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db, get_async_session
from src.models.tracking_request import FlightTrackingRequestDB
from src.models.price_history import PriceHistoryDB
from src.services.flight_service import flight_service
from src.services.price_monitoring_service import price_monitoring_service
from src.services.telegram_service import telegram_service
from src.config import Settings

logger = logging.getLogger(__name__)

# Get settings
settings = Settings()

# Initialize Celery app
celery_app = Celery(
    "flight_tracker",
    broker=settings.redis.url,
    backend=settings.redis.url
)

# Celery configuration
celery_app.conf.update(
    timezone='UTC',
    enable_utc=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def check_prices_for_request(self, request_id: str) -> dict:
    """
    Check price for a single tracking request.
    
    Args:
        request_id: UUID of the tracking request
        
    Returns:
        dict: Result summary with price info and actions taken
    """
    try:
        logger.info(f"Checking price for request {request_id}")
        
        with Session(get_db()) as db:
            # Get the tracking request
            request = db.get(FlightTrackingRequestDB, request_id)
            if not request:
                logger.warning(f"Request {request_id} not found")
                return {"status": "not_found", "request_id": request_id}
                
            if not request.is_active:
                logger.info(f"Request {request_id} is inactive, skipping")
                return {"status": "inactive", "request_id": request_id}
                
            if request.expires_at < datetime.utcnow():
                logger.info(f"Request {request_id} has expired, marking inactive")
                request.is_active = False
                db.commit()
                return {"status": "expired", "request_id": request_id}
            
            # Get current flight price
            flight_data = flight_service.search_flights(
                origin_iata=request.origin_iata,
                destination_iata=request.destination_iata,
                departure_date=request.departure_date,
                return_date=request.return_date
            )
            
            if not flight_data or not flight_data.get("flights"):
                logger.warning(f"No flight data found for request {request_id}")
                return {"status": "no_flights", "request_id": request_id}
            
            # Get the best (cheapest) price
            best_flight = min(flight_data["flights"], key=lambda f: f["total_price"])
            current_price = Decimal(str(best_flight["total_price"]))
            
            # Store price in history
            price_entry = PriceHistoryDB(
                tracking_request_id=request_id,
                price=current_price,
                currency=best_flight.get("currency", "USD"),
                source_data=best_flight,
                checked_at=datetime.utcnow()
            )
            db.add(price_entry)
            
            # Check for significant price changes
            price_change_info = price_monitoring_service.analyze_price_change(
                request_id=request_id,
                new_price=current_price,
                baseline_price=request.baseline_price
            )
            
            # Update request with current price
            request.current_price = current_price
            request.updated_at = datetime.utcnow()
            
            # If significant change detected, trigger notification
            notifications_sent = []
            if price_change_info["should_notify"]:
                notification_sent = telegram_service.send_price_alert(
                    chat_id=request.telegram_chat_id,
                    request_id=request_id,
                    old_price=price_change_info["previous_price"],
                    new_price=current_price,
                    change_percentage=price_change_info["change_percentage"]
                )
                if notification_sent:
                    notifications_sent.append("price_alert")
            
            db.commit()
            
            return {
                "status": "success",
                "request_id": request_id,
                "current_price": float(current_price),
                "price_change": price_change_info,
                "notifications_sent": notifications_sent
            }
            
    except Exception as exc:
        logger.error(f"Error checking price for request {request_id}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task
def check_all_active_prices() -> dict:
    """
    Check prices for all active tracking requests.
    
    This is the main scheduled task that runs periodically to check
    prices for all active requests.
    
    Returns:
        dict: Summary of processing results
    """
    try:
        logger.info("Starting batch price check for all active requests")
        
        with Session(get_db()) as db:
            # Get all active requests that haven't expired
            active_requests = db.execute(
                select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.is_active == True,
                    FlightTrackingRequestDB.expires_at > datetime.utcnow()
                )
            ).scalars().all()
            
            if not active_requests:
                logger.info("No active requests found")
                return {"status": "no_active_requests", "processed": 0}
            
            logger.info(f"Found {len(active_requests)} active requests to process")
            
            # Process each request asynchronously
            task_results = []
            for request in active_requests:
                # Schedule individual price check task
                task = check_prices_for_request.delay(str(request.id))
                task_results.append({
                    "request_id": str(request.id),
                    "task_id": task.id
                })
            
            return {
                "status": "scheduled",
                "processed": len(active_requests),
                "tasks": task_results
            }
            
    except Exception as exc:
        logger.error(f"Error in batch price check: {exc}")
        raise


@celery_app.task
def cleanup_expired_requests() -> dict:
    """
    Clean up expired tracking requests.
    
    Marks expired requests as inactive and sends expiry notifications
    if configured.
    
    Returns:
        dict: Summary of cleanup results
    """
    try:
        logger.info("Starting cleanup of expired requests")
        
        with Session(get_db()) as db:
            # Find expired but still active requests
            expired_requests = db.execute(
                select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.is_active == True,
                    FlightTrackingRequestDB.expires_at <= datetime.utcnow()
                )
            ).scalars().all()
            
            if not expired_requests:
                logger.info("No expired requests found")
                return {"status": "no_expired", "cleaned": 0}
            
            logger.info(f"Found {len(expired_requests)} expired requests")
            
            cleaned_count = 0
            for request in expired_requests:
                # Mark as inactive
                request.is_active = False
                request.updated_at = datetime.utcnow()
                
                # Optionally send expiry notification
                try:
                    telegram_service.send_expiry_notification(
                        chat_id=request.telegram_chat_id,
                        request_id=str(request.id)
                    )
                except Exception as e:
                    logger.warning(f"Failed to send expiry notification for {request.id}: {e}")
                
                cleaned_count += 1
            
            db.commit()
            
            return {
                "status": "success",
                "cleaned": cleaned_count
            }
            
    except Exception as exc:
        logger.error(f"Error in cleanup task: {exc}")
        raise


# Task routing and periodic scheduling will be configured in scheduler.py