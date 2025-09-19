"""FlightTrackingRequest model with validation."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, String, Integer, BigInteger, DateTime, Date, 
    Numeric, Boolean, Text, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from pydantic import BaseModel, Field, validator
import re

Base = declarative_base()


class FlightTrackingRequestDB(Base):
    """Database model for flight tracking requests."""
    
    __tablename__ = "flight_tracking_requests"
    
    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Flight details
    origin_iata = Column(String(3), nullable=False)
    destination_iata = Column(String(3), nullable=False) 
    departure_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    
    # User and pricing
    telegram_chat_id = Column(BigInteger, nullable=False)
    baseline_price = Column(Numeric(10, 2), nullable=True)
    current_price = Column(Numeric(10, 2), nullable=True)
    price_threshold = Column(Numeric(5, 2), nullable=False, default=5.0)
    currency = Column(String(3), nullable=False, default="USD")
    
    # Status and timing
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships using string references to avoid circular imports
    # Will be configured after all models are loaded
    
    # Table constraints
    __table_args__ = (
        # Performance indexes
        Index("idx_tracking_active", "is_active", "expires_at"),
        Index("idx_tracking_dates", "departure_date", "return_date"),
        Index("idx_tracking_telegram", "telegram_chat_id"),
        
        # Unique constraint to prevent duplicates
        Index(
            "uq_tracking_request", 
            "origin_iata", "destination_iata", "departure_date", 
            "return_date", "telegram_chat_id",
            unique=True
        ),
        
        # Check constraints
        CheckConstraint("price_threshold >= 1.0 AND price_threshold <= 50.0", name="ck_price_threshold_range"),
        CheckConstraint("baseline_price > 0 OR baseline_price IS NULL", name="ck_baseline_price_positive"),
        CheckConstraint("current_price > 0 OR current_price IS NULL", name="ck_current_price_positive"),
        CheckConstraint("return_date IS NULL OR return_date > departure_date", name="ck_return_after_departure"),
        CheckConstraint("expires_at > created_at", name="ck_expires_after_created"),
    )
    
    @validates('origin_iata', 'destination_iata')
    def validate_iata_code(self, key, value):
        """Validate IATA airport codes."""
        if not value or len(value) != 3:
            raise ValueError(f"{key} must be exactly 3 characters")
        if not value.isupper():
            raise ValueError(f"{key} must be uppercase")
        if not value.isalpha():
            raise ValueError(f"{key} must contain only letters")
        return value
    
    @validates('telegram_chat_id')
    def validate_telegram_chat_id(self, key, value):
        """Validate Telegram chat ID format."""
        if not isinstance(value, int):
            raise ValueError("telegram_chat_id must be an integer")
        # Telegram chat IDs can be negative for groups, positive for users
        if abs(value) < 1:
            raise ValueError("telegram_chat_id must be non-zero")
        return value
    
    @validates('currency')
    def validate_currency(self, key, value):
        """Validate currency code."""
        if not value or len(value) != 3:
            raise ValueError("currency must be exactly 3 characters")
        if not value.isupper():
            raise ValueError("currency must be uppercase")
        return value
    
    def __repr__(self):
        return f"<FlightTrackingRequest({self.origin_iata}→{self.destination_iata}, {self.departure_date}, active={self.is_active})>"


class FlightTrackingRequestSchema(BaseModel):
    """Pydantic schema for API requests/responses."""
    
    id: Optional[UUID] = None
    origin_iata: str = Field(..., min_length=3, max_length=3, description="IATA airport code for departure")
    destination_iata: str = Field(..., min_length=3, max_length=3, description="IATA airport code for arrival")
    departure_date: date = Field(..., description="Flight departure date")
    return_date: Optional[date] = Field(None, description="Return flight date (for round trips)")
    telegram_chat_id: int = Field(..., description="Telegram chat ID for notifications")
    baseline_price: Optional[Decimal] = Field(None, ge=0, description="Initial price when tracking started")
    current_price: Optional[Decimal] = Field(None, ge=0, description="Most recent price found")
    price_threshold: Decimal = Field(5.0, ge=1.0, le=50.0, description="Minimum % change to trigger notification")
    currency: str = Field("USD", min_length=3, max_length=3, description="Price currency code")
    is_active: bool = Field(True, description="Whether tracking is currently enabled")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    @validator('origin_iata', 'destination_iata')
    def validate_iata_codes(cls, v):
        """Validate IATA airport codes."""
        if not v.isupper():
            raise ValueError("IATA codes must be uppercase")
        if not v.isalpha():
            raise ValueError("IATA codes must contain only letters")
        return v
    
    @validator('currency')
    def validate_currency_code(cls, v):
        """Validate currency code."""
        if not v.isupper():
            raise ValueError("Currency code must be uppercase")
        return v
    
    @validator('return_date')
    def validate_return_date(cls, v, values):
        """Validate return date is after departure date."""
        if v and 'departure_date' in values and v <= values['departure_date']:
            raise ValueError("Return date must be after departure date")
        return v
    
    @validator('departure_date')
    def validate_departure_date(cls, v):
        """Validate departure date is in the future."""
        if v <= date.today():
            raise ValueError("Departure date must be in the future")
        return v
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class FlightTrackingRequestCreate(BaseModel):
    """Schema for creating new tracking requests."""
    
    origin_iata: str = Field(..., min_length=3, max_length=3)
    destination_iata: str = Field(..., min_length=3, max_length=3)
    departure_date: date
    return_date: Optional[date] = None
    telegram_chat_id: int
    price_threshold: Decimal = Field(5.0, ge=1.0, le=50.0)
    currency: str = Field("USD", min_length=3, max_length=3)
    
    @validator('origin_iata', 'destination_iata', 'currency')
    def uppercase_codes(cls, v):
        """Convert codes to uppercase."""
        return v.upper() if v else v
    
    @validator('return_date')
    def validate_return_date(cls, v, values):
        """Validate return date is after departure date."""
        if v and 'departure_date' in values and v <= values['departure_date']:
            raise ValueError("Return date must be after departure date")
        return v
    
    @validator('departure_date')
    def validate_departure_date(cls, v):
        """Validate departure date is in the future."""
        if v <= date.today():
            raise ValueError("Departure date must be in the future")
        return v


class FlightTrackingRequestUpdate(BaseModel):
    """Schema for updating tracking requests."""
    
    price_threshold: Optional[Decimal] = Field(None, ge=1.0, le=50.0)
    is_active: Optional[bool] = None