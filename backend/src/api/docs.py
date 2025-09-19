"""OpenAPI documentation completion and examples."""

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from enum import Enum


# Response models for documentation
class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: Dict[str, Any] = Field(
        ...,
        description="Error details",
        example={
            "code": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "field": "departure_date"
        }
    )


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service health status", example="healthy")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="API version", example="1.0.0")
    services: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Individual service status",
        example={
            "database": {"status": "healthy", "response_time": "< 10ms"},
            "cache": {"status": "healthy", "response_time": "< 5ms"},
            "external_apis": {"status": "healthy", "response_time": "< 100ms"}
        }
    )


class FlightOfferResponse(BaseModel):
    """Flight offer response model."""
    flight_id: str = Field(..., description="Unique flight identifier", example="UA123-2024-01-15")
    airline: str = Field(..., description="Airline name", example="United Airlines")
    departure_time: datetime = Field(..., description="Departure time", example="2024-01-15T08:00:00Z")
    arrival_time: datetime = Field(..., description="Arrival time", example="2024-01-15T14:30:00Z")
    price: float = Field(..., description="Flight price", example=299.99)
    currency: str = Field(..., description="Price currency", example="USD")
    booking_url: Optional[str] = Field(None, description="Booking URL", example="https://example.com/book/123")


class FlightSearchResponse(BaseModel):
    """Flight search response model."""
    offers: List[FlightOfferResponse] = Field(..., description="List of flight offers")
    search_params: Dict[str, Any] = Field(
        ...,
        description="Search parameters used",
        example={
            "origin": "JFK",
            "destination": "LAX", 
            "departure_date": "2024-01-15",
            "passengers": 1,
            "cabin_class": "economy"
        }
    )
    total_results: int = Field(..., description="Total number of results", example=25)
    cached: bool = Field(..., description="Whether results were cached", example=False)


class TrackingRequestStatus(str, Enum):
    """Tracking request status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"


class TrackingRequestCreate(BaseModel):
    """Create tracking request model."""
    user_id: str = Field(..., description="User identifier", example="user_123")
    origin_airport: str = Field(
        ..., 
        description="IATA origin airport code", 
        example="JFK",
        min_length=3,
        max_length=3
    )
    destination_airport: str = Field(
        ..., 
        description="IATA destination airport code", 
        example="LAX",
        min_length=3,
        max_length=3
    )
    departure_date: date = Field(
        ..., 
        description="Flight departure date", 
        example="2024-01-15"
    )
    return_date: Optional[date] = Field(
        None, 
        description="Return flight date (for round trip)", 
        example="2024-01-22"
    )
    passengers: int = Field(
        1, 
        description="Number of passengers", 
        example=2,
        ge=1,
        le=9
    )
    cabin_class: str = Field(
        "economy", 
        description="Cabin class preference", 
        example="business"
    )
    max_price: Optional[float] = Field(
        None, 
        description="Maximum acceptable price", 
        example=500.0,
        ge=0
    )
    telegram_chat_id: int = Field(
        ..., 
        description="Telegram chat ID for notifications", 
        example=123456789
    )

    class Config:
        schema_extra = {
            "example": {
                "user_id": "user_123",
                "origin_airport": "JFK",
                "destination_airport": "LAX",
                "departure_date": "2024-01-15",
                "return_date": "2024-01-22",
                "passengers": 2,
                "cabin_class": "economy",
                "max_price": 500.0,
                "telegram_chat_id": 123456789
            }
        }


class TrackingRequestResponse(BaseModel):
    """Tracking request response model."""
    id: str = Field(..., description="Tracking request ID", example="550e8400-e29b-41d4-a716-446655440000")
    user_id: str = Field(..., description="User identifier", example="user_123")
    origin_airport: str = Field(..., description="Origin airport code", example="JFK")
    destination_airport: str = Field(..., description="Destination airport code", example="LAX")
    departure_date: date = Field(..., description="Departure date", example="2024-01-15")
    return_date: Optional[date] = Field(None, description="Return date", example="2024-01-22")
    passengers: int = Field(..., description="Number of passengers", example=2)
    cabin_class: str = Field(..., description="Cabin class", example="economy")
    max_price: Optional[float] = Field(None, description="Maximum price", example=500.0)
    status: TrackingRequestStatus = Field(..., description="Request status", example="active")
    created_at: datetime = Field(..., description="Creation timestamp", example="2024-01-01T12:00:00Z")
    telegram_chat_id: int = Field(..., description="Telegram chat ID", example=123456789)


class PriceHistoryResponse(BaseModel):
    """Price history response model."""
    id: str = Field(..., description="Price history entry ID")
    tracking_request_id: str = Field(..., description="Associated tracking request ID")
    flight_id: str = Field(..., description="Flight identifier", example="UA123-2024-01-15")
    airline: str = Field(..., description="Airline name", example="United Airlines")
    departure_time: datetime = Field(..., description="Flight departure time")
    arrival_time: datetime = Field(..., description="Flight arrival time")
    price: float = Field(..., description="Flight price", example=299.99)
    currency: str = Field(..., description="Price currency", example="USD")
    created_at: datetime = Field(..., description="Price check timestamp")
    booking_url: Optional[str] = Field(None, description="Booking URL")


class PaginationResponse(BaseModel):
    """Pagination information model."""
    page: int = Field(..., description="Current page number", example=1)
    per_page: int = Field(..., description="Items per page", example=20)
    total_items: int = Field(..., description="Total number of items", example=150)
    total_pages: int = Field(..., description="Total number of pages", example=8)
    has_next: bool = Field(..., description="Whether there is a next page", example=True)
    has_prev: bool = Field(..., description="Whether there is a previous page", example=False)


def setup_openapi_documentation(app: FastAPI) -> None:
    """Setup comprehensive OpenAPI documentation."""
    
    # Update app metadata
    app.title = "Flight Price Tracking API"
    app.description = """
    ## Flight Price Tracking API

    A comprehensive API for tracking flight prices and receiving notifications when prices drop.

    ### Features

    * **Flight Search**: Search for flights across multiple airlines
    * **Price Tracking**: Monitor flight prices automatically
    * **Notifications**: Get Telegram notifications when prices drop
    * **Price History**: View historical price data
    * **User Management**: Manage multiple tracking requests per user

    ### Authentication

    Currently, the API uses simple user identification via headers or request parameters.
    Future versions will implement proper authentication tokens.

    ### Rate Limiting

    * **Flight Search**: 60 requests per minute
    * **Tracking Requests**: 20 requests per minute
    * **General API**: 100 requests per minute

    ### Caching

    * Flight search results are cached for 15 minutes
    * API responses are cached to improve performance
    * Cache can be bypassed with `Cache-Control: no-cache` header

    ### Error Handling

    All errors follow RFC 7807 Problem Details standard:

    ```json
    {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Detailed error message",
            "field": "specific_field_name"
        }
    }
    ```

    ### Webhooks

    Configure webhook endpoints to receive price alerts:

    * **Price Drop**: When flight price drops significantly
    * **Target Price**: When flight price meets user's target
    * **Expiry Warning**: When tracking request is about to expire

    ### Support

    * **Documentation**: [API Docs](/docs)
    * **Health Check**: [GET /api/v1/health](/api/v1/health)
    * **OpenAPI Schema**: [GET /openapi.json](/openapi.json)
    """
    
    app.version = "1.0.0"
    app.openapi_tags = [
        {
            "name": "health",
            "description": "Health checks and system status"
        },
        {
            "name": "flights", 
            "description": "Flight search and price information"
        },
        {
            "name": "tracking",
            "description": "Price tracking request management"
        }
    ]
    
    # Add custom OpenAPI schema
    app.openapi_version = "3.0.2"
    
    # Add servers information
    if not hasattr(app, 'servers'):
        app.servers = [
            {
                "url": "https://api.flightpricetracker.com",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.flightpricetracker.com",
                "description": "Staging server"
            },
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ]


def get_openapi_examples() -> Dict[str, Any]:
    """Get OpenAPI documentation examples."""
    
    return {
        "flight_search_examples": {
            "economy_domestic": {
                "summary": "Domestic Economy Flight",
                "description": "Search for economy flights within the same country",
                "value": {
                    "origin": "JFK",
                    "destination": "LAX",
                    "departure_date": "2024-02-15",
                    "passengers": 1,
                    "cabin_class": "economy"
                }
            },
            "business_international": {
                "summary": "International Business Flight",
                "description": "Search for business class international flights",
                "value": {
                    "origin": "JFK",
                    "destination": "LHR", 
                    "departure_date": "2024-03-20",
                    "return_date": "2024-03-27",
                    "passengers": 2,
                    "cabin_class": "business"
                }
            },
            "family_vacation": {
                "summary": "Family Vacation",
                "description": "Round-trip flights for a family",
                "value": {
                    "origin": "LAX",
                    "destination": "MIA",
                    "departure_date": "2024-07-01",
                    "return_date": "2024-07-10",
                    "passengers": 4,
                    "cabin_class": "economy"
                }
            }
        },
        
        "tracking_request_examples": {
            "basic_tracking": {
                "summary": "Basic Price Tracking",
                "description": "Track price for a specific route with maximum price limit",
                "value": {
                    "user_id": "user_12345",
                    "origin_airport": "JFK",
                    "destination_airport": "LAX",
                    "departure_date": "2024-02-15",
                    "passengers": 1,
                    "cabin_class": "economy",
                    "max_price": 400.0,
                    "telegram_chat_id": 123456789
                }
            },
            "round_trip_tracking": {
                "summary": "Round-trip Price Tracking",
                "description": "Track prices for round-trip flights",
                "value": {
                    "user_id": "user_67890",
                    "origin_airport": "SFO",
                    "destination_airport": "NYC",
                    "departure_date": "2024-03-10",
                    "return_date": "2024-03-17",
                    "passengers": 2,
                    "cabin_class": "business",
                    "max_price": 1200.0,
                    "telegram_chat_id": 987654321
                }
            },
            "budget_travel": {
                "summary": "Budget Travel Tracking", 
                "description": "Track very affordable flights with strict price limits",
                "value": {
                    "user_id": "budget_traveler",
                    "origin_airport": "BWI",
                    "destination_airport": "FLL",
                    "departure_date": "2024-05-15",
                    "passengers": 1,
                    "cabin_class": "economy",
                    "max_price": 200.0,
                    "telegram_chat_id": 555666777
                }
            }
        },
        
        "response_examples": {
            "flight_offers": {
                "summary": "Flight Search Results",
                "value": {
                    "offers": [
                        {
                            "flight_id": "UA123-2024-02-15",
                            "airline": "United Airlines",
                            "departure_time": "2024-02-15T08:00:00Z",
                            "arrival_time": "2024-02-15T14:30:00Z",
                            "price": 299.99,
                            "currency": "USD",
                            "booking_url": "https://united.com/book/UA123"
                        },
                        {
                            "flight_id": "DL456-2024-02-15",
                            "airline": "Delta Air Lines",
                            "departure_time": "2024-02-15T10:15:00Z",
                            "arrival_time": "2024-02-15T16:45:00Z",
                            "price": 325.50,
                            "currency": "USD",
                            "booking_url": "https://delta.com/book/DL456"
                        }
                    ],
                    "search_params": {
                        "origin": "JFK",
                        "destination": "LAX",
                        "departure_date": "2024-02-15",
                        "passengers": 1,
                        "cabin_class": "economy"
                    },
                    "total_results": 15,
                    "cached": False
                }
            },
            
            "tracking_request": {
                "summary": "Created Tracking Request",
                "value": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_id": "user_12345",
                    "origin_airport": "JFK",
                    "destination_airport": "LAX", 
                    "departure_date": "2024-02-15",
                    "return_date": None,
                    "passengers": 1,
                    "cabin_class": "economy",
                    "max_price": 400.0,
                    "status": "active",
                    "created_at": "2024-01-15T10:30:00Z",
                    "telegram_chat_id": 123456789
                }
            },
            
            "price_history": {
                "summary": "Price History Data",
                "value": [
                    {
                        "id": "price_001",
                        "tracking_request_id": "550e8400-e29b-41d4-a716-446655440000",
                        "flight_id": "UA123-2024-02-15",
                        "airline": "United Airlines",
                        "departure_time": "2024-02-15T08:00:00Z",
                        "arrival_time": "2024-02-15T14:30:00Z",
                        "price": 350.0,
                        "currency": "USD",
                        "created_at": "2024-01-15T10:30:00Z",
                        "booking_url": "https://united.com/book/UA123"
                    },
                    {
                        "id": "price_002", 
                        "tracking_request_id": "550e8400-e29b-41d4-a716-446655440000",
                        "flight_id": "UA123-2024-02-15",
                        "airline": "United Airlines",
                        "departure_time": "2024-02-15T08:00:00Z",
                        "arrival_time": "2024-02-15T14:30:00Z",
                        "price": 299.99,
                        "currency": "USD",
                        "created_at": "2024-01-16T10:30:00Z",
                        "booking_url": "https://united.com/book/UA123"
                    }
                ]
            }
        },
        
        "error_examples": {
            "validation_error": {
                "summary": "Validation Error",
                "value": {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid airport code format",
                        "field": "origin_airport"
                    }
                }
            },
            "not_found": {
                "summary": "Resource Not Found",
                "value": {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Tracking request not found with ID: 123",
                        "resource": "TrackingRequest",
                        "resource_id": "123"
                    }
                }
            },
            "rate_limit": {
                "summary": "Rate Limit Exceeded",
                "value": {
                    "error": {
                        "code": "RATE_LIMIT_ERROR",
                        "message": "Rate limit exceeded. Maximum 60 requests per minute.",
                        "retry_after": 45
                    }
                }
            },
            "service_unavailable": {
                "summary": "Service Unavailable",
                "value": {
                    "error": {
                        "code": "SERVICE_UNAVAILABLE", 
                        "message": "Flight API service is temporarily unavailable",
                        "service": "Amadeus API",
                        "retry_after": 30
                    }
                }
            }
        }
    }


def get_openapi_security_schemes() -> Dict[str, Any]:
    """Get OpenAPI security scheme definitions."""
    
    return {
        "UserAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-User-ID",
            "description": "User identifier for request authorization"
        },
        "APIKeyAuth": {
            "type": "apiKey", 
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service access (future implementation)"
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token for authenticated access (future implementation)"
        }
    }


# Custom OpenAPI generation
def custom_openapi_generator(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced documentation."""
    
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add custom extensions
    examples = get_openapi_examples()
    security_schemes = get_openapi_security_schemes()
    
    # Add security schemes
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    
    openapi_schema["components"]["securitySchemes"] = security_schemes
    
    # Add examples to schema
    if "x-examples" not in openapi_schema:
        openapi_schema["x-examples"] = examples
    
    # Add contact information
    openapi_schema["info"]["contact"] = {
        "name": "Flight Price Tracker API Support",
        "email": "api-support@flightpricetracker.com",
        "url": "https://github.com/flightpricetracker/api"
    }
    
    # Add license information
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Add external documentation
    openapi_schema["externalDocs"] = {
        "description": "Flight Price Tracker Documentation",
        "url": "https://docs.flightpricetracker.com"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Export all models for use in API endpoints
__all__ = [
    "ErrorResponse",
    "HealthResponse", 
    "FlightOfferResponse",
    "FlightSearchResponse",
    "TrackingRequestStatus",
    "TrackingRequestCreate",
    "TrackingRequestResponse",
    "PriceHistoryResponse",
    "PaginationResponse",
    "setup_openapi_documentation",
    "get_openapi_examples",
    "get_openapi_security_schemes", 
    "custom_openapi_generator"
]