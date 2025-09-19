"""API endpoints for flight search."""

import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..services.flight_service import flight_service, FlightSearchParams, FlightAPIError
from ..services.validation_service import validation_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search")
async def search_flights(
    origin: str = Query(..., description="Origin airport IATA code (e.g., JFK)", min_length=3, max_length=3),
    destination: str = Query(..., description="Destination airport IATA code (e.g., LAX)", min_length=3, max_length=3),
    departure_date: date = Query(..., description="Departure date (YYYY-MM-DD)"),
    return_date: Optional[date] = Query(None, description="Return date for round trips (YYYY-MM-DD)"),
    adults: int = Query(1, ge=1, le=9, description="Number of adult passengers"),
    currency: str = Query("USD", description="Price currency code", min_length=3, max_length=3)
):
    """
    Search for available flights.
    
    - **origin**: IATA code for departure airport
    - **destination**: IATA code for arrival airport
    - **departure_date**: Flight departure date
    - **return_date**: Return flight date (optional, for round trips)
    - **adults**: Number of adult passengers (1-9)
    - **currency**: Currency for prices (default: USD)
    
    Returns flight offers with pricing, schedule, and booking information.
    """
    try:
        # Validate input parameters
        
        # Validate airport codes
        origin_result = validation_service.validate_iata_code(origin.upper())
        if not origin_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid origin airport code",
                    "errors": origin_result.errors
                }
            )
        
        destination_result = validation_service.validate_iata_code(destination.upper())
        if not destination_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid destination airport code", 
                    "errors": destination_result.errors
                }
            )
        
        # Validate route
        route_result = validation_service.validate_route(origin.upper(), destination.upper())
        if not route_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid flight route",
                    "errors": route_result.errors
                }
            )
        
        # Validate dates
        date_result = validation_service.validate_date_range(departure_date, return_date)
        if not date_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid date range",
                    "errors": date_result.errors
                }
            )
        
        # Validate currency
        currency_result = validation_service.validate_currency_code(currency.upper())
        if not currency_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid currency code",
                    "errors": currency_result.errors
                }
            )
        
        # Create search parameters
        search_params = FlightSearchParams(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            currency=currency.upper()
        )
        
        # Search for flights
        logger.info(f"Searching flights: {origin} -> {destination} on {departure_date}")
        
        search_results = await flight_service.search_flights(search_params)
        
        # Convert to API response format
        response = {
            "flights": [
                {
                    "id": flight.id,
                    "flight_number": flight.flight_number,
                    "airline": flight.airline,
                    "airline_code": flight.airline_code,
                    "price": float(flight.price),
                    "currency": flight.currency,
                    "departure_time": flight.departure_time.isoformat(),
                    "arrival_time": flight.arrival_time.isoformat(),
                    "duration": flight.duration,
                    "stops": flight.stops,
                    "booking_url": flight.booking_url
                }
                for flight in search_results.flights
            ],
            "search_metadata": {
                **search_results.search_metadata,
                "request_params": {
                    "origin": origin.upper(),
                    "destination": destination.upper(),
                    "departure_date": departure_date.isoformat(),
                    "return_date": return_date.isoformat() if return_date else None,
                    "adults": adults,
                    "currency": currency.upper()
                }
            },
            "total_results": search_results.total_results,
            "currency": search_results.currency
        }
        
        logger.info(f"Found {search_results.total_results} flights for {origin} -> {destination}")
        
        return response
        
    except HTTPException:
        raise
    except FlightAPIError as e:
        logger.error(f"Flight API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Flight search service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in flight search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Flight search failed"
        )


@router.get("/current-price")
async def get_current_price(
    origin: str = Query(..., description="Origin airport IATA code", min_length=3, max_length=3),
    destination: str = Query(..., description="Destination airport IATA code", min_length=3, max_length=3),
    departure_date: date = Query(..., description="Departure date (YYYY-MM-DD)"),
    return_date: Optional[date] = Query(None, description="Return date (YYYY-MM-DD)")
):
    """
    Get current lowest price for a specific route.
    
    - **origin**: IATA code for departure airport
    - **destination**: IATA code for arrival airport
    - **departure_date**: Flight departure date
    - **return_date**: Return flight date (optional)
    
    Returns the current lowest available price for the route.
    """
    try:
        # Validate input parameters (reuse validation from search endpoint)
        route_result = validation_service.validate_route(origin.upper(), destination.upper())
        if not route_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid flight route",
                    "errors": route_result.errors
                }
            )
        
        date_result = validation_service.validate_date_range(departure_date, return_date)
        if not date_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Invalid date range",
                    "errors": date_result.errors
                }
            )
        
        # Get current price
        logger.info(f"Getting current price: {origin} -> {destination} on {departure_date}")
        
        current_price = await flight_service.get_current_price(
            origin=origin.upper(),
            destination=destination.upper(), 
            departure_date=departure_date,
            return_date=return_date
        )
        
        if current_price is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No flights found for the specified route and date"
            )
        
        response = {
            "route": {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "departure_date": departure_date.isoformat(),
                "return_date": return_date.isoformat() if return_date else None
            },
            "current_price": float(current_price),
            "currency": "USD",  # Default currency
            "checked_at": date.today().isoformat()
        }
        
        return response
        
    except HTTPException:
        raise
    except FlightAPIError as e:
        logger.error(f"Flight API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Price lookup service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting current price: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Price lookup failed"
        )