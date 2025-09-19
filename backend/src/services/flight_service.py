"""Flight API service for Amadeus integration."""

import os
import httpx
import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal
from dataclasses import dataclass
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class FlightSearchParams:
    """Parameters for flight search."""
    origin: str  # IATA code
    destination: str  # IATA code
    departure_date: date
    return_date: Optional[date] = None
    adults: int = 1
    currency: str = "USD"


@dataclass
class FlightOffer:
    """Flight offer from search results."""
    id: str
    flight_number: str
    airline: str
    airline_code: str
    price: Decimal
    currency: str
    departure_time: datetime
    arrival_time: datetime
    duration: str
    stops: int
    booking_url: Optional[str] = None
    source_data: Optional[Dict[str, Any]] = None


class FlightSearchResponse(BaseModel):
    """Response from flight search."""
    flights: List[FlightOffer]
    search_metadata: Dict[str, Any]
    total_results: int
    currency: str = "USD"


class FlightAPIError(Exception):
    """Custom exception for flight API errors."""
    pass


class FlightService:
    """Service for interacting with flight search APIs."""
    
    def __init__(self):
        self.amadeus_api_key = os.getenv("AMADEUS_API_KEY")
        self.amadeus_api_secret = os.getenv("AMADEUS_API_SECRET") 
        self.amadeus_base_url = "https://api.amadeus.com"
        self.access_token = None
        self.token_expires_at = None
        
        # Fallback to mock data if no API credentials
        self.use_mock_data = not (self.amadeus_api_key and self.amadeus_api_secret)
        if self.use_mock_data:
            logger.warning("No Amadeus API credentials found, using mock data")
    
    async def authenticate(self) -> str:
        """Authenticate with Amadeus API and get access token."""
        if not self.amadeus_api_key or not self.amadeus_api_secret:
            raise FlightAPIError("Amadeus API credentials not configured")
        
        # Check if we have a valid token
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
        
        auth_url = f"{self.amadeus_base_url}/v1/security/oauth2/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "client_credentials",
            "client_id": self.amadeus_api_key,
            "client_secret": self.amadeus_api_secret
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(auth_url, headers=headers, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 1799)  # Default 30 minutes
                self.token_expires_at = datetime.now().timestamp() + expires_in - 60  # 1 minute buffer
                
                return self.access_token
        except httpx.HTTPError as e:
            logger.error(f"Failed to authenticate with Amadeus API: {e}")
            raise FlightAPIError(f"Authentication failed: {e}")
    
    async def search_flights(self, params: FlightSearchParams) -> FlightSearchResponse:
        """
        Search for flights using Amadeus API.
        
        Args:
            params: Flight search parameters
            
        Returns:
            FlightSearchResponse: Search results
        """
        if self.use_mock_data:
            return await self._get_mock_flight_data(params)
        
        try:
            token = await self.authenticate()
            
            search_url = f"{self.amadeus_base_url}/v2/shopping/flight-offers"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            search_params = {
                "originLocationCode": params.origin,
                "destinationLocationCode": params.destination,
                "departureDate": params.departure_date.isoformat(),
                "adults": params.adults,
                "currencyCode": params.currency,
                "max": 20  # Limit results
            }
            
            if params.return_date:
                search_params["returnDate"] = params.return_date.isoformat()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(search_url, headers=headers, params=search_params)
                response.raise_for_status()
                
                data = response.json()
                return self._parse_amadeus_response(data, params)
                
        except httpx.HTTPError as e:
            logger.error(f"Flight search API error: {e}")
            # Fallback to mock data on API failure
            return await self._get_mock_flight_data(params)
        except Exception as e:
            logger.error(f"Unexpected error in flight search: {e}")
            raise FlightAPIError(f"Flight search failed: {e}")
    
    def _parse_amadeus_response(self, data: Dict[str, Any], params: FlightSearchParams) -> FlightSearchResponse:
        """Parse Amadeus API response into our format."""
        flights = []
        
        for offer in data.get("data", []):
            try:
                # Extract flight details from Amadeus response
                flight_offer = self._extract_flight_offer(offer)
                if flight_offer:
                    flights.append(flight_offer)
            except Exception as e:
                logger.warning(f"Failed to parse flight offer: {e}")
                continue
        
        metadata = {
            "search_date": datetime.now().isoformat(),
            "origin": params.origin,
            "destination": params.destination,
            "departure_date": params.departure_date.isoformat(),
            "return_date": params.return_date.isoformat() if params.return_date else None,
            "source": "amadeus"
        }
        
        return FlightSearchResponse(
            flights=flights,
            search_metadata=metadata,
            total_results=len(flights),
            currency=params.currency
        )
    
    def _extract_flight_offer(self, offer: Dict[str, Any]) -> Optional[FlightOffer]:
        """Extract flight offer details from Amadeus response."""
        try:
            # Price information
            price_info = offer["price"]
            price = Decimal(price_info["total"])
            currency = price_info["currency"]
            
            # Flight segments (using first itinerary, first segment for simplicity)
            itineraries = offer["itineraries"]
            first_itinerary = itineraries[0]
            segments = first_itinerary["segments"]
            first_segment = segments[0]
            
            # Flight details
            operating = first_segment["operating"]
            airline_code = operating["carrierCode"]
            flight_number = f"{airline_code}{operating['number']}"
            
            # Departure and arrival
            departure = first_segment["departure"]
            arrival = first_segment["arrival"]
            
            departure_time = datetime.fromisoformat(departure["at"].replace("Z", "+00:00"))
            arrival_time = datetime.fromisoformat(arrival["at"].replace("Z", "+00:00"))
            
            # Duration
            duration = first_itinerary.get("duration", "Unknown")
            
            # Stops (number of segments - 1)
            stops = len(segments) - 1
            
            return FlightOffer(
                id=offer["id"],
                flight_number=flight_number,
                airline=airline_code,  # Could be enhanced with airline name lookup
                airline_code=airline_code,
                price=price,
                currency=currency,
                departure_time=departure_time,
                arrival_time=arrival_time,
                duration=duration,
                stops=stops,
                source_data=offer
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Failed to extract flight offer details: {e}")
            return None
    
    async def _get_mock_flight_data(self, params: FlightSearchParams) -> FlightSearchResponse:
        """Generate mock flight data for testing/development."""
        # Simulate API delay
        import asyncio
        await asyncio.sleep(0.1)
        
        base_price = 300  # Base price in USD
        
        # Generate some mock flights
        mock_flights = []
        airlines = [
            ("AA", "American Airlines"),
            ("UA", "United Airlines"), 
            ("DL", "Delta Air Lines"),
            ("SW", "Southwest Airlines")
        ]
        
        for i, (code, name) in enumerate(airlines):
            price = Decimal(str(base_price + (i * 50) + (hash(f"{params.origin}{params.destination}") % 200)))
            
            # Mock flight times
            departure_time = datetime.combine(params.departure_date, datetime.min.time().replace(hour=8 + i * 2))
            arrival_time = departure_time.replace(hour=departure_time.hour + 3 + i)  # 3-6 hour flights
            
            mock_flights.append(FlightOffer(
                id=f"mock_{code}_{i}",
                flight_number=f"{code}{1000 + i}",
                airline=name,
                airline_code=code,
                price=price,
                currency=params.currency,
                departure_time=departure_time,
                arrival_time=arrival_time,
                duration=f"PT{3 + i}H00M",
                stops=0 if i < 2 else 1,
                booking_url=f"https://example.com/book/{code}{1000 + i}",
                source_data={"mock": True, "generated_at": datetime.now().isoformat()}
            ))
        
        metadata = {
            "search_date": datetime.now().isoformat(),
            "origin": params.origin,
            "destination": params.destination,
            "departure_date": params.departure_date.isoformat(),
            "return_date": params.return_date.isoformat() if params.return_date else None,
            "source": "mock"
        }
        
        return FlightSearchResponse(
            flights=mock_flights,
            search_metadata=metadata,
            total_results=len(mock_flights),
            currency=params.currency
        )
    
    async def get_current_price(self, origin: str, destination: str, departure_date: date, 
                              return_date: Optional[date] = None) -> Optional[Decimal]:
        """
        Get current price for a specific flight route.
        
        Args:
            origin: Origin IATA code
            destination: Destination IATA code
            departure_date: Departure date
            return_date: Return date (optional)
            
        Returns:
            Current lowest price or None if not found
        """
        params = FlightSearchParams(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date
        )
        
        try:
            results = await self.search_flights(params)
            if results.flights:
                # Return the lowest price
                lowest_price = min(flight.price for flight in results.flights)
                return lowest_price
            return None
        except Exception as e:
            logger.error(f"Failed to get current price: {e}")
            return None


# Global service instance
flight_service = FlightService()