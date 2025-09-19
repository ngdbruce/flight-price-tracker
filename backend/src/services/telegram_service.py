"""Telegram Bot service for notifications."""

import os
import httpx
import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of messages to send."""
    TRACKING_STARTED = "tracking_started"
    PRICE_CHANGE = "price_change"
    PRICE_DROP = "price_drop"
    PRICE_INCREASE = "price_increase"
    TRACKING_EXPIRED = "tracking_expired"
    ERROR = "error"


@dataclass
class TelegramMessage:
    """Telegram message data."""
    chat_id: int
    text: str
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = True


@dataclass
class NotificationContext:
    """Context for generating notifications."""
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    old_price: Optional[Decimal] = None
    new_price: Optional[Decimal] = None
    currency: str = "USD"
    booking_url: Optional[str] = None
    tracking_id: Optional[str] = None


class TelegramAPIError(Exception):
    """Custom exception for Telegram API errors."""
    pass


class TelegramService:
    """Service for sending notifications via Telegram Bot API."""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        
        # Use mock mode if no bot token configured
        self.use_mock_mode = not self.bot_token
        if self.use_mock_mode:
            logger.warning("No Telegram bot token found, using mock mode")
    
    async def send_message(self, message: TelegramMessage) -> Dict[str, Any]:
        """
        Send a message via Telegram Bot API.
        
        Args:
            message: TelegramMessage to send
            
        Returns:
            Dict containing message_id and status
        """
        if self.use_mock_mode:
            return await self._send_mock_message(message)
        
        if not self.bot_token:
            raise TelegramAPIError("Telegram bot token not configured")
        
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": message.chat_id,
            "text": message.text,
            "parse_mode": message.parse_mode,
            "disable_web_page_preview": message.disable_web_page_preview
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                if data["ok"]:
                    return {
                        "success": True,
                        "message_id": data["result"]["message_id"],
                        "status": "sent"
                    }
                else:
                    raise TelegramAPIError(f"Telegram API error: {data.get('description', 'Unknown error')}")
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending Telegram message: {e}")
            raise TelegramAPIError(f"Failed to send message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            raise TelegramAPIError(f"Message sending failed: {e}")
    
    async def _send_mock_message(self, message: TelegramMessage) -> Dict[str, Any]:
        """Send mock message for testing."""
        import asyncio
        import random
        
        # Simulate API delay
        await asyncio.sleep(0.1)
        
        logger.info(f"MOCK TELEGRAM: Sending to chat {message.chat_id}: {message.text}")
        
        return {
            "success": True,
            "message_id": random.randint(1000, 9999),
            "status": "sent",
            "mock": True
        }
    
    def create_tracking_started_message(self, context: NotificationContext) -> TelegramMessage:
        """Create message for when tracking starts."""
        route = f"{context.origin} → {context.destination}"
        date_info = context.departure_date
        if context.return_date:
            date_info += f" (return {context.return_date})"
        
        text = (
            f"✈️ <b>Flight Tracking Started</b>\n\n"
            f"📍 Route: <b>{route}</b>\n"
            f"📅 Date: <b>{date_info}</b>\n"
            f"💰 Currency: <b>{context.currency}</b>\n\n"
            f"I'll notify you when prices change significantly!\n"
            f"🔍 Tracking ID: <code>{context.tracking_id}</code>"
        )
        
        return TelegramMessage(
            chat_id=0,  # Will be set by caller
            text=text
        )
    
    def create_price_change_message(self, context: NotificationContext, message_type: MessageType) -> TelegramMessage:
        """Create message for price changes."""
        route = f"{context.origin} → {context.destination}"
        
        if message_type == MessageType.PRICE_DROP:
            emoji = "📉"
            trend = "dropped"
            color = "🟢"
        elif message_type == MessageType.PRICE_INCREASE:
            emoji = "📈"
            trend = "increased"
            color = "🔴"
        else:
            emoji = "💰"
            trend = "changed"
            color = "🟡"
        
        # Calculate percentage change
        percentage_change = ""
        if context.old_price and context.new_price:
            change = ((context.new_price - context.old_price) / context.old_price) * 100
            percentage_change = f" ({change:+.1f}%)"
        
        text = (
            f"{emoji} <b>Price Alert</b> {color}\n\n"
            f"📍 Route: <b>{route}</b>\n"
            f"📅 Date: <b>{context.departure_date}</b>\n\n"
        )
        
        if context.old_price and context.new_price:
            text += (
                f"💰 Price {trend}:\n"
                f"   • Was: <b>{context.old_price:.2f} {context.currency}</b>\n"
                f"   • Now: <b>{context.new_price:.2f} {context.currency}</b>\n"
                f"   • Change: <b>{percentage_change}</b>\n\n"
            )
        
        if context.booking_url:
            text += f"🔗 <a href='{context.booking_url}'>Book this flight</a>\n\n"
        
        text += f"🔍 Tracking ID: <code>{context.tracking_id}</code>"
        
        return TelegramMessage(
            chat_id=0,  # Will be set by caller
            text=text
        )
    
    def create_tracking_expired_message(self, context: NotificationContext) -> TelegramMessage:
        """Create message for when tracking expires."""
        route = f"{context.origin} → {context.destination}"
        
        text = (
            f"⏰ <b>Tracking Expired</b>\n\n"
            f"📍 Route: <b>{route}</b>\n"
            f"📅 Date: <b>{context.departure_date}</b>\n\n"
            f"Flight tracking has ended as the departure date has passed.\n\n"
            f"🔍 Tracking ID: <code>{context.tracking_id}</code>"
        )
        
        return TelegramMessage(
            chat_id=0,  # Will be set by caller
            text=text
        )
    
    def create_error_message(self, context: NotificationContext, error_details: str) -> TelegramMessage:
        """Create message for errors."""
        route = f"{context.origin} → {context.destination}"
        
        text = (
            f"⚠️ <b>Tracking Error</b>\n\n"
            f"📍 Route: <b>{route}</b>\n"
            f"📅 Date: <b>{context.departure_date}</b>\n\n"
            f"❌ Error: {error_details}\n\n"
            f"Tracking will continue automatically.\n"
            f"🔍 Tracking ID: <code>{context.tracking_id}</code>"
        )
        
        return TelegramMessage(
            chat_id=0,  # Will be set by caller
            text=text
        )
    
    async def send_tracking_started_notification(self, chat_id: int, context: NotificationContext) -> Dict[str, Any]:
        """Send tracking started notification."""
        message = self.create_tracking_started_message(context)
        message.chat_id = chat_id
        return await self.send_message(message)
    
    async def send_price_change_notification(self, chat_id: int, context: NotificationContext, 
                                          message_type: MessageType = MessageType.PRICE_CHANGE) -> Dict[str, Any]:
        """Send price change notification."""
        message = self.create_price_change_message(context, message_type)
        message.chat_id = chat_id
        return await self.send_message(message)
    
    async def send_tracking_expired_notification(self, chat_id: int, context: NotificationContext) -> Dict[str, Any]:
        """Send tracking expired notification."""
        message = self.create_tracking_expired_message(context)
        message.chat_id = chat_id
        return await self.send_message(message)
    
    async def send_error_notification(self, chat_id: int, context: NotificationContext, 
                                    error_details: str) -> Dict[str, Any]:
        """Send error notification."""
        message = self.create_error_message(context, error_details)
        message.chat_id = chat_id
        return await self.send_message(message)
    
    async def check_bot_health(self) -> Dict[str, Any]:
        """Check if the bot is working properly."""
        if self.use_mock_mode:
            return {
                "status": "healthy",
                "message": "Mock mode - bot simulation active",
                "response_time": "< 10ms"
            }
        
        if not self.bot_token:
            return {
                "status": "unhealthy",
                "message": "Bot token not configured",
                "response_time": None
            }
        
        try:
            url = f"{self.base_url}/getMe"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                data = response.json()
                if data["ok"]:
                    bot_info = data["result"]
                    return {
                        "status": "healthy",
                        "message": f"Bot '{bot_info['first_name']}' is active",
                        "response_time": "< 100ms",
                        "bot_username": bot_info.get("username")
                    }
                else:
                    return {
                        "status": "unhealthy", 
                        "message": f"Bot API error: {data.get('description', 'Unknown error')}",
                        "response_time": None
                    }
        
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Bot health check failed: {e}",
                "response_time": None
            }


# Global service instance
telegram_service = TelegramService()