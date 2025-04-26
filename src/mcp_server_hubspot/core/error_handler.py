"""
Error handling utilities for HubSpot API interactions.
"""
import logging
import json
import functools
from typing import Any, Callable

from hubspot.crm.contacts.exceptions import ApiException

logger = logging.getLogger('mcp_hubspot_client.error_handler')

def handle_hubspot_errors(func: Callable) -> Callable:
    """Decorator to handle HubSpot API errors consistently.
    
    Args:
        func: Function to wrap with error handling
        
    Returns:
        Wrapped function with error handling
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            logger.error(f"API Exception in {func.__name__}: {str(e)}")
            return json.dumps({"error": str(e)})
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {str(e)}")
            return json.dumps({"error": str(e)})
    return wrapper
