"""Tracking request service for CRUD operations."""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

from src.models.tracking_request import (
    FlightTrackingRequestDB, 
    FlightTrackingRequestSchema,
    FlightTrackingRequestCreate,
    FlightTrackingRequestUpdate
)
from src.models.price_history import PriceHistoryDB, PriceHistorySchema
from src.database import get_async_session

logger = logging.getLogger(__name__)


class TrackingServiceError(Exception):
    """Custom exception for tracking service errors."""
    pass


class TrackingService:
    """Service for managing flight tracking requests."""
    
    async def create_tracking_request(self, request_data: FlightTrackingRequestCreate) -> FlightTrackingRequestSchema:
        """
        Create a new flight tracking request.
        
        Args:
            request_data: Tracking request creation data
            
        Returns:
            Created tracking request
            
        Raises:
            TrackingServiceError: If creation fails
        """
        try:
            async with get_async_session() as session:
                # Check for duplicate requests
                existing = await self._check_duplicate_request(session, request_data)
                if existing:
                    raise TrackingServiceError(
                        f"Duplicate tracking request for {request_data.origin_iata} → "
                        f"{request_data.destination_iata} on {request_data.departure_date}"
                    )
                
                # Calculate expiry date (departure date + 1 day)
                expires_at = datetime.combine(request_data.departure_date, datetime.min.time())
                expires_at = expires_at.replace(hour=23, minute=59, second=59)  # End of departure day
                
                # Create database model
                db_request = FlightTrackingRequestDB(
                    origin_iata=request_data.origin_iata,
                    destination_iata=request_data.destination_iata,
                    departure_date=request_data.departure_date,
                    return_date=request_data.return_date,
                    telegram_chat_id=request_data.telegram_chat_id,
                    price_threshold=request_data.price_threshold,
                    currency=request_data.currency,
                    expires_at=expires_at
                )
                
                session.add(db_request)
                await session.commit()
                await session.refresh(db_request)
                
                logger.info(f"Created tracking request {db_request.id} for {request_data.origin_iata} → {request_data.destination_iata}")
                
                return FlightTrackingRequestSchema.from_orm(db_request)
                
        except TrackingServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to create tracking request: {e}")
            raise TrackingServiceError(f"Failed to create tracking request: {e}")
    
    async def get_tracking_request(self, request_id: UUID) -> Optional[FlightTrackingRequestSchema]:
        """
        Get a tracking request by ID.
        
        Args:
            request_id: Request ID
            
        Returns:
            Tracking request or None if not found
        """
        try:
            async with get_async_session() as session:
                query = select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.id == request_id
                )
                
                result = await session.execute(query)
                db_request = result.scalar_one_or_none()
                
                if db_request:
                    return FlightTrackingRequestSchema.from_orm(db_request)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get tracking request {request_id}: {e}")
            raise TrackingServiceError(f"Failed to get tracking request: {e}")
    
    async def get_user_tracking_requests(self, telegram_chat_id: int, 
                                       active_only: bool = False) -> List[FlightTrackingRequestSchema]:
        """
        Get all tracking requests for a user.
        
        Args:
            telegram_chat_id: Telegram chat ID
            active_only: If True, only return active requests
            
        Returns:
            List of tracking requests
        """
        try:
            async with get_async_session() as session:
                query = select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.telegram_chat_id == telegram_chat_id
                )
                
                if active_only:
                    query = query.where(
                        FlightTrackingRequestDB.is_active == True,
                        FlightTrackingRequestDB.expires_at > datetime.utcnow()
                    )
                
                query = query.order_by(FlightTrackingRequestDB.created_at.desc())
                
                result = await session.execute(query)
                db_requests = result.scalars().all()
                
                return [FlightTrackingRequestSchema.from_orm(req) for req in db_requests]
                
        except Exception as e:
            logger.error(f"Failed to get user tracking requests for chat {telegram_chat_id}: {e}")
            raise TrackingServiceError(f"Failed to get user tracking requests: {e}")
    
    async def get_all_tracking_requests(self, skip: int = 0, limit: int = 100, 
                                      active_only: bool = False) -> List[FlightTrackingRequestSchema]:
        """
        Get all tracking requests (with pagination).
        
        Args:
            skip: Number of requests to skip
            limit: Maximum number of requests to return
            active_only: If True, only return active requests
            
        Returns:
            List of tracking requests
        """
        try:
            async with get_async_session() as session:
                query = select(FlightTrackingRequestDB)
                
                if active_only:
                    query = query.where(
                        FlightTrackingRequestDB.is_active == True,
                        FlightTrackingRequestDB.expires_at > datetime.utcnow()
                    )
                
                query = query.order_by(FlightTrackingRequestDB.created_at.desc())
                query = query.offset(skip).limit(limit)
                
                result = await session.execute(query)
                db_requests = result.scalars().all()
                
                return [FlightTrackingRequestSchema.from_orm(req) for req in db_requests]
                
        except Exception as e:
            logger.error(f"Failed to get all tracking requests: {e}")
            raise TrackingServiceError(f"Failed to get all tracking requests: {e}")
    
    async def update_tracking_request(self, request_id: UUID, 
                                    update_data: FlightTrackingRequestUpdate) -> Optional[FlightTrackingRequestSchema]:
        """
        Update a tracking request.
        
        Args:
            request_id: Request ID
            update_data: Update data
            
        Returns:
            Updated tracking request or None if not found
        """
        try:
            async with get_async_session() as session:
                query = select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.id == request_id
                )
                
                result = await session.execute(query)
                db_request = result.scalar_one_or_none()
                
                if not db_request:
                    return None
                
                # Update fields
                update_values = {}
                if update_data.price_threshold is not None:
                    update_values['price_threshold'] = update_data.price_threshold
                
                if update_data.is_active is not None:
                    update_values['is_active'] = update_data.is_active
                
                if update_values:
                    update_values['updated_at'] = datetime.utcnow()
                    
                    update_query = update(FlightTrackingRequestDB).where(
                        FlightTrackingRequestDB.id == request_id
                    ).values(**update_values)
                    
                    await session.execute(update_query)
                    await session.commit()
                    await session.refresh(db_request)
                
                logger.info(f"Updated tracking request {request_id}")
                
                return FlightTrackingRequestSchema.from_orm(db_request)
                
        except Exception as e:
            logger.error(f"Failed to update tracking request {request_id}: {e}")
            raise TrackingServiceError(f"Failed to update tracking request: {e}")
    
    async def delete_tracking_request(self, request_id: UUID) -> bool:
        """
        Delete a tracking request.
        
        Args:
            request_id: Request ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            async with get_async_session() as session:
                # Check if request exists
                query = select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.id == request_id
                )
                
                result = await session.execute(query)
                db_request = result.scalar_one_or_none()
                
                if not db_request:
                    return False
                
                # Delete request (cascade will handle related records)
                delete_query = delete(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.id == request_id
                )
                
                await session.execute(delete_query)
                await session.commit()
                
                logger.info(f"Deleted tracking request {request_id}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete tracking request {request_id}: {e}")
            raise TrackingServiceError(f"Failed to delete tracking request: {e}")
    
    async def get_price_history(self, request_id: UUID, page: int = 1, 
                              limit: int = 50) -> Optional[dict]:
        """
        Get price history for a tracking request.
        
        Args:
            request_id: Request ID
            page: Page number (1-based)
            limit: Number of records per page
            
        Returns:
            Dictionary with price history and metadata
        """
        try:
            async with get_async_session() as session:
                # Check if request exists
                request_query = select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.id == request_id
                )
                
                request_result = await session.execute(request_query)
                db_request = request_result.scalar_one_or_none()
                
                if not db_request:
                    return None
                
                # Get price history with pagination
                offset = (page - 1) * limit
                
                history_query = select(PriceHistoryDB).where(
                    PriceHistoryDB.tracking_request_id == request_id
                ).order_by(PriceHistoryDB.checked_at.desc()).offset(offset).limit(limit)
                
                history_result = await session.execute(history_query)
                price_history = history_result.scalars().all()
                
                # Get total count
                count_query = select(PriceHistoryDB).where(
                    PriceHistoryDB.tracking_request_id == request_id
                )
                count_result = await session.execute(count_query)
                total_count = len(count_result.scalars().all())
                
                return {
                    "prices": [PriceHistorySchema.from_orm(ph) for ph in price_history],
                    "request_id": request_id,
                    "total_count": total_count,
                    "page": page,
                    "limit": limit,
                    "has_next": total_count > (page * limit)
                }
                
        except Exception as e:
            logger.error(f"Failed to get price history for request {request_id}: {e}")
            raise TrackingServiceError(f"Failed to get price history: {e}")
    
    async def _check_duplicate_request(self, session: AsyncSession, 
                                     request_data: FlightTrackingRequestCreate) -> Optional[FlightTrackingRequestDB]:
        """Check if a duplicate tracking request already exists."""
        query = select(FlightTrackingRequestDB).where(
            and_(
                FlightTrackingRequestDB.origin_iata == request_data.origin_iata,
                FlightTrackingRequestDB.destination_iata == request_data.destination_iata,
                FlightTrackingRequestDB.departure_date == request_data.departure_date,
                or_(
                    and_(
                        FlightTrackingRequestDB.return_date == request_data.return_date,
                        request_data.return_date is not None
                    ),
                    and_(
                        FlightTrackingRequestDB.return_date.is_(None),
                        request_data.return_date is None
                    )
                ),
                FlightTrackingRequestDB.telegram_chat_id == request_data.telegram_chat_id,
                FlightTrackingRequestDB.is_active == True
            )
        )
        
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_active_requests_count(self) -> int:
        """Get count of active tracking requests."""
        try:
            async with get_async_session() as session:
                query = select(FlightTrackingRequestDB).where(
                    FlightTrackingRequestDB.is_active == True,
                    FlightTrackingRequestDB.expires_at > datetime.utcnow()
                )
                
                result = await session.execute(query)
                requests = result.scalars().all()
                
                return len(requests)
                
        except Exception as e:
            logger.error(f"Failed to get active requests count: {e}")
            return 0
    
    async def cleanup_old_requests(self, days_old: int = 30) -> int:
        """
        Clean up old inactive tracking requests.
        
        Args:
            days_old: Delete requests older than this many days
            
        Returns:
            Number of requests deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            async with get_async_session() as session:
                delete_query = delete(FlightTrackingRequestDB).where(
                    and_(
                        FlightTrackingRequestDB.is_active == False,
                        FlightTrackingRequestDB.updated_at < cutoff_date
                    )
                )
                
                result = await session.execute(delete_query)
                deleted_count = result.rowcount
                
                await session.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old tracking requests")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old requests: {e}")
            return 0


# Global service instance
tracking_service = TrackingService()