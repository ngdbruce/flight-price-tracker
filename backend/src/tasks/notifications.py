"""
Celery task for sending notifications.

This module contains background tasks for sending various types of notifications
to users via Telegram, including price alerts, system updates, and error notifications.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal

from celery import Celery
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.tracking_request import FlightTrackingRequestDB
from src.models.notification_log import NotificationLogDB, NotificationType, NotificationStatus
from src.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)

# Import celery app from price_check to use the same instance
from .price_check import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_price_alert_notification(
    self,
    chat_id: int,
    request_id: str,
    old_price: float,
    new_price: float,
    change_percentage: float,
    flight_details: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Send price alert notification to user.
    
    Args:
        chat_id: Telegram chat ID
        request_id: Tracking request UUID
        old_price: Previous price
        new_price: Current price
        change_percentage: Percentage change (positive = increase, negative = decrease)
        flight_details: Optional flight information
        
    Returns:
        dict: Result of notification sending
    """
    try:
        logger.info(f"Sending price alert to chat {chat_id} for request {request_id}")
        
        # Determine notification type based on price change
        if change_percentage < 0:
            notification_type = NotificationType.PRICE_CHANGE  # Price drop
            emoji = "📉"
            action = "dropped"
        else:
            notification_type = NotificationType.PRICE_CHANGE  # Price increase
            emoji = "📈"
            action = "increased"
        
        # Format price change message
        old_price_str = f"${old_price:.2f}"
        new_price_str = f"${new_price:.2f}"
        change_str = f"{abs(change_percentage):.1f}%"
        
        message = f"{emoji} **Price Alert!**\n\n"
        message += f"Your flight price has {action} by {change_str}\n"
        message += f"Previous price: {old_price_str}\n"
        message += f"Current price: {new_price_str}\n\n"
        
        if flight_details:
            message += f"✈️ Flight: {flight_details.get('airline', 'N/A')} {flight_details.get('flight_number', '')}\n"
            message += f"🛫 Route: {flight_details.get('origin', 'N/A')} → {flight_details.get('destination', 'N/A')}\n"
            message += f"📅 Date: {flight_details.get('departure_date', 'N/A')}\n"
            
            if flight_details.get('booking_url'):
                message += f"\n🔗 [Book Now]({flight_details['booking_url']})"
        
        message += f"\n\n📝 Request ID: `{request_id}`"
        
        # Send notification via Telegram
        success = telegram_service.send_message(
            chat_id=chat_id,
            message=message,
            parse_mode="Markdown"
        )
        
        # Log the notification attempt
        with Session(get_db()) as db:
            log_entry = NotificationLogDB(
                tracking_request_id=request_id,
                notification_type=notification_type,
                message=message,
                price=Decimal(str(new_price)),
                status=NotificationStatus.SENT if success else NotificationStatus.FAILED,
                telegram_chat_id=chat_id,
                sent_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        
        if success:
            logger.info(f"Price alert sent successfully to chat {chat_id}")
            return {
                "status": "sent",
                "chat_id": chat_id,
                "request_id": request_id,
                "message_preview": message[:100] + "..."
            }
        else:
            logger.error(f"Failed to send price alert to chat {chat_id}")
            return {"status": "failed", "chat_id": chat_id, "request_id": request_id}
            
    except Exception as exc:
        logger.error(f"Error sending price alert: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_tracking_started_notification(
    self,
    chat_id: int,
    request_id: str,
    tracking_details: Dict[str, Any]
) -> dict:
    """
    Send notification when tracking starts.
    
    Args:
        chat_id: Telegram chat ID
        request_id: Tracking request UUID  
        tracking_details: Details about the tracking request
        
    Returns:
        dict: Result of notification sending
    """
    try:
        logger.info(f"Sending tracking started notification to chat {chat_id}")
        
        message = "🎯 **Flight Tracking Started!**\n\n"
        message += f"✅ We're now monitoring prices for your flight:\n\n"
        message += f"🛫 Route: {tracking_details.get('origin_iata', 'N/A')} → {tracking_details.get('destination_iata', 'N/A')}\n"
        message += f"📅 Departure: {tracking_details.get('departure_date', 'N/A')}\n"
        
        if tracking_details.get('return_date'):
            message += f"🔄 Return: {tracking_details['return_date']}\n"
        
        if tracking_details.get('baseline_price'):
            message += f"💰 Starting price: ${tracking_details['baseline_price']:.2f}\n"
        
        message += f"\n⚡ You'll receive alerts when prices change significantly\n"
        message += f"📝 Request ID: `{request_id}`"
        
        success = telegram_service.send_message(
            chat_id=chat_id,
            message=message,
            parse_mode="Markdown"
        )
        
        # Log the notification
        with Session(get_db()) as db:
            log_entry = NotificationLogDB(
                tracking_request_id=request_id,
                notification_type=NotificationType.TRACKING_STARTED,
                message=message,
                status=NotificationStatus.SENT if success else NotificationStatus.FAILED,
                telegram_chat_id=chat_id,
                sent_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        
        return {
            "status": "sent" if success else "failed",
            "chat_id": chat_id,
            "request_id": request_id
        }
        
    except Exception as exc:
        logger.error(f"Error sending tracking started notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_tracking_stopped_notification(
    self,
    chat_id: int,
    request_id: str,
    reason: str = "User requested"
) -> dict:
    """
    Send notification when tracking stops.
    
    Args:
        chat_id: Telegram chat ID
        request_id: Tracking request UUID
        reason: Reason for stopping tracking
        
    Returns:
        dict: Result of notification sending
    """
    try:
        logger.info(f"Sending tracking stopped notification to chat {chat_id}")
        
        message = "⏹️ **Flight Tracking Stopped**\n\n"
        message += f"We've stopped monitoring prices for your flight.\n\n"
        message += f"📝 Request ID: `{request_id}`\n"
        message += f"🔄 Reason: {reason}\n\n"
        message += f"Thank you for using our flight tracking service! ✈️"
        
        success = telegram_service.send_message(
            chat_id=chat_id,
            message=message,
            parse_mode="Markdown"
        )
        
        # Log the notification
        with Session(get_db()) as db:
            log_entry = NotificationLogDB(
                tracking_request_id=request_id,
                notification_type=NotificationType.TRACKING_STOPPED,
                message=message,
                status=NotificationStatus.SENT if success else NotificationStatus.FAILED,
                telegram_chat_id=chat_id,
                sent_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        
        return {
            "status": "sent" if success else "failed",
            "chat_id": chat_id,
            "request_id": request_id
        }
        
    except Exception as exc:
        logger.error(f"Error sending tracking stopped notification: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=1)
def send_expiry_warning_notification(
    self,
    chat_id: int,
    request_id: str,
    expires_at: datetime
) -> dict:
    """
    Send warning notification before tracking expires.
    
    Args:
        chat_id: Telegram chat ID
        request_id: Tracking request UUID
        expires_at: When the tracking will expire
        
    Returns:
        dict: Result of notification sending
    """
    try:
        logger.info(f"Sending expiry warning to chat {chat_id}")
        
        time_until_expiry = expires_at - datetime.utcnow()
        days_left = time_until_expiry.days
        
        message = "⚠️ **Tracking Expiry Warning**\n\n"
        message += f"Your flight price tracking will expire in {days_left} day(s).\n\n"
        message += f"📝 Request ID: `{request_id}`\n"
        message += f"⏰ Expires: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        message += f"If you'd like to extend tracking, please create a new request."
        
        success = telegram_service.send_message(
            chat_id=chat_id,
            message=message,
            parse_mode="Markdown"
        )
        
        # Log the notification
        with Session(get_db()) as db:
            log_entry = NotificationLogDB(
                tracking_request_id=request_id,
                notification_type=NotificationType.EXPIRY_WARNING,
                message=message,
                status=NotificationStatus.SENT if success else NotificationStatus.FAILED,
                telegram_chat_id=chat_id,
                sent_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        
        return {
            "status": "sent" if success else "failed",
            "chat_id": chat_id,
            "request_id": request_id
        }
        
    except Exception as exc:
        logger.error(f"Error sending expiry warning: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task
def send_bulk_notifications(notification_requests: List[Dict[str, Any]]) -> dict:
    """
    Send multiple notifications in batch.
    
    Args:
        notification_requests: List of notification request dictionaries
        
    Returns:
        dict: Summary of batch processing results
    """
    try:
        logger.info(f"Processing bulk notifications: {len(notification_requests)} requests")
        
        results = {
            "total": len(notification_requests),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for request in notification_requests:
            try:
                notification_type = request.get("type")
                
                if notification_type == "price_alert":
                    task = send_price_alert_notification.delay(
                        chat_id=request["chat_id"],
                        request_id=request["request_id"],
                        old_price=request["old_price"],
                        new_price=request["new_price"],
                        change_percentage=request["change_percentage"],
                        flight_details=request.get("flight_details")
                    )
                elif notification_type == "tracking_started":
                    task = send_tracking_started_notification.delay(
                        chat_id=request["chat_id"],
                        request_id=request["request_id"],
                        tracking_details=request["tracking_details"]
                    )
                elif notification_type == "tracking_stopped":
                    task = send_tracking_stopped_notification.delay(
                        chat_id=request["chat_id"],
                        request_id=request["request_id"],
                        reason=request.get("reason", "User requested")
                    )
                elif notification_type == "expiry_warning":
                    task = send_expiry_warning_notification.delay(
                        chat_id=request["chat_id"],
                        request_id=request["request_id"],
                        expires_at=request["expires_at"]
                    )
                else:
                    raise ValueError(f"Unknown notification type: {notification_type}")
                
                results["successful"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
                logger.error(f"Failed to send notification: {e}")
        
        return results
        
    except Exception as exc:
        logger.error(f"Error in bulk notification processing: {exc}")
        raise