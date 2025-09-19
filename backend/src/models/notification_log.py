"""NotificationLog model for audit trail."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum
from sqlalchemy import (
    Column, String, DateTime, Numeric, Text, ForeignKey, BigInteger, Integer,
    Index, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from pydantic import BaseModel, Field, validator

Base = declarative_base()


class NotificationType(str, Enum):
    """Types of notifications that can be sent."""
    PRICE_CHANGE = "price_change"
    TRACKING_STARTED = "tracking_started"
    TRACKING_STOPPED = "tracking_stopped"
    ERROR = "error"
    EXPIRY_WARNING = "expiry_warning"


class NotificationStatus(str, Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"


class NotificationLogDB(Base):
    """Database model for notification audit trail."""
    
    __tablename__ = "notification_log"
    
    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign key
    tracking_request_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("flight_tracking_requests.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Notification details
    notification_type = Column(
        SQLEnum(NotificationType, name="notification_type_enum"),
        nullable=False
    )
    old_price = Column(Numeric(10, 2), nullable=True)
    new_price = Column(Numeric(10, 2), nullable=True)
    message_content = Column(Text, nullable=False)
    
    # Telegram delivery details
    telegram_message_id = Column(BigInteger, nullable=True)
    
    # Status and timing
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(
        SQLEnum(NotificationStatus, name="notification_status_enum"),
        nullable=False,
        default=NotificationStatus.PENDING
    )
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    
    # Relationships - removed to avoid circular imports in initial setup
    
    # Table constraints
    __table_args__ = (
        # Performance indexes
        Index("idx_notifications_request", "tracking_request_id", "sent_at"),
        Index("idx_notifications_status", "status", "sent_at"),
        Index("idx_notifications_type", "notification_type", "sent_at"),
        
        # Check constraints
        CheckConstraint("old_price > 0 OR old_price IS NULL", name="ck_old_price_positive"),
        CheckConstraint("new_price > 0 OR new_price IS NULL", name="ck_new_price_positive"),
        CheckConstraint("retry_count >= 0", name="ck_retry_count_non_negative"),
        CheckConstraint("sent_at <= CURRENT_TIMESTAMP", name="ck_sent_at_not_future"),
        CheckConstraint(
            "notification_type != 'price_change' OR (old_price IS NOT NULL AND new_price IS NOT NULL)",
            name="ck_price_change_requires_prices"
        ),
    )
    
    @validates('old_price', 'new_price')
    def validate_prices(self, key, value):
        """Validate prices are positive."""
        if value is not None and value <= 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @validates('sent_at')
    def validate_sent_at(self, key, value):
        """Validate sent_at is not in the future."""
        if value > datetime.utcnow():
            raise ValueError("sent_at cannot be in the future")
        return value
    
    @validates('message_content')
    def validate_message_content(self, key, value):
        """Validate message content is not empty."""
        if not value or not value.strip():
            raise ValueError("Message content cannot be empty")
        return value.strip()
    
    def __repr__(self):
        return f"<NotificationLog(type={self.notification_type}, status={self.status}, sent_at={self.sent_at})>"


class NotificationLogSchema(BaseModel):
    """Pydantic schema for notification log API responses."""
    
    id: UUID
    tracking_request_id: UUID
    notification_type: NotificationType
    old_price: Optional[Decimal] = Field(None, description="Previous price for price_change notifications")
    new_price: Optional[Decimal] = Field(None, description="New price for price_change notifications")
    message_content: str = Field(..., description="Full notification message sent")
    telegram_message_id: Optional[int] = Field(None, description="Telegram message ID if sent successfully")
    sent_at: datetime = Field(..., description="When notification was sent")
    status: NotificationStatus = Field(..., description="Delivery status")
    error_message: Optional[str] = Field(None, description="Error details if delivery failed")
    retry_count: int = Field(0, description="Number of retry attempts")
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class NotificationLogCreate(BaseModel):
    """Schema for creating notification log entries."""
    
    tracking_request_id: UUID
    notification_type: NotificationType
    old_price: Optional[Decimal] = Field(None, gt=0)
    new_price: Optional[Decimal] = Field(None, gt=0)
    message_content: str = Field(..., min_length=1)
    telegram_message_id: Optional[int] = None
    status: NotificationStatus = NotificationStatus.PENDING
    error_message: Optional[str] = None
    
    @validator('message_content')
    def validate_message_content(cls, v):
        """Validate message content is not empty."""
        if not v.strip():
            raise ValueError("Message content cannot be empty")
        return v.strip()
    
    @validator('new_price', 'old_price')
    def validate_prices_for_price_change(cls, v, values):
        """Validate that price_change notifications have both old and new prices."""
        if 'notification_type' in values and values['notification_type'] == NotificationType.PRICE_CHANGE:
            if 'old_price' in values and 'new_price' in values:
                if values['old_price'] is None or values.get('new_price') is None:
                    raise ValueError("Price change notifications require both old_price and new_price")
        return v


class NotificationLogUpdate(BaseModel):
    """Schema for updating notification log entries."""
    
    telegram_message_id: Optional[int] = None
    status: Optional[NotificationStatus] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = Field(None, ge=0)