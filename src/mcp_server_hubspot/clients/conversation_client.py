"""
Client for HubSpot conversation-related operations.
"""
import json
import logging
import requests
from typing import Any, Dict, List, Optional

from hubspot import HubSpot
from hubspot.crm.objects.emails import BatchReadInputSimplePublicObjectId, SimplePublicObjectId
from hubspot.crm.contacts.exceptions import ApiException

from ..core.formatters import convert_datetime_fields
from ..core.error_handler import handle_hubspot_errors
from ..core.storage import ThreadStorage

logger = logging.getLogger('mcp_hubspot_client.conversation')

class ConversationClient:
    """Client for HubSpot conversation-related operations."""
    
    def __init__(self, hubspot_client: HubSpot, access_token: str, thread_storage: ThreadStorage):
        """Initialize with HubSpot client instance.
        
        Args:
            hubspot_client: Initialized HubSpot client
            access_token: HubSpot API access token
            thread_storage: Storage handler for conversation threads
        """
        self.client = hubspot_client
        self.access_token = access_token
        self.thread_storage = thread_storage
    
    @handle_hubspot_errors
    def get_recent_emails(self, limit: int = 10, after: Optional[str] = None) -> Dict[str, Any]:
        """Get recent emails from HubSpot with pagination.
        
        Args:
            limit: Maximum number of emails to return per page (default: 10)
            after: Pagination token from a previous call (default: None)
            
        Returns:
            Dictionary containing email data and pagination token
        """
        logger.debug(f"Fetching {limit} emails with after={after}")
        api_response = self._fetch_emails_page(limit, after)
        
        email_ids = [email.id for email in api_response.results]
        logger.debug(f"Found {len(email_ids)} email IDs")
        
        if not email_ids:
            logger.info("No emails found")
            return self._create_empty_email_response(api_response)
        
        email_details = self._get_email_details(email_ids)
        next_after = self._extract_pagination_token(api_response)
        
        return {
            "results": email_details,
            "pagination": {
                "next": {"after": next_after}
            }
        }
    
    def _fetch_emails_page(self, limit: int, after: Optional[str]) -> Any:
        """Fetch a page of emails from HubSpot.
        
        Args:
            limit: Maximum number of emails to return
            after: Pagination token
            
        Returns:
            API response with email results
        """
        return self.client.crm.objects.emails.basic_api.get_page(
            limit=limit, 
            archived=False,
            after=after
        )
    
    def _create_empty_email_response(self, api_response: Any) -> Dict[str, Any]:
        """Create an empty email response structure with pagination.
        
        Args:
            api_response: API response containing pagination info
            
        Returns:
            Empty response structure with pagination
        """
        next_after = None
        if hasattr(api_response, 'paging') and hasattr(api_response.paging, 'next'):
            next_after = api_response.paging.next.after
            
        return {
            "results": [],
            "pagination": {
                "next": {"after": next_after}
            }
        }
    
    def _get_email_details(self, email_ids: List[str]) -> List[Dict[str, Any]]:
        """Get detailed content for each email.
        
        Args:
            email_ids: List of email IDs to retrieve details for
            
        Returns:
            List of formatted email details
        """
        formatted_emails = []
        batch_size = 10  # HubSpot API limit for batch operations
        
        for i in range(0, len(email_ids), batch_size):
            batch_ids = email_ids[i:i+batch_size]
            logger.debug(f"Processing batch of {len(batch_ids)} emails")
            
            try:
                batch_response = self._fetch_email_batch(batch_ids)
                formatted_batch = self._format_email_batch(batch_response)
                formatted_emails.extend(formatted_batch)
            except ApiException as e:
                logger.error(f"Batch API Exception: {str(e)}")
        
        # Convert datetime fields
        return convert_datetime_fields(formatted_emails)
    
    def _fetch_email_batch(self, batch_ids: List[str]) -> Any:
        """Fetch details for a batch of emails.
        
        Args:
            batch_ids: List of email IDs to retrieve
            
        Returns:
            Batch API response
        """
        batch_input = BatchReadInputSimplePublicObjectId(
            inputs=[SimplePublicObjectId(id=email_id) for email_id in batch_ids],
            properties=[
                "subject", "hs_email_text", "hs_email_html", "hs_email_from",
                "hs_email_to", "hs_email_cc", "hs_email_bcc", "createdAt", "updatedAt"
            ]
        )
        
        return self.client.crm.objects.emails.batch_api.read(
            batch_read_input_simple_public_object_id=batch_input
        )
    
    def _format_email_batch(self, batch_response: Any) -> List[Dict[str, Any]]:
        """Format a batch of email responses.
        
        Args:
            batch_response: Batch API response
            
        Returns:
            List of formatted emails
        """
        formatted_emails = []
        
        for email in batch_response.results:
            email_dict = email.to_dict()
            properties = email_dict.get("properties", {})
            
            formatted_email = {
                "id": email_dict.get("id"),
                "created_at": properties.get("createdAt"),
                "updated_at": properties.get("updatedAt"),
                "subject": properties.get("subject", ""),
                "from": properties.get("hs_email_from", ""),
                "to": properties.get("hs_email_to", ""),
                "cc": properties.get("hs_email_cc", ""),
                "bcc": properties.get("hs_email_bcc", ""),
                "body": properties.get("hs_email_text", "") or properties.get("hs_email_html", "")
            }
            
            formatted_emails.append(formatted_email)
            
        return formatted_emails
    
    def _extract_pagination_token(self, api_response: Any) -> Optional[str]:
        """Extract the pagination token from an API response.
        
        Args:
            api_response: API response potentially containing pagination
            
        Returns:
            Pagination token or None
        """
        if hasattr(api_response, 'paging') and hasattr(api_response.paging, 'next'):
            return api_response.paging.next.after
        return None
    
    @handle_hubspot_errors
    def get_recent_threads(
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
        threads_data = self._get_threads_data(limit, after, refresh_cache)
        thread_results = threads_data.get("results", [])
        logger.debug(f"Found {len(thread_results)} threads")
        
        if not thread_results:
            logger.info("No threads found")
            return self._create_empty_threads_response(threads_data)
        
        formatted_threads = self._get_thread_messages(thread_results)
        next_after = threads_data.get("paging", {}).get("next", {}).get("after")
        
        # Convert datetime fields
        converted_threads = convert_datetime_fields(formatted_threads)
        
        return {
            "results": converted_threads,
            "pagination": {
                "next": {"after": next_after}
            }
        }
    
    def _get_threads_data(
        self, 
        limit: int, 
        after: Optional[str], 
        refresh_cache: bool
    ) -> Dict[str, Any]:
        """Get thread data, either from cache or by fetching from API.
        
        Args:
            limit: Maximum number of threads to return
            after: Pagination token
            refresh_cache: Whether to refresh the cache
            
        Returns:
            Thread data
        """
        # Use cached threads unless refresh_cache is True or we're paginating
        if not refresh_cache and not after and self.thread_storage.get_cached_threads().get("results"):
            logger.info("Using cached threads")
            return self.thread_storage.get_cached_threads()
        
        # Get a page of threads
        logger.debug(f"Fetching {limit} threads with after={after}")
        threads_response = self._fetch_threads_page(limit, after)
        
        # Save or update threads cache
        if not after:  # Only replace full cache when getting first page
            self.thread_storage.update_cache(threads_response)
        
        return threads_response
    
    def _fetch_threads_page(self, limit: int, after: Optional[str]) -> Dict[str, Any]:
        """Fetch a page of conversation threads from HubSpot.
        
        Args:
            limit: Maximum number of threads to return
            after: Pagination token
            
        Returns:
            API response with thread results
        """
        url = "https://api.hubapi.com/conversations/v3/conversations/threads"
        
        params = {"limit": limit, "sort": "-id"}
        if after:
            params["after"] = after
        
        headers = {
            'accept': "application/json",
            'authorization': f"Bearer {self.access_token}"
        }
        
        response = requests.request("GET", url, headers=headers, params=params)
        return response.json()
    
    def _create_empty_threads_response(self, threads_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an empty threads response structure with pagination.
        
        Args:
            threads_data: Thread data containing pagination info
            
        Returns:
            Empty response structure with pagination
        """
        return {
            "results": [],
            "pagination": {
                "next": {"after": threads_data.get("paging", {}).get("next", {}).get("after")}
            }
        }
    
    def _get_thread_messages(self, thread_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get messages for each thread and format them.
        
        Args:
            thread_results: List of thread data
            
        Returns:
            List of formatted threads with their messages
        """
        formatted_threads = []
        
        for thread in thread_results:
            thread_id = thread.get("id")
            if not thread_id:
                continue
            
            # Get the messages for this thread
            try:
                messages_response = self._fetch_thread_messages(thread_id)
                
                # Format thread with its messages
                message_results = messages_response.get("results", [])
                
                # Only keep actual messages (not system messages)
                actual_messages = [msg for msg in message_results if msg.get("type") == "MESSAGE"]
                
                formatted_thread = self._format_thread(thread, actual_messages)
                formatted_threads.append(formatted_thread)
                
            except Exception as e:
                logger.error(f"Error fetching messages for thread {thread_id}: {str(e)}")
        
        return formatted_threads
    
    def _fetch_thread_messages(self, thread_id: str) -> Dict[str, Any]:
        """Fetch messages for a specific thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            API response with message results
        """
        url = f"https://api.hubapi.com/conversations/v3/conversations/threads/{thread_id}/messages"
        
        headers = {
            'accept': "application/json",
            'authorization': f"Bearer {self.access_token}"
        }
        
        response = requests.request("GET", url, headers=headers)
        return response.json()
    
    def _format_thread(
        self, 
        thread: Dict[str, Any], 
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format a thread with its messages.
        
        Args:
            thread: Thread data
            messages: List of messages in the thread
            
        Returns:
            Formatted thread with messages
        """
        formatted_thread = {
            "id": thread.get("id"),
            "created_at": thread.get("createdAt"),
            "status": thread.get("status"),
            "inbox_id": thread.get("inboxId"),
            "associated_contact_id": thread.get("associatedContactId"),
            "spam": thread.get("spam", False),
            "archived": thread.get("archived", False),
            "assigned_to": thread.get("assignedTo"),
            "latest_message_timestamp": thread.get("latestMessageTimestamp"),
            "messages": []
        }
        
        # Add formatted messages
        for msg in messages:
            formatted_message = self._format_message(msg)
            formatted_thread["messages"].append(formatted_message)
        
        return formatted_thread
    
    def _format_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Format a message.
        
        Args:
            msg: Message data
            
        Returns:
            Formatted message
        """
        sender_info = self._extract_sender_info(msg)
        recipients_info = self._extract_recipients_info(msg)
        
        return {
            "id": msg.get("id"),
            "created_at": msg.get("createdAt"),
            "updated_at": msg.get("updatedAt"),
            "sender": sender_info,
            "recipients": recipients_info,
            "subject": msg.get("subject", ""),
            "text": msg.get("text", ""),
            "rich_text": msg.get("richText", ""),
            "status": msg.get("status", {}).get("statusType", ""),
            "direction": msg.get("direction", ""),
            "channel_id": msg.get("channelId", ""),
            "channel_account_id": msg.get("channelAccountId", "")
        }
    
    def _extract_sender_info(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Extract sender information from a message.
        
        Args:
            msg: Message data
            
        Returns:
            Sender information
        """
        sender_info = {}
        if msg.get("senders") and len(msg.get("senders")) > 0:
            sender = msg.get("senders")[0]
            sender_info = {
                "actor_id": sender.get("actorId", ""),
                "name": sender.get("name", ""),
                "sender_field": sender.get("senderField", ""),
                "email": sender.get("deliveryIdentifier", {}).get("value", "") 
                        if sender.get("deliveryIdentifier", {}).get("type") == "HS_EMAIL_ADDRESS" 
                        else ""
            }
        return sender_info
    
    def _extract_recipients_info(self, msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract recipient information from a message.
        
        Args:
            msg: Message data
            
        Returns:
            List of recipient information
        """
        recipients_info = []
        for recipient in msg.get("recipients", []):
            if recipient.get("deliveryIdentifier", {}).get("type") == "HS_EMAIL_ADDRESS":
                recipients_info.append({
                    "recipient_field": recipient.get("recipientField", ""),
                    "email": recipient.get("deliveryIdentifier", {}).get("value", "")
                })
        return recipients_info
