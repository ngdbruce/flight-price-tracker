"""
Task retry logic and error handling utilities.

This module provides common utilities for Celery task error handling,
retry strategies, and monitoring task execution.
"""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Union
from functools import wraps
from enum import Enum

from celery import Task
from celery.exceptions import Retry, MaxRetriesExceededError

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Classification of error severity levels."""
    LOW = "low"          # Transient errors, safe to retry
    MEDIUM = "medium"    # API errors, may need backoff
    HIGH = "high"        # Data errors, manual intervention may be needed
    CRITICAL = "critical"  # System errors, immediate attention required


class TaskError(Exception):
    """Custom exception for task-specific errors."""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 retry_after: Optional[int] = None, context: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.retry_after = retry_after  # Seconds to wait before retry
        self.context = context or {}


class RetryStrategy:
    """Defines retry strategies for different types of tasks."""
    
    # Default retry settings
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_COUNTDOWN = 60
    
    # Strategy configurations
    STRATEGIES = {
        "api_call": {
            "max_retries": 5,
            "countdown": lambda retry_count: min(60 * (2 ** retry_count), 300),  # Exponential backoff, max 5 min
            "retry_on": [ConnectionError, TimeoutError, "5xx_http_errors"]
        },
        "database": {
            "max_retries": 3,
            "countdown": lambda retry_count: 30 * (retry_count + 1),  # Linear backoff
            "retry_on": ["connection_errors", "timeout_errors"]
        },
        "notification": {
            "max_retries": 3,
            "countdown": lambda retry_count: 60 * (retry_count + 1),  # Linear backoff
            "retry_on": ["telegram_api_errors", "network_errors"]
        },
        "price_check": {
            "max_retries": 2,
            "countdown": lambda retry_count: 120,  # Fixed 2-minute delay
            "retry_on": ["flight_api_errors", "rate_limit_errors"]
        },
        "critical": {
            "max_retries": 1,
            "countdown": lambda retry_count: 300,  # 5-minute delay
            "retry_on": ["system_errors"]
        }
    }


def get_retry_countdown(strategy: str, retry_count: int) -> int:
    """
    Calculate retry countdown based on strategy and attempt count.
    
    Args:
        strategy: Name of retry strategy
        retry_count: Current retry attempt (0-based)
        
    Returns:
        int: Seconds to wait before retry
    """
    strategy_config = RetryStrategy.STRATEGIES.get(strategy, {})
    countdown_func = strategy_config.get("countdown")
    
    if callable(countdown_func):
        return countdown_func(retry_count)
    elif isinstance(countdown_func, int):
        return countdown_func
    else:
        return RetryStrategy.DEFAULT_COUNTDOWN


def should_retry_error(error: Exception, strategy: str) -> bool:
    """
    Determine if an error should trigger a retry.
    
    Args:
        error: The exception that occurred
        strategy: Name of retry strategy
        
    Returns:
        bool: True if the error should trigger a retry
    """
    strategy_config = RetryStrategy.STRATEGIES.get(strategy, {})
    retry_on = strategy_config.get("retry_on", [])
    
    # Check if error type is in retry list
    error_type = type(error).__name__
    if error_type in retry_on or type(error) in retry_on:
        return True
    
    # Check for specific error patterns
    error_message = str(error).lower()
    
    if "connection" in error_message and "connection_errors" in retry_on:
        return True
    if "timeout" in error_message and "timeout_errors" in retry_on:
        return True
    if "rate limit" in error_message and "rate_limit_errors" in retry_on:
        return True
    if "5xx" in error_message and "5xx_http_errors" in retry_on:
        return True
    
    return False


def retry_task_on_error(strategy: str = "default"):
    """
    Decorator for automatic task retry with error handling.
    
    Args:
        strategy: Name of retry strategy to use
        
    Usage:
        @retry_task_on_error("api_call")
        @celery_app.task(bind=True)
        def my_task(self, param1, param2):
            # Task implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Task, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                # Log the error with context
                error_context = {
                    "task_name": self.name,
                    "task_id": self.request.id,
                    "retry_count": self.request.retries,
                    "args": args,
                    "kwargs": kwargs,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)
                }
                
                logger.error(f"Task {self.name} failed: {exc}", extra=error_context)
                
                # Check if we should retry
                if should_retry_error(exc, strategy):
                    max_retries = RetryStrategy.STRATEGIES.get(strategy, {}).get(
                        "max_retries", RetryStrategy.DEFAULT_MAX_RETRIES
                    )
                    
                    if self.request.retries < max_retries:
                        countdown = get_retry_countdown(strategy, self.request.retries)
                        
                        logger.info(
                            f"Retrying task {self.name} in {countdown} seconds "
                            f"(attempt {self.request.retries + 1}/{max_retries})"
                        )
                        
                        raise self.retry(exc=exc, countdown=countdown)
                
                # Log final failure
                logger.error(
                    f"Task {self.name} failed permanently after {self.request.retries} retries",
                    extra=error_context
                )
                raise exc
                
        return wrapper
    return decorator


def log_task_execution(include_args: bool = False, include_result: bool = False):
    """
    Decorator for logging task execution details.
    
    Args:
        include_args: Whether to log task arguments
        include_result: Whether to log task result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Task, *args, **kwargs):
            start_time = datetime.utcnow()
            
            log_context = {
                "task_name": self.name,
                "task_id": self.request.id,
                "start_time": start_time.isoformat()
            }
            
            if include_args:
                log_context.update({"args": args, "kwargs": kwargs})
            
            logger.info(f"Starting task {self.name}", extra=log_context)
            
            try:
                result = func(self, *args, **kwargs)
                
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                log_context.update({
                    "end_time": end_time.isoformat(),
                    "duration_seconds": duration,
                    "status": "success"
                })
                
                if include_result:
                    log_context["result"] = result
                
                logger.info(f"Task {self.name} completed successfully", extra=log_context)
                return result
                
            except Exception as exc:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                log_context.update({
                    "end_time": end_time.isoformat(),
                    "duration_seconds": duration,
                    "status": "failed",
                    "error": str(exc),
                    "traceback": traceback.format_exc()
                })
                
                logger.error(f"Task {self.name} failed", extra=log_context)
                raise
                
        return wrapper
    return decorator


class TaskMonitor:
    """Monitor and track task execution metrics."""
    
    def __init__(self):
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "avg_execution_time": 0,
            "last_execution": None
        }
    
    def record_execution(self, task_name: str, duration: float, success: bool):
        """Record task execution metrics."""
        self.metrics["total_executions"] += 1
        self.metrics["last_execution"] = datetime.utcnow()
        
        if success:
            self.metrics["successful_executions"] += 1
        else:
            self.metrics["failed_executions"] += 1
        
        # Update average execution time
        current_avg = self.metrics["avg_execution_time"]
        total_count = self.metrics["total_executions"]
        self.metrics["avg_execution_time"] = (
            (current_avg * (total_count - 1) + duration) / total_count
        )
        
        logger.info(f"Task metrics updated for {task_name}: {self.metrics}")
    
    def get_success_rate(self) -> float:
        """Calculate task success rate."""
        if self.metrics["total_executions"] == 0:
            return 0.0
        return self.metrics["successful_executions"] / self.metrics["total_executions"]


# Global task monitor instance
task_monitor = TaskMonitor()


def handle_task_failure(task_name: str, error: Exception, context: Dict[str, Any]):
    """
    Handle task failure with appropriate logging and alerting.
    
    Args:
        task_name: Name of the failed task
        error: Exception that caused the failure
        context: Additional context about the failure
    """
    failure_info = {
        "task_name": task_name,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
        "context": context
    }
    
    # Determine error severity
    if isinstance(error, TaskError):
        severity = error.severity
    elif "database" in str(error).lower():
        severity = ErrorSeverity.HIGH
    elif "connection" in str(error).lower():
        severity = ErrorSeverity.MEDIUM
    else:
        severity = ErrorSeverity.LOW
    
    failure_info["severity"] = severity
    
    # Log failure
    log_level = {
        ErrorSeverity.LOW: logging.WARNING,
        ErrorSeverity.MEDIUM: logging.ERROR,
        ErrorSeverity.HIGH: logging.ERROR,
        ErrorSeverity.CRITICAL: logging.CRITICAL
    }[severity]
    
    logger.log(log_level, f"Task failure: {task_name}", extra=failure_info)
    
    # For critical errors, additional alerting could be implemented here
    if severity == ErrorSeverity.CRITICAL:
        # Send alert to monitoring system, Slack, etc.
        pass


def create_task_with_retry(celery_app, strategy: str = "default"):
    """
    Factory function to create Celery tasks with built-in retry logic.
    
    Args:
        celery_app: Celery application instance
        strategy: Retry strategy name
        
    Returns:
        Decorator function for creating tasks
    """
    def task_decorator(**task_kwargs):
        def decorator(func):
            # Apply retry and logging decorators
            func = retry_task_on_error(strategy)(func)
            func = log_task_execution(include_args=True)(func)
            
            # Create Celery task with bind=True
            return celery_app.task(bind=True, **task_kwargs)(func)
        return decorator
    return task_decorator


# Utility functions for common task patterns
def safe_task_execution(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    """
    Execute a function safely with error handling and result tracking.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        dict: Execution result with status and data/error info
    """
    try:
        start_time = datetime.utcnow()
        result = func(*args, **kwargs)
        end_time = datetime.utcnow()
        
        return {
            "status": "success",
            "result": result,
            "execution_time": (end_time - start_time).total_seconds(),
            "timestamp": end_time.isoformat()
        }
    except Exception as exc:
        end_time = datetime.utcnow()
        
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "timestamp": end_time.isoformat()
        }