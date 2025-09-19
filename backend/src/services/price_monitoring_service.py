"""Price monitoring service with change detection."""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.models.tracking_request import FlightTrackingRequestDB
from src.models.price_history import PriceHistoryDB
from src.models.notification_log import NotificationLogDB, NotificationType, NotificationStatus
from src.services.flight_service import flight_service, FlightSearchParams
from src.services.telegram_service import telegram_service, NotificationContext, MessageType
from src.database import get_async_session

logger = logging.getLogger(__name__)


class PriceMonitoringService:
    """Service for monitoring flight prices and detecting changes."""
    
    def __init__(self):
        self.price_change_threshold = Decimal("5.0")  # Default 5% threshold
    
    async def check_all_active_requests(self) -> Dict[str, int]:
        """
        Check prices for all active tracking requests.
        
        Returns:
            Dictionary with summary statistics
        """
        stats = {
            "total_checked": 0,
            "price_changes": 0,
            "notifications_sent": 0,
            "errors": 0
        }
        
        async with get_async_session() as session:
            # Get all active tracking requests that haven't expired
            query = select(FlightTrackingRequestDB).where(
                FlightTrackingRequestDB.is_active == True,
                FlightTrackingRequestDB.expires_at > datetime.utcnow()
            ).options(selectinload(FlightTrackingRequestDB.price_history))
            
            result = await session.execute(query)
            active_requests = result.scalars().all()
            
            logger.info(f"Found {len(active_requests)} active tracking requests")
            
            for request in active_requests:
                try:
                    await self.check_single_request(session, request)
                    stats["total_checked"] += 1
                except Exception as e:
                    logger.error(f"Error checking request {request.id}: {e}")
                    stats["errors"] += 1
                    
                    # Send error notification
                    try:
                        await self._send_error_notification(request, str(e))
                    except Exception as notification_error:
                        logger.error(f"Failed to send error notification: {notification_error}")
            
            await session.commit()
        
        return stats
    
    async def check_single_request(self, session: AsyncSession, request: FlightTrackingRequestDB) -> Optional[Decimal]:
        """
        Check price for a single tracking request.
        
        Args:
            session: Database session
            request: Tracking request to check
            
        Returns:
            New price if found, None otherwise
        """
        try:
            logger.info(f"Checking price for request {request.id} ({request.origin_iata} → {request.destination_iata})")
            
            # Get current price from flight API
            new_price = await flight_service.get_current_price(
                origin=request.origin_iata,
                destination=request.destination_iata,
                departure_date=request.departure_date,
                return_date=request.return_date
            )
            
            if new_price is None:
                logger.warning(f"No price found for request {request.id}")
                return None
            
            # Record price in history
            price_history = PriceHistoryDB(
                tracking_request_id=request.id,
                price=new_price,
                currency=request.currency,
                checked_at=datetime.utcnow()
            )
            session.add(price_history)
            
            # Check if this is the first price (baseline)
            if request.baseline_price is None:
                request.baseline_price = new_price
                request.current_price = new_price
                
                # Send tracking started notification
                await self._send_tracking_started_notification(request)
                
                logger.info(f"Set baseline price {new_price} for request {request.id}")
            else:
                # Check for significant price change
                old_price = request.current_price
                price_change = await self._detect_price_change(old_price, new_price, request.price_threshold)
                
                if price_change:
                    # Update current price
                    request.current_price = new_price
                    request.updated_at = datetime.utcnow()
                    
                    # Send price change notification
                    await self._send_price_change_notification(request, old_price, new_price)
                    
                    logger.info(f"Price change detected for request {request.id}: {old_price} → {new_price}")
                else:
                    # Update current price and timestamp even if no significant change
                    request.current_price = new_price
                    request.updated_at = datetime.utcnow()
            
            return new_price
            
        except Exception as e:
            logger.error(f"Error checking price for request {request.id}: {e}")
            raise
    
    async def _detect_price_change(self, old_price: Decimal, new_price: Decimal, threshold: Decimal) -> bool:
        """
        Detect if price change is significant enough to notify.
        
        Args:
            old_price: Previous price
            new_price: Current price
            threshold: Percentage threshold for notification
            
        Returns:
            True if change is significant
        """
        if old_price == new_price:
            return False
        
        percentage_change = abs((new_price - old_price) / old_price * 100)
        return percentage_change >= threshold
    
    async def _send_tracking_started_notification(self, request: FlightTrackingRequestDB):
        """Send notification that tracking has started."""
        try:
            context = NotificationContext(
                origin=request.origin_iata,
                destination=request.destination_iata,
                departure_date=request.departure_date.isoformat(),
                return_date=request.return_date.isoformat() if request.return_date else None,
                currency=request.currency,
                tracking_id=str(request.id)
            )
            
            result = await telegram_service.send_tracking_started_notification(
                chat_id=request.telegram_chat_id,
                context=context
            )
            
            # Log notification
            await self._log_notification(
                request.id,
                NotificationType.TRACKING_STARTED,
                "Flight price tracking started",
                result.get("message_id"),
                NotificationStatus.SENT if result.get("success") else NotificationStatus.FAILED,
                None if result.get("success") else "Failed to send notification"
            )
            
        except Exception as e:
            logger.error(f"Failed to send tracking started notification for request {request.id}: {e}")
            await self._log_notification(
                request.id,
                NotificationType.TRACKING_STARTED,
                "Flight price tracking started",
                None,
                NotificationStatus.FAILED,
                str(e)
            )
    
    async def _send_price_change_notification(self, request: FlightTrackingRequestDB, 
                                            old_price: Decimal, new_price: Decimal):
        """Send price change notification."""
        try:
            # Determine message type based on price direction
            if new_price < old_price:
                message_type = MessageType.PRICE_DROP
            elif new_price > old_price:
                message_type = MessageType.PRICE_INCREASE
            else:
                message_type = MessageType.PRICE_CHANGE
            
            context = NotificationContext(
                origin=request.origin_iata,
                destination=request.destination_iata,
                departure_date=request.departure_date.isoformat(),
                return_date=request.return_date.isoformat() if request.return_date else None,
                old_price=old_price,
                new_price=new_price,
                currency=request.currency,
                tracking_id=str(request.id)
            )
            
            result = await telegram_service.send_price_change_notification(
                chat_id=request.telegram_chat_id,
                context=context,
                message_type=message_type
            )
            
            # Log notification
            await self._log_notification(
                request.id,
                NotificationType.PRICE_CHANGE,
                f"Price changed from {old_price} to {new_price} {request.currency}",
                result.get("message_id"),
                NotificationStatus.SENT if result.get("success") else NotificationStatus.FAILED,
                None if result.get("success") else "Failed to send notification",
                old_price,
                new_price
            )
            
        except Exception as e:
            logger.error(f"Failed to send price change notification for request {request.id}: {e}")
            await self._log_notification(
                request.id,
                NotificationType.PRICE_CHANGE,
                f"Price changed from {old_price} to {new_price} {request.currency}",
                None,
                NotificationStatus.FAILED,
                str(e),
                old_price,
                new_price
            )
    
    async def _send_error_notification(self, request: FlightTrackingRequestDB, error_details: str):
        """Send error notification."""
        try:
            context = NotificationContext(
                origin=request.origin_iata,
                destination=request.destination_iata,
                departure_date=request.departure_date.isoformat(),
                return_date=request.return_date.isoformat() if request.return_date else None,
                currency=request.currency,
                tracking_id=str(request.id)
            )
            
            result = await telegram_service.send_error_notification(
                chat_id=request.telegram_chat_id,
                context=context,
                error_details=error_details
            )
            
            # Log notification
            await self._log_notification(
                request.id,
                NotificationType.ERROR,
                f"Error in price monitoring: {error_details}",
                result.get("message_id"),
                NotificationStatus.SENT if result.get("success") else NotificationStatus.FAILED,
                None if result.get("success") else "Failed to send notification"
            )
            
        except Exception as e:
            logger.error(f"Failed to send error notification for request {request.id}: {e}")
    
    async def _log_notification(self, tracking_request_id: str, notification_type: NotificationType,
                              message_content: str, telegram_message_id: Optional[int] = None,
                              status: NotificationStatus = NotificationStatus.SENT,
                              error_message: Optional[str] = None,
                              old_price: Optional[Decimal] = None,
                              new_price: Optional[Decimal] = None):
        """Log notification to database."""
        try:
            async with get_async_session() as session:
                notification_log = NotificationLogDB(
                    tracking_request_id=tracking_request_id,
                    notification_type=notification_type,
                    old_price=old_price,
                    new_price=new_price,
                    message_content=message_content,
                    telegram_message_id=telegram_message_id,
                    status=status,
                    error_message=error_message,
                    sent_at=datetime.utcnow()
                )
                
                session.add(notification_log)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")
    
    async def expire_old_requests(self) -> int:
        """
        Mark expired tracking requests as inactive.
        
        Returns:
            Number of requests expired
        """
        async with get_async_session() as session:
            # Update expired requests
            query = update(FlightTrackingRequestDB).where(
                FlightTrackingRequestDB.is_active == True,
                FlightTrackingRequestDB.expires_at <= datetime.utcnow()
            ).values(is_active=False)
            
            result = await session.execute(query)
            expired_count = result.rowcount
            
            if expired_count > 0:
                logger.info(f"Expired {expired_count} tracking requests")
                
                # Send expiry notifications for recently expired requests
                expired_requests_query = select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.is_active == False,
                    FlightTrackingRequestDB.expires_at <= datetime.utcnow(),
                    FlightTrackingRequestDB.expires_at > datetime.utcnow() - timedelta(hours=24)  # Last 24 hours
                )
                
                expired_requests = await session.execute(expired_requests_query)
                for request in expired_requests.scalars():
                    try:
                        await self._send_tracking_expired_notification(request)
                    except Exception as e:
                        logger.error(f"Failed to send expiry notification for request {request.id}: {e}")
            
            await session.commit()
            return expired_count
    
    async def _send_tracking_expired_notification(self, request: FlightTrackingRequestDB):
        """Send tracking expired notification."""
        try:
            context = NotificationContext(
                origin=request.origin_iata,
                destination=request.destination_iata,
                departure_date=request.departure_date.isoformat(),
                return_date=request.return_date.isoformat() if request.return_date else None,
                currency=request.currency,
                tracking_id=str(request.id)
            )
            
            result = await telegram_service.send_tracking_expired_notification(
                chat_id=request.telegram_chat_id,
                context=context
            )
            
            # Log notification
            await self._log_notification(
                request.id,
                NotificationType.TRACKING_STOPPED,
                "Flight tracking expired",
                result.get("message_id"),
                NotificationStatus.SENT if result.get("success") else NotificationStatus.FAILED,
                None if result.get("success") else "Failed to send notification"
            )
            
        except Exception as e:
            logger.error(f"Failed to send tracking expired notification for request {request.id}: {e}")


# Global service instance
price_monitoring_service = PriceMonitoringService()