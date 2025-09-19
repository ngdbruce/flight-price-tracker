"""API endpoints for flight tracking requests."""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import Response

from ..models.tracking_request import (
    FlightTrackingRequestSchema,
    FlightTrackingRequestCreate,
    FlightTrackingRequestUpdate
)
from ..models.price_history import PriceHistoryResponse
from ..services.tracking_service import tracking_service, TrackingServiceError
from ..services.validation_service import validation_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/requests", response_model=FlightTrackingRequestSchema, status_code=status.HTTP_201_CREATED)
async def create_tracking_request(request_data: FlightTrackingRequestCreate):
    """
    Create a new flight price tracking request.
    
    - **origin_iata**: IATA code for departure airport
    - **destination_iata**: IATA code for arrival airport  
    - **departure_date**: Flight departure date
    - **return_date**: Return flight date (optional)
    - **telegram_chat_id**: Telegram chat ID for notifications
    - **price_threshold**: Minimum % change to trigger notification (default 5.0)
    - **currency**: Price currency code (default USD)
    """
    try:
        # Validate the request data
        validation_result = validation_service.validate_tracking_request_data(request_data.dict())
        
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings
                }
            )
        
        # Create the tracking request
        created_request = await tracking_service.create_tracking_request(request_data)
        
        logger.info(f"Created tracking request {created_request.id} for user {request_data.telegram_chat_id}")
        
        return created_request
        
    except TrackingServiceError as e:
        logger.error(f"Failed to create tracking request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating tracking request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tracking request"
        )


@router.get("/requests", response_model=dict)
async def get_tracking_requests(
    telegram_chat_id: Optional[int] = Query(None, description="Filter by Telegram chat ID"),
    active_only: bool = Query(False, description="Only return active requests"),
    skip: int = Query(0, ge=0, description="Number of requests to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of requests to return")
):
    """
    Get tracking requests.
    
    - **telegram_chat_id**: Filter by user's Telegram chat ID
    - **active_only**: Only return active (non-expired) requests
    - **skip**: Number of requests to skip (pagination)
    - **limit**: Maximum number of requests to return
    """
    try:
        if telegram_chat_id:
            # Get requests for specific user
            requests = await tracking_service.get_user_tracking_requests(
                telegram_chat_id=telegram_chat_id,
                active_only=active_only
            )
            total_count = len(requests)
            
            # Apply pagination
            paginated_requests = requests[skip:skip + limit]
            
        else:
            # Get all requests (admin endpoint)
            requests = await tracking_service.get_all_tracking_requests(
                skip=skip,
                limit=limit,
                active_only=active_only
            )
            paginated_requests = requests
            total_count = len(requests)  # Note: This is approximate for pagination
        
        return {
            "requests": paginated_requests,
            "total_count": total_count,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Failed to get tracking requests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracking requests"
        )


@router.get("/requests/{request_id}", response_model=FlightTrackingRequestSchema)
async def get_tracking_request(request_id: UUID):
    """
    Get a specific tracking request by ID.
    
    - **request_id**: UUID of the tracking request
    """
    try:
        request = await tracking_service.get_tracking_request(request_id)
        
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tracking request {request_id} not found"
            )
        
        return request
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tracking request {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracking request"
        )


@router.put("/requests/{request_id}", response_model=FlightTrackingRequestSchema)
async def update_tracking_request(request_id: UUID, update_data: FlightTrackingRequestUpdate):
    """
    Update a tracking request.
    
    - **request_id**: UUID of the tracking request
    - **price_threshold**: New price threshold percentage
    - **is_active**: Enable/disable tracking
    """
    try:
        updated_request = await tracking_service.update_tracking_request(request_id, update_data)
        
        if not updated_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tracking request {request_id} not found"
            )
        
        logger.info(f"Updated tracking request {request_id}")
        
        return updated_request
        
    except HTTPException:
        raise
    except TrackingServiceError as e:
        logger.error(f"Failed to update tracking request {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error updating tracking request {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tracking request"
        )


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracking_request(request_id: UUID):
    """
    Delete a tracking request.
    
    - **request_id**: UUID of the tracking request
    """
    try:
        deleted = await tracking_service.delete_tracking_request(request_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tracking request {request_id} not found"
            )
        
        logger.info(f"Deleted tracking request {request_id}")
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete tracking request {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tracking request"
        )


@router.get("/requests/{request_id}/prices", response_model=dict)
async def get_price_history(
    request_id: UUID,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(50, ge=1, le=200, description="Number of price records per page")
):
    """
    Get price history for a tracking request.
    
    - **request_id**: UUID of the tracking request
    - **page**: Page number (1-based)
    - **limit**: Number of price records per page
    """
    try:
        price_history = await tracking_service.get_price_history(request_id, page, limit)
        
        if price_history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tracking request {request_id} not found"
            )
        
        return price_history
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get price history for request {request_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve price history"
        )