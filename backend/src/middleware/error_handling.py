"""Error handling middleware and custom exceptions."""

import logging
import traceback
from typing import Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.config import settings

# Optional Sentry integration
try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

logger = logging.getLogger(__name__)


# Custom exceptions
class FlightTrackerError(Exception):
    """Base exception for Flight Tracker application."""
    
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code or "FLIGHT_TRACKER_ERROR"
        super().__init__(self.message)


class ValidationError(FlightTrackerError):
    """Exception for validation errors."""
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class ExternalServiceError(FlightTrackerError):
    """Exception for external service errors."""
    
    def __init__(self, message: str, service: str = None, status_code: int = None):
        self.service = service
        self.status_code = status_code
        super().__init__(message, "EXTERNAL_SERVICE_ERROR")


class DatabaseError(FlightTrackerError):
    """Exception for database operations."""
    
    def __init__(self, message: str, operation: str = None):
        self.operation = operation
        super().__init__(message, "DATABASE_ERROR")


class AuthenticationError(FlightTrackerError):
    """Exception for authentication errors."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(FlightTrackerError):
    """Exception for authorization errors."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, "AUTHORIZATION_ERROR")


class RateLimitError(FlightTrackerError):
    """Exception for rate limiting."""
    
    def __init__(self, message: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message, "RATE_LIMIT_ERROR")


class BusinessLogicError(FlightTrackerError):
    """Exception for business logic violations."""
    
    def __init__(self, message: str, rule: str = None):
        self.rule = rule
        super().__init__(message, "BUSINESS_LOGIC_ERROR")


# Error handling middleware
class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive error handling and logging."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with error handling."""
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self._handle_exception(request, exc)
    
    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle different types of exceptions."""
        
        # Log the exception
        await self._log_exception(request, exc)
        
        # Send to Sentry if configured
        if SENTRY_AVAILABLE and settings.app.sentry_dsn:
            sentry_sdk.capture_exception(exc)
        
        # Handle specific exception types
        if isinstance(exc, HTTPException):
            return await self._handle_http_exception(request, exc)
        elif isinstance(exc, ValidationError):
            return await self._handle_validation_error(request, exc)
        elif isinstance(exc, ExternalServiceError):
            return await self._handle_external_service_error(request, exc)
        elif isinstance(exc, DatabaseError):
            return await self._handle_database_error(request, exc)
        elif isinstance(exc, AuthenticationError):
            return await self._handle_authentication_error(request, exc)
        elif isinstance(exc, AuthorizationError):
            return await self._handle_authorization_error(request, exc)
        elif isinstance(exc, RateLimitError):
            return await self._handle_rate_limit_error(request, exc)
        elif isinstance(exc, BusinessLogicError):
            return await self._handle_business_logic_error(request, exc)
        elif isinstance(exc, FlightTrackerError):
            return await self._handle_flight_tracker_error(request, exc)
        else:
            return await self._handle_unexpected_error(request, exc)
    
    async def _log_exception(self, request: Request, exc: Exception):
        """Log exception with context."""
        error_id = f"{request.method}_{request.url.path}_{id(exc)}"
        
        context = {
            "error_id": error_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", "Unknown"),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }
        
        if isinstance(exc, (ValidationError, BusinessLogicError)):
            logger.warning(f"Client error: {exc}", extra=context)
        elif isinstance(exc, (AuthenticationError, AuthorizationError)):
            logger.warning(f"Security error: {exc}", extra=context)
        elif isinstance(exc, ExternalServiceError):
            logger.error(f"External service error: {exc}", extra=context)
        elif isinstance(exc, DatabaseError):
            logger.error(f"Database error: {exc}", extra=context)
        else:
            logger.error(f"Unexpected error: {exc}", extra=context, exc_info=True)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exc.detail,
                    "status_code": exc.status_code
                }
            }
        )
    
    async def _handle_validation_error(self, request: Request, exc: ValidationError) -> JSONResponse:
        """Handle validation errors."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "field": exc.field
                }
            }
        )
    
    async def _handle_external_service_error(self, request: Request, exc: ExternalServiceError) -> JSONResponse:
        """Handle external service errors."""
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": "External service temporarily unavailable",
                    "service": exc.service,
                    "retry_after": 30
                }
            }
        )
    
    async def _handle_database_error(self, request: Request, exc: DatabaseError) -> JSONResponse:
        """Handle database errors."""
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": "Service temporarily unavailable",
                    "retry_after": 10
                }
            }
        )
    
    async def _handle_authentication_error(self, request: Request, exc: AuthenticationError) -> JSONResponse:
        """Handle authentication errors."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message
                }
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    async def _handle_authorization_error(self, request: Request, exc: AuthorizationError) -> JSONResponse:
        """Handle authorization errors."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message
                }
            }
        )
    
    async def _handle_rate_limit_error(self, request: Request, exc: RateLimitError) -> JSONResponse:
        """Handle rate limit errors."""
        headers = {}
        if exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "retry_after": exc.retry_after
                }
            },
            headers=headers
        )
    
    async def _handle_business_logic_error(self, request: Request, exc: BusinessLogicError) -> JSONResponse:
        """Handle business logic errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "rule": exc.rule
                }
            }
        )
    
    async def _handle_flight_tracker_error(self, request: Request, exc: FlightTrackerError) -> JSONResponse:
        """Handle generic flight tracker errors."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message
                }
            }
        )
    
    async def _handle_unexpected_error(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        error_message = "Internal server error"
        error_details = None
        
        if settings.app.debug:
            error_message = str(exc)
            error_details = {
                "type": type(exc).__name__,
                "traceback": traceback.format_exc().split("\n")
            }
        
        content = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": error_message
            }
        }
        
        if error_details:
            content["error"]["details"] = error_details
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content
        )


# Error response builder
class ErrorResponseBuilder:
    """Builder for consistent error responses."""
    
    @staticmethod
    def validation_error(message: str, field: str = None, errors: Dict = None) -> Dict[str, Any]:
        """Build validation error response."""
        response = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message
            }
        }
        
        if field:
            response["error"]["field"] = field
        
        if errors:
            response["error"]["details"] = errors
        
        return response
    
    @staticmethod
    def not_found_error(resource: str, resource_id: str = None) -> Dict[str, Any]:
        """Build not found error response."""
        message = f"{resource} not found"
        if resource_id:
            message += f" with ID: {resource_id}"
        
        return {
            "error": {
                "code": "NOT_FOUND",
                "message": message,
                "resource": resource,
                "resource_id": resource_id
            }
        }
    
    @staticmethod
    def conflict_error(message: str, resource: str = None) -> Dict[str, Any]:
        """Build conflict error response."""
        response = {
            "error": {
                "code": "CONFLICT",
                "message": message
            }
        }
        
        if resource:
            response["error"]["resource"] = resource
        
        return response
    
    @staticmethod
    def service_unavailable_error(service: str, retry_after: int = None) -> Dict[str, Any]:
        """Build service unavailable error response."""
        response = {
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": f"{service} service is temporarily unavailable",
                "service": service
            }
        }
        
        if retry_after:
            response["error"]["retry_after"] = retry_after
        
        return response


# Health check for error handling system
async def health_check_error_handling() -> Dict[str, Any]:
    """Perform health check for error handling system."""
    try:
        # Test error logging
        test_logger = logging.getLogger("test_error_handling")
        test_logger.info("Error handling health check")
        
        return {
            "status": "healthy",
            "message": "Error handling system operational",
            "sentry_enabled": bool(settings.app.sentry_dsn),
            "debug_mode": settings.app.debug
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Error handling system issues: {str(e)}"
        }