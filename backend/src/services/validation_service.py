"""Validation service for IATA codes and input data."""

import re
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class ValidationService:
    """Service for validating IATA codes, dates, and other input data."""
    
    def __init__(self):
        # Common IATA airport codes (in production, this would be loaded from a database/API)
        self.known_iata_codes = {
            # US Major Airports
            "JFK", "LAX", "ORD", "DFW", "ATL", "LAS", "SEA", "SFO", "PHX", "CLT",
            "MIA", "EWR", "LGA", "IAD", "DCA", "BOS", "MSP", "DTW", "PHL", "BWI",
            "TPA", "SAN", "STL", "HNL", "PDX", "AUS", "RDU", "SLC", "MDW", "OAK",
            
            # International Major Airports
            "LHR", "CDG", "FRA", "AMS", "MAD", "FCO", "MUC", "ZUR", "VIE", "CPH",
            "ARN", "OSL", "HEL", "IST", "DOH", "DXB", "SIN", "NRT", "ICN", "PVG",
            "PEK", "HKG", "BKK", "KUL", "SYD", "MEL", "YYZ", "YVR", "GRU", "EZE",
            
            # Additional codes for testing
            "DEN", "CLE", "MCI", "OMA", "MSY", "JAX", "IND", "CMH", "MKE", "BNA"
        }
        
        # Regex pattern for IATA code format
        self.iata_pattern = re.compile(r'^[A-Z]{3}$')
        
        # Regex pattern for currency codes
        self.currency_pattern = re.compile(r'^[A-Z]{3}$')
        
        # Known currency codes
        self.known_currencies = {
            "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "SEK", "NOK",
            "DKK", "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "RUB", "TRY", "BRL",
            "MXN", "ARS", "CLP", "COP", "PEN", "UYU", "KRW", "TWD", "HKD", "SGD",
            "THB", "MYR", "IDR", "PHP", "VND", "INR", "PKR", "BDT", "LKR", "NPR"
        }
    
    def validate_iata_code(self, code: str, allow_unknown: bool = True) -> ValidationResult:
        """
        Validate IATA airport code.
        
        Args:
            code: IATA airport code to validate
            allow_unknown: If True, allow codes not in known list
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        if not code:
            errors.append("IATA code is required")
            return ValidationResult(False, errors, warnings)
        
        if not isinstance(code, str):
            errors.append("IATA code must be a string")
            return ValidationResult(False, errors, warnings)
        
        # Check format
        if not self.iata_pattern.match(code):
            if len(code) != 3:
                errors.append("IATA code must be exactly 3 characters")
            elif not code.isupper():
                errors.append("IATA code must be uppercase")
            elif not code.isalpha():
                errors.append("IATA code must contain only letters")
            else:
                errors.append("Invalid IATA code format")
            
            return ValidationResult(False, errors, warnings)
        
        # Check against known codes
        if code not in self.known_iata_codes:
            if allow_unknown:
                warnings.append(f"IATA code '{code}' not in known airport list")
            else:
                errors.append(f"Unknown IATA airport code: {code}")
                return ValidationResult(False, errors, warnings)
        
        return ValidationResult(True, [], warnings)
    
    def validate_route(self, origin: str, destination: str) -> ValidationResult:
        """
        Validate flight route (origin and destination).
        
        Args:
            origin: Origin IATA code
            destination: Destination IATA code
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        # Validate individual codes
        origin_result = self.validate_iata_code(origin)
        if not origin_result.is_valid:
            errors.extend([f"Origin: {error}" for error in origin_result.errors])
        warnings.extend([f"Origin: {warning}" for warning in origin_result.warnings])
        
        destination_result = self.validate_iata_code(destination)
        if not destination_result.is_valid:
            errors.extend([f"Destination: {error}" for error in destination_result.errors])
        warnings.extend([f"Destination: {warning}" for warning in destination_result.warnings])
        
        # Check if origin and destination are different
        if origin and destination and origin == destination:
            errors.append("Origin and destination cannot be the same")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)
    
    def validate_date_range(self, departure_date: date, return_date: Optional[date] = None) -> ValidationResult:
        """
        Validate flight date range.
        
        Args:
            departure_date: Departure date
            return_date: Return date (optional)
            
Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        today = date.today()
        
        # Validate departure date
        if not departure_date:
            errors.append("Departure date is required")
            return ValidationResult(False, errors, warnings)
        
        if not isinstance(departure_date, date):
            errors.append("Departure date must be a date object")
            return ValidationResult(False, errors, warnings)
        
        # Check if departure date is in the future
        if departure_date <= today:
            errors.append("Departure date must be in the future")
        
        # Check if departure date is too far in the future (1 year limit)
        max_future_date = today.replace(year=today.year + 1)
        if departure_date > max_future_date:
            warnings.append("Departure date is more than 1 year in the future")
        
        # Validate return date if provided
        if return_date:
            if not isinstance(return_date, date):
                errors.append("Return date must be a date object")
                return ValidationResult(False, errors, warnings)
            
            # Check if return date is after departure date
            if return_date <= departure_date:
                errors.append("Return date must be after departure date")
            
            # Check trip duration (warn if more than 30 days)
            if return_date and departure_date:
                trip_duration = (return_date - departure_date).days
                if trip_duration > 30:
                    warnings.append(f"Trip duration is {trip_duration} days (more than 30 days)")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)
    
    def validate_price_threshold(self, threshold: Decimal) -> ValidationResult:
        """
        Validate price change threshold percentage.
        
        Args:
            threshold: Price threshold percentage
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        if threshold is None:
            errors.append("Price threshold is required")
            return ValidationResult(False, errors, warnings)
        
        if not isinstance(threshold, (Decimal, int, float)):
            errors.append("Price threshold must be a number")
            return ValidationResult(False, errors, warnings)
        
        threshold = Decimal(str(threshold))
        
        # Check range
        if threshold < Decimal("1.0"):
            errors.append("Price threshold must be at least 1.0%")
        elif threshold > Decimal("50.0"):
            errors.append("Price threshold cannot exceed 50.0%")
        
        # Warnings for unusual values
        if threshold < Decimal("2.0"):
            warnings.append("Very low price threshold may result in many notifications")
        elif threshold > Decimal("20.0"):
            warnings.append("High price threshold may miss significant price changes")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)
    
    def validate_currency_code(self, currency: str) -> ValidationResult:
        """
        Validate currency code.
        
        Args:
            currency: ISO 4217 currency code
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        if not currency:
            errors.append("Currency code is required")
            return ValidationResult(False, errors, warnings)
        
        if not isinstance(currency, str):
            errors.append("Currency code must be a string")
            return ValidationResult(False, errors, warnings)
        
        # Check format
        if not self.currency_pattern.match(currency):
            if len(currency) != 3:
                errors.append("Currency code must be exactly 3 characters")
            elif not currency.isupper():
                errors.append("Currency code must be uppercase")
            else:
                errors.append("Invalid currency code format")
            
            return ValidationResult(False, errors, warnings)
        
        # Check against known currencies
        if currency not in self.known_currencies:
            warnings.append(f"Currency '{currency}' not in known currency list")
        
        return ValidationResult(True, [], warnings)
    
    def validate_telegram_chat_id(self, chat_id: int) -> ValidationResult:
        """
        Validate Telegram chat ID.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        if chat_id is None:
            errors.append("Telegram chat ID is required")
            return ValidationResult(False, errors, warnings)
        
        if not isinstance(chat_id, int):
            errors.append("Telegram chat ID must be an integer")
            return ValidationResult(False, errors, warnings)
        
        # Telegram chat IDs can be negative (groups) or positive (users)
        if chat_id == 0:
            errors.append("Telegram chat ID cannot be zero")
        
        # Check reasonable ranges (Telegram limits)
        if abs(chat_id) > 10**12:  # Telegram's theoretical limit
            errors.append("Telegram chat ID is out of valid range")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)
    
    def validate_tracking_request_data(self, data: dict) -> ValidationResult:
        """
        Validate complete tracking request data.
        
        Args:
            data: Dictionary with tracking request data
            
        Returns:
            ValidationResult with comprehensive validation
        """
        errors = []
        warnings = []
        
        # Required fields check
        required_fields = ["origin_iata", "destination_iata", "departure_date", "telegram_chat_id"]
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        if errors:  # If required fields are missing, stop here
            return ValidationResult(False, errors, warnings)
        
        try:
            # Validate route
            route_result = self.validate_route(data["origin_iata"], data["destination_iata"])
            if not route_result.is_valid:
                errors.extend(route_result.errors)
            warnings.extend(route_result.warnings)
            
            # Validate dates
            departure_date = data["departure_date"]
            return_date = data.get("return_date")
            
            if isinstance(departure_date, str):
                departure_date = datetime.fromisoformat(departure_date).date()
            if isinstance(return_date, str):
                return_date = datetime.fromisoformat(return_date).date()
            
            date_result = self.validate_date_range(departure_date, return_date)
            if not date_result.is_valid:
                errors.extend(date_result.errors)
            warnings.extend(date_result.warnings)
            
            # Validate Telegram chat ID
            chat_id_result = self.validate_telegram_chat_id(data["telegram_chat_id"])
            if not chat_id_result.is_valid:
                errors.extend(chat_id_result.errors)
            warnings.extend(chat_id_result.warnings)
            
            # Validate optional fields
            if "price_threshold" in data and data["price_threshold"] is not None:
                threshold_result = self.validate_price_threshold(data["price_threshold"])
                if not threshold_result.is_valid:
                    errors.extend(threshold_result.errors)
                warnings.extend(threshold_result.warnings)
            
            if "currency" in data and data["currency"]:
                currency_result = self.validate_currency_code(data["currency"])
                if not currency_result.is_valid:
                    errors.extend(currency_result.errors)
                warnings.extend(currency_result.warnings)
        
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)
    
    def get_known_iata_codes(self) -> Set[str]:
        """Get set of known IATA airport codes."""
        return self.known_iata_codes.copy()
    
    def get_known_currencies(self) -> Set[str]:
        """Get set of known currency codes."""
        return self.known_currencies.copy()
    
    def add_iata_code(self, code: str) -> bool:
        """
        Add a new IATA code to the known list.
        
        Args:
            code: IATA airport code to add
            
        Returns:
            True if added successfully
        """
        if not code or not isinstance(code, str) or len(code) != 3:
            return False
        
        code = code.upper()
        if self.iata_pattern.match(code):
            self.known_iata_codes.add(code)
            logger.info(f"Added IATA code: {code}")
            return True
        
        return False


# Global service instance
validation_service = ValidationService()