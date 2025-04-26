"""
HubSpot client module for MCP server integration.
Provides access to HubSpot API functionality through specialized client modules.
"""
import logging
import os
import json
import pathlib
from typing import Any, Dict, List, Optional, Literal

from hubspot import HubSpot
from hubspot.crm.contacts.exceptions import ApiException

from .core.storage import ThreadStorage
from .core.formatters import convert_datetime_fields
from .clients.company_client import CompanyClient
from .clients.contact_client import ContactClient
from .clients.conversation_client import ConversationClient
from .clients.ticket_client import TicketClient

# Re-export ApiException
__all__ = ["HubSpotClient", "ApiException"]

logger = logging.getLogger('mcp_hubspot_client')

class HubSpotClient:
    """Main HubSpot client that composes specialized clients for each domain."""
    
    def __init__(self, access_token: Optional[str] = None):
        """Initialize the HubSpot client with API credentials.
        
        Args:
            access_token: HubSpot API access token. If None, uses HUBSPOT_ACCESS_TOKEN env var
        """
        self.access_token = self._get_access_token(access_token)
        self.client = HubSpot(access_token=self.access_token)
        
        # Initialize storage
        storage_dir = pathlib.Path("storage")
        self.thread_storage = ThreadStorage(storage_dir)
        
        # Initialize domain-specific clients
        self.companies = CompanyClient(self.client, self.access_token)
        self.contacts = ContactClient(self.client, self.access_token)
        self.conversations = ConversationClient(self.client, self.access_token, self.thread_storage)
        self.tickets = TicketClient(self.client, self.access_token)
    
    def _get_access_token(self, access_token: Optional[str]) -> str:
        """Retrieve and validate the HubSpot access token.
        
        Args:
            access_token: Directly provided token or None
            
        Returns:
            Valid access token
            
        Raises:
            ValueError: If no valid token is available
        """
        token = access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
        logger.debug(f"Using access token: {'[MASKED]' if token else 'None'}")
        if not token:
            raise ValueError("HUBSPOT_ACCESS_TOKEN environment variable is required")
        return token
    
    # Method delegation to specialized clients
    def get_recent_companies(self, limit: int = 10) -> str:
        """Get most recently active companies from HubSpot.
        
        Args:
            limit: Maximum number of companies to return (default: 10)
            
        Returns:
            JSON string with company data
        """
        return self.companies.get_recent(limit)
        
    def get_company_activity(self, company_id: str) -> str:
        """Get activity history for a specific company.
        
        Args:
            company_id: HubSpot company ID
            
        Returns:
            JSON string with company activity data
        """
        return self.companies.get_activity(company_id)
    
    def get_recent_contacts(self, limit: int = 10) -> str:
        """Get most recently active contacts from HubSpot.
        
        Args:
            limit: Maximum number of contacts to return (default: 10)
            
        Returns:
            JSON string with contact data
        """
        return self.contacts.get_recent(limit)
    
    def get_recent_emails(self, limit: int = 10, after: Optional[str] = None) -> Dict[str, Any]:
        """Get recent emails from HubSpot with pagination.
        
        Args:
            limit: Maximum number of emails to return per page (default: 10)
            after: Pagination token from a previous call (default: None)
            
        Returns:
            Dictionary containing email data and pagination token
        """
        return self.conversations.get_recent_emails(limit, after)
    
    def get_recent_conversations(
        self, 
        limit: int = 10, 
        after: Optional[str] = None, 
        refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get recent conversation threads from HubSpot with pagination.
        
        Args:
            limit: Maximum number of threads to return per page (default: 10)
            after: Pagination token from a previous call (default: None)
            refresh_cache: Whether to refresh the threads cache (default: False)
            
        Returns:
            Dictionary containing conversation threads with their messages and pagination token
        """
        return self.conversations.get_recent_threads(limit, after, refresh_cache)
    
    def get_tickets(
        self, 
        criteria: Literal["default", "Closed"] = "default", 
        limit: int = 50, 
        max_retries: int = 3, 
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """Get tickets from HubSpot based on configurable selection criteria.
        
        Args:
            criteria: Selection criteria for tickets
                - "default": Tickets with "close date" or "last close date" > 1 day ago
                - "Closed": Tickets with status equals "Closed"
            limit: Maximum number of tickets to return (default: 50)
            max_retries: Maximum number of retry attempts for rate limiting (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 1.0)
            
        Returns:
            Dictionary containing ticket data and pagination information
        """
        return self.tickets.get_tickets(criteria, limit, max_retries, retry_delay)
    
    def get_ticket_conversation_threads(self, ticket_id: str) -> Dict[str, Any]:
        """Get conversation threads associated with a specific ticket.
        
        Args:
            ticket_id: The ID of the ticket to retrieve conversation threads for
            
        Returns:
            Dictionary containing conversation threads with their messages
        """
        return self.tickets.get_conversation_threads(ticket_id)
