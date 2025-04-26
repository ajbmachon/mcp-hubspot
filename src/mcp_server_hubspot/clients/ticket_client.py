"""
Client for HubSpot ticket-related operations.
"""
import json
import logging
import time
import requests
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime, timedelta

from hubspot import HubSpot
from hubspot.crm.tickets import PublicObjectSearchRequest
from hubspot.crm.contacts.exceptions import ApiException

from ..core.formatters import convert_datetime_fields
from ..core.error_handler import handle_hubspot_errors

logger = logging.getLogger('mcp_hubspot_client.ticket')

class TicketClient:
    """Client for HubSpot ticket-related operations."""
    
    def __init__(self, hubspot_client: HubSpot, access_token: str):
        """Initialize with HubSpot client instance.
        
        Args:
            hubspot_client: Initialized HubSpot client
            access_token: HubSpot API access token
        """
        self.client = hubspot_client
        self.access_token = access_token
    
    @handle_hubspot_errors
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
        # Create filter groups based on criteria
        filter_groups = self._create_filter_groups_for_criteria(criteria)
        
        # Create search request
        search_request = self._create_ticket_search_request(filter_groups, limit)
        
        # Implement retry logic with exponential backoff for rate limiting
        return self._execute_ticket_search_with_retry(
            search_request, max_retries, retry_delay
        )
    
    def _create_filter_groups_for_criteria(
        self, 
        criteria: Literal["default", "Closed"]
    ) -> List[Dict[str, Any]]:
        """Create filter groups based on ticket selection criteria.
        
        Args:
            criteria: Selection criteria for tickets
            
        Returns:
            List of filter groups for the search request
        """
        if criteria == "default":
            return self._create_default_criteria_filters()
        elif criteria == "Closed":
            return self._create_closed_criteria_filters()
        else:
            raise ValueError(f"Invalid criteria: {criteria}. Must be 'default' or 'Closed'")
    
    def _create_default_criteria_filters(self) -> List[Dict[str, Any]]:
        """Create filter groups for the default criteria.
        Default: Tickets with "close date" or "last modified date" > 1 day ago
        
        Returns:
            List of filter groups
        """
        one_day_ago = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Create filter group for close_date > 1 day ago
        close_date_filter = {
            "filters": [
                {
                    "propertyName": "closedate",
                    "operator": "GT",
                    "value": one_day_ago
                }
            ]
        }
        
        # Create filter group for hs_lastmodifieddate > 1 day ago
        last_close_date_filter = {
            "filters": [
                {
                    "propertyName": "hs_lastmodifieddate",
                    "operator": "GT",
                    "value": one_day_ago
                }
            ]
        }
        
        # Add both filter groups (either condition can match)
        return [close_date_filter, last_close_date_filter]
    
    def _create_closed_criteria_filters(self) -> List[Dict[str, Any]]:
        """Create filter groups for the closed criteria.
        Closed: Ticket status equals "Closed"
        
        Returns:
            List of filter groups
        """
        return [
            # Primary approach: using the pipeline stage ID
            {
                "filters": [
                    {
                        "propertyName": "hs_pipeline_stage",
                        "operator": "EQ",
                        "value": "4"  # Using the stage ID from the pipeline data
                    }
                ]
            },
            # Alternative approach: using the properly capitalized stage name
            {
                "filters": [
                    {
                        "propertyName": "hs_pipeline_stage",
                        "operator": "EQ",
                        "value": "Closed"  # Using correct capitalization
                    }
                ]
            }
        ]
    
    def _create_ticket_search_request(
        self, 
        filter_groups: List[Dict[str, Any]],
        limit: int
    ) -> PublicObjectSearchRequest:
        """Create a search request for tickets with specified filters.
        
        Args:
            filter_groups: List of filter groups for the search
            limit: Maximum number of tickets to return
            
        Returns:
            Configured search request object
        """
        return PublicObjectSearchRequest(
            filter_groups=filter_groups,
            sorts=[{
                "propertyName": "hs_lastmodifieddate",
                "direction": "DESCENDING"
            }],
            limit=limit,
            properties=[
                "subject", 
                "content", 
                "hs_pipeline", 
                "hs_pipeline_stage", 
                "hs_ticket_status",
                "status",     
                "hs_ticket_priority", 
                "createdate", 
                "closedate", 
                "hs_lastmodifieddate"
            ]
        )
    
    def _execute_ticket_search_with_retry(
        self,
        search_request: PublicObjectSearchRequest,
        max_retries: int,
        retry_delay: float
    ) -> Dict[str, Any]:
        """Execute a ticket search with retry logic for rate limiting.
        
        Args:
            search_request: Search request to execute
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            
        Returns:
            Dictionary with search results and pagination information
        """
        retry_count = 0
        current_delay = retry_delay
        
        while True:
            try:
                # Log filter groups for debugging
                logger.debug(f"Executing ticket search with filter groups: {json.dumps(search_request.filter_groups)}")
                
                # Execute the search
                search_response = self.client.crm.tickets.search_api.do_search(
                    public_object_search_request=search_request
                )
                
                # Log raw response
                logger.debug(f"Search response total results: {search_response.total}")
                
                # Convert the response to a dictionary
                tickets_dict = [ticket.to_dict() for ticket in search_response.results]
                converted_tickets = convert_datetime_fields(tickets_dict)
                
                # Log ticket data if available
                if tickets_dict:
                    logger.debug(f"First ticket pipeline stage: {tickets_dict[0].get('properties', {}).get('hs_pipeline_stage')}")
                    logger.debug(f"First ticket status: {tickets_dict[0].get('properties', {}).get('hs_ticket_status')}")
                
                # Get pagination information
                next_after = None
                if hasattr(search_response, 'paging') and hasattr(search_response.paging, 'next'):
                    next_after = search_response.paging.next.after
                
                return {
                    "results": converted_tickets,
                    "pagination": {
                        "next": {"after": next_after}
                    },
                    "total": search_response.total
                }
                
            except ApiException as e:
                # Check if it's a rate limiting error (429) or server error (5xx)
                if e.status == 429 or (e.status >= 500 and e.status < 600):
                    retry_count += 1
                    
                    # Check if we've reached max retries
                    if retry_count > max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for API request")
                        raise
                    
                    # Calculate exponential backoff delay
                    sleep_time = current_delay * (2 ** (retry_count - 1))
                    logger.warning(f"Rate limit hit or server error ({e.status}). Retrying in {sleep_time:.2f} seconds (attempt {retry_count}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    # Not a rate limiting or server error, re-raise
                    raise
    
    @handle_hubspot_errors
    def get_conversation_threads(self, ticket_id: str) -> Dict[str, Any]:
        """Get conversation threads associated with a specific ticket.
        
        Args:
            ticket_id: The ID of the ticket to retrieve conversation threads for
            
        Returns:
            Dictionary containing conversation threads with their messages
        """
        logger.debug(f"Fetching conversation threads for ticket {ticket_id}")
        
        try:
            # Step 1: Use Associations API to retrieve conversation threads associated with the ticket
            associated_conversations = self._get_associated_conversations(ticket_id)
            
            # Step 2: Extract thread IDs from the associated conversations
            thread_ids = self._extract_thread_ids(associated_conversations)
            
            logger.debug(f"Found {len(thread_ids)} conversation threads associated with ticket {ticket_id}")
            
            if not thread_ids:
                logger.info(f"No conversation threads found for ticket {ticket_id}")
                return self._create_empty_ticket_threads_response(ticket_id)
            
            # Step 3: Retrieve all messages for each thread
            threads, total_messages = self._get_thread_messages(thread_ids)
            
            # Convert datetime fields
            converted_threads = convert_datetime_fields(threads)
            
            return {
                "ticket_id": ticket_id,
                "threads": converted_threads,
                "total_threads": len(converted_threads),
                "total_messages": total_messages
            }
        except Exception as e:
            logger.error(f"Error retrieving conversation threads for ticket {ticket_id}: {str(e)}", exc_info=True)
            return self._create_empty_ticket_threads_response(ticket_id)
    
    def _get_associated_conversations(self, ticket_id: str) -> Dict[str, Any]:
        """Get conversation threads associated with a ticket.
        
        Args:
            ticket_id: Ticket ID
            
        Returns:
            API response with conversation associations
        """
        url = f"https://api.hubapi.com/crm/v4/objects/tickets/{ticket_id}/associations/conversation"
        headers = {
            'accept': "application/json",
            'authorization': f"Bearer {self.access_token}"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        return response.json()
    
    def _extract_thread_ids(self, associated_conversations: Dict[str, Any]) -> List[str]:
        """Extract thread IDs from the conversations association response.
        
        Args:
            associated_conversations: Conversations association response
            
        Returns:
            List of thread IDs
        """
        thread_ids = []
        
        for conversation in associated_conversations.get('results', []):
            # Check if the conversation has a toObjectId field (this is the conversation ID)
            if 'toObjectId' in conversation:
                thread_ids.append(str(conversation['toObjectId']))
            elif 'id' in conversation:
                # Fallback to id if it exists
                thread_ids.append(str(conversation['id']))
            else:
                # Log warning for debugging
                logger.warning(f"No 'id' or 'toObjectId' field in conversation: {json.dumps(conversation)}")
        
        return thread_ids
    
    def _create_empty_ticket_threads_response(self, ticket_id: str) -> Dict[str, Any]:
        """Create an empty ticket threads response.
        
        Args:
            ticket_id: Ticket ID
            
        Returns:
            Empty response structure
        """
        return {
            "ticket_id": ticket_id,
            "threads": [],
            "total_threads": 0,
            "total_messages": 0
        }
    
    def _get_thread_messages(self, thread_ids: List[str]) -> tuple[List[Dict[str, Any]], int]:
        """Get messages for each thread and format them.
        
        Args:
            thread_ids: List of thread IDs
            
        Returns:
            Tuple of (formatted threads, total message count)
        """
        threads = []
        total_messages = 0
        
        for thread_id in thread_ids:
            try:
                # Get messages for this thread
                messages_data = self._fetch_thread_messages(thread_id)
                
                message_results = messages_data.get("results", [])
                
                # Only keep actual messages (not system messages)
                actual_messages = [msg for msg in message_results if msg.get("type") == "MESSAGE"]
                
                # Format thread with its messages
                formatted_thread = {
                    "id": thread_id,
                    "messages": []
                }
                
                # Add formatted messages
                for msg in actual_messages:
                    formatted_message = self._format_message(msg)
                    formatted_thread["messages"].append(formatted_message)
                
                # Sort messages by creation time (ascending)
                formatted_thread["messages"].sort(key=lambda x: x.get("created_at", ""))
                
                # Add thread to the list
                threads.append(formatted_thread)
                total_messages += len(formatted_thread["messages"])
                
            except Exception as e:
                logger.error(f"Error fetching messages for thread {thread_id}: {str(e)}")
        
        return threads, total_messages
    
    def _fetch_thread_messages(self, thread_id: str) -> Dict[str, Any]:
        """Fetch messages for a specific thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            API response with message results
        """
        messages_url = f"https://api.hubapi.com/conversations/v3/conversations/threads/{thread_id}/messages"
        headers = {
            'accept': "application/json",
            'authorization': f"Bearer {self.access_token}"
        }
        
        response = requests.get(messages_url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def _format_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Format a message.
        
        Args:
            msg: Message data
            
        Returns:
            Formatted message
        """
        # Determine sender type (AGENT or CUSTOMER)
        sender_type = self._determine_sender_type(msg)
        
        # Format the message with required metadata
        return {
            "id": msg.get("id"),
            "created_at": msg.get("createdAt"),
            "sender_type": sender_type,
            "text": msg.get("text", ""),  # Focus only on text content, ignore attachments
        }
    
    def _determine_sender_type(self, msg: Dict[str, Any]) -> str:
        """Determine the sender type (AGENT or CUSTOMER).
        
        Args:
            msg: Message data
            
        Returns:
            Sender type string
        """
        sender_type = "UNKNOWN"
        if msg.get("senders") and len(msg.get("senders")) > 0:
            sender = msg.get("senders")[0]
            # In HubSpot, agents typically have senderField as "FROM" and actorId starting with specific prefixes
            if sender.get("senderField") == "FROM" and sender.get("actorId", "").startswith(("0-1", "0-2")):
                sender_type = "AGENT"
            else:
                sender_type = "CUSTOMER"
        return sender_type
