"""PriceHistory model with relationships."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, String, DateTime, Numeric, Text, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from pydantic import BaseModel, Field, validator

Base = declarative_base()


class PriceHistoryDB(Base):
    """Database model for historical price data."""
    
    __tablename__ = "price_history"
    
    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign key
    tracking_request_id = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("flight_tracking_requests.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Price data
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    source_data = Column(JSONB, nullable=True)
    booking_url = Column(Text, nullable=True)
    
    # Timing
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships - removed to avoid circular imports in initial setup
    
    # Table constraints
    __table_args__ = (
        # Performance indexes
        Index("idx_price_history_request", "tracking_request_id", "checked_at"),
        Index("idx_price_history_time", "checked_at"),
        
        # Check constraints
        CheckConstraint("price > 0", name="ck_price_positive"),
        CheckConstraint("checked_at <= CURRENT_TIMESTAMP", name="ck_checked_at_not_future"),
    )
    
    @validates('price')
    def validate_price(self, key, value):
        """Validate price is positive."""
        if value <= 0:
            raise ValueError("Price must be positive")
        return value
    
    @validates('currency')
    def validate_currency(self, key, value):
        """Validate currency code."""
        if not value or len(value) != 3:
            raise ValueError("Currency must be exactly 3 characters")
        if not value.isupper():
            raise ValueError("Currency must be uppercase")
        return value
    
    @validates('checked_at')
    def validate_checked_at(self, key, value):
        """Validate checked_at is not in the future."""
        if value > datetime.utcnow():
            raise ValueError("checked_at cannot be in the future")
        return value
    
    def __repr__(self):
        return f"<PriceHistory(tracking_id={self.tracking_request_id}, price={self.price}, checked_at={self.checked_at})>"


class PriceHistorySchema(BaseModel):
    """Pydantic schema for price history API responses."""
    
    id: UUID
    tracking_request_id: UUID
    price: Decimal = Field(..., gt=0, description="Flight price at check time")
    currency: str = Field(..., min_length=3, max_length=3, description="Price currency code")
    source_data: Optional[Dict[str, Any]] = Field(None, description="Raw response from flight API")
    booking_url: Optional[str] = Field(None, description="Direct booking link")
    checked_at: datetime = Field(..., description="When this price was recorded")
    
    @validator('currency')
    def validate_currency_code(cls, v):
        """Validate currency code."""
        if not v.isupper():
            raise ValueError("Currency code must be uppercase")
        return v
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class PriceHistoryCreate(BaseModel):
    """Schema for creating price history entries."""
    
    tracking_request_id: UUID
    price: Decimal = Field(..., gt=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    source_data: Optional[Dict[str, Any]] = None
    booking_url: Optional[str] = None
    
    @validator('currency')
    def uppercase_currency(cls, v):
        """Convert currency to uppercase."""
        return v.upper() if v else v


class PriceHistoryResponse(BaseModel):
    """Schema for price history list responses."""
    
    prices: list[PriceHistorySchema]
    request_id: UUID
    total_count: int
    page: Optional[int] = None
    limit: Optional[int] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }