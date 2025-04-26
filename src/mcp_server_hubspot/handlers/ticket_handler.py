"""
Handler for ticket-related HubSpot operations.
"""
from typing import Any, Dict, List, Optional
import json

import mcp.types as types

from .base_handler import BaseHandler

class TicketHandler(BaseHandler):
    """Handler for ticket-related HubSpot tools."""
    
    def __init__(self, hubspot_client, faiss_manager, embedding_model):
        """Initialize the ticket handler.
        
        Args:
            hubspot_client: HubSpot client
            faiss_manager: FAISS vector store manager
            embedding_model: Sentence transformer model
        """
        super().__init__(hubspot_client, faiss_manager, embedding_model, "ticket_handler")
    
    def get_tickets_schema(self) -> Dict[str, Any]:
        """Get the input schema for tickets.
        
        Returns:
            Schema definition dictionary
        """
        return {
            "type": "object",
            "properties": {
                "criteria": {
                    "type": "string", 
                    "enum": ["default", "Closed"],
                    "description": "Selection criteria for tickets: 'default' (tickets with close date or last modified date > 1 day ago) or 'closed' (tickets with status equals 'Closed')"
                },
                "limit": {"type": "integer", "description": "Maximum number of tickets to return (default: 50)"},
                "max_retries": {"type": "integer", "description": "Maximum number of retry attempts for rate limiting (default: 3)"},
                "retry_delay": {"type": "number", "description": "Initial delay between retries in seconds (default: 1.0)"}
            },
        }
    
    def get_ticket_conversation_threads_schema(self) -> Dict[str, Any]:
        """Get the input schema for ticket conversation threads.
        
        Returns:
            Schema definition dictionary
        """
        return {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "ID of the ticket to retrieve conversation threads for"}
            },
            "required": ["ticket_id"]
        }
    
    def get_tickets(self, arguments: Optional[Dict[str, Any]]) -> List[types.TextContent]:
        """Get tickets from HubSpot based on configurable selection criteria.
        
        Args:
            arguments: Tool arguments containing ticket selection criteria
            
        Returns:
            Text response with ticket data
        """
        # Extract parameters with defaults
        criteria = self.get_argument_with_default(arguments, "criteria", "default")
        limit = self.get_argument_with_default(arguments, "limit", 50)
        max_retries = self.get_argument_with_default(arguments, "max_retries", 3)
        retry_delay = self.get_argument_with_default(arguments, "retry_delay", 1.0)
        
        # Ensure parameters are of correct type
        limit = int(limit) if limit is not None else 50
        max_retries = int(max_retries) if max_retries is not None else 3
        retry_delay = float(retry_delay) if retry_delay is not None else 1.0
        
        # Validate criteria
        if criteria not in ["default", "Closed"]:
            return self.create_text_response({
                "error": f"Invalid criteria: {criteria}. Must be 'default' or 'Closed'",
                "results": [],
                "pagination": {"next": {"after": None}},
                "total": 0
            })
        
        # Get tickets based on criteria
        self.logger.debug(f"Getting tickets with criteria={criteria}, limit={limit}, max_retries={max_retries}, retry_delay={retry_delay}")
        results = self.hubspot.get_tickets(
            criteria=criteria,
            limit=limit,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
        
        # Store in FAISS for future reference
        self._store_tickets_in_faiss(results, criteria, limit)
        
        # Return results as JSON
        return self.create_text_response(results)
    
    def _store_tickets_in_faiss(
        self, 
        results: Dict[str, Any], 
        criteria: str, 
        limit: int
    ) -> None:
        """Store ticket data in FAISS.
        
        Args:
            results: Ticket results
            criteria: Selection criteria used in the request
            limit: Limit parameter used in the request
        """
        try:
            data = results.get("results", [])
            if data:
                metadata_extras = {
                    "criteria": criteria,
                    "limit": limit
                }
                self.logger.debug(f"Preparing to store {len(data)} tickets in FAISS")
                self.logger.debug(f"Metadata extras: {metadata_extras}")
                
                self.store_in_faiss_safely(
                    data=data,
                    data_type="ticket",
                    metadata_extras=metadata_extras
                )
        except Exception as e:
            self.logger.error(f"Error storing tickets in FAISS: {str(e)}", exc_info=True)
    
    def get_ticket_conversation_threads(self, arguments: Optional[Dict[str, Any]]) -> List[types.TextContent]:
        """Get conversation threads associated with a specific ticket.
        
        Args:
            arguments: Tool arguments containing ticket ID
            
        Returns:
            Text response with conversation thread data
        """
        # Validate required parameters
        self.validate_required_arguments(arguments, ["ticket_id"])
        
        ticket_id = arguments["ticket_id"]
        
        try:
            # Get conversation threads for the ticket
            self.logger.debug(f"Getting conversation threads for ticket {ticket_id}")
            results = self.hubspot.get_ticket_conversation_threads(ticket_id=ticket_id)
            
            # Check if results is a string (error message)
            if isinstance(results, str):
                self.logger.error(f"Error retrieving conversation threads: {results}")
                return self.create_text_response({
                    "error": results,
                    "ticket_id": ticket_id,
                    "threads": [],
                    "total_threads": 0,
                    "total_messages": 0
                })
            
            # Store in FAISS for future reference
            self._store_ticket_threads_in_faiss(results, ticket_id)
            
            # Return results as JSON
            return self.create_text_response(results)
        except Exception as e:
            self.logger.error(f"Exception in get_ticket_conversation_threads: {str(e)}", exc_info=True)
            return self.create_text_response({
                "error": str(e),
                "ticket_id": ticket_id,
                "threads": [],
                "total_threads": 0,
                "total_messages": 0
            })
    
    def _store_ticket_threads_in_faiss(
        self, 
        results: Dict[str, Any], 
        ticket_id: str
    ) -> None:
        """Store ticket conversation threads in FAISS.
        
        Args:
            results: Conversation thread results
            ticket_id: Ticket ID used in the request
        """
        try:
            threads_data = results.get("threads", [])
            if threads_data:
                metadata_extras = {
                    "ticket_id": ticket_id,
                    "total_threads": results.get("total_threads", 0),
                    "total_messages": results.get("total_messages", 0)
                }
                self.logger.debug(f"Preparing to store {len(threads_data)} conversation threads in FAISS")
                self.logger.debug(f"Metadata extras: {metadata_extras}")
                
                self.store_in_faiss_safely(
                    data=threads_data,
                    data_type="ticket_conversation_thread",
                    metadata_extras=metadata_extras
                )
        except Exception as e:
            self.logger.error(f"Error storing ticket conversation threads in FAISS: {str(e)}", exc_info=True)
