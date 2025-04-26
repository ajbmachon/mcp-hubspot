#!/usr/bin/env python
"""
Script to retrieve all closed tickets and their conversation threads from HubSpot.
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List

# Add src directory to path to allow direct imports
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Import HubSpot client
from mcp_server_hubspot.hubspot_client import HubSpotClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("get_closed_ticket_conversations")

def get_closed_tickets(hubspot_client: HubSpotClient) -> List[Dict[str, Any]]:
    """Get all closed tickets from HubSpot.
    
    Args:
        hubspot_client: Initialized HubSpot client
        
    Returns:
        List of closed tickets
    """
    logger.info("Retrieving closed tickets...")
    
    # Get closed tickets
    tickets_response = hubspot_client.get_tickets(
        criteria="Closed",
        limit=20,
        max_retries=3,
        retry_delay=1.0
    )
    
    # Extract ticket data
    tickets = tickets_response.get("results", [])
    logger.info(f"Found {len(tickets)} closed tickets")
    
    return tickets

def get_ticket_conversations(hubspot_client: HubSpotClient, ticket_id: str) -> Dict[str, Any]:
    """Get conversation threads for a specific ticket.
    
    Args:
        hubspot_client: Initialized HubSpot client
        ticket_id: ID of the ticket to retrieve conversations for
        
    Returns:
        Conversation thread data or error information
    """
    logger.info(f"Retrieving conversation threads for ticket {ticket_id}...")
    
    try:
        # Get conversation threads
        threads_response = hubspot_client.get_ticket_conversation_threads(ticket_id=ticket_id)
        
        # Check if response is a string (error message)
        if isinstance(threads_response, str):
            logger.error(f"Error retrieving conversation threads: {threads_response}")
            return {"error": threads_response, "total_threads": 0, "total_messages": 0, "threads": []}
        
        return threads_response
    except Exception as e:
        logger.error(f"Exception retrieving conversation threads: {str(e)}")
        return {"error": str(e), "total_threads": 0, "total_messages": 0, "threads": []}

def main():
    """Run the script to get closed tickets and their conversations."""
    # Initialize HubSpot client
    access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not access_token:
        logger.error("HUBSPOT_ACCESS_TOKEN environment variable is required")
        sys.exit(1)
    
    hubspot_client = HubSpotClient(access_token)
    logger.info("HubSpot client initialized")
    
    # Get closed tickets
    closed_tickets = get_closed_tickets(hubspot_client)
    
    if not closed_tickets:
        logger.info("No closed tickets found")
        return
    
    # Get conversation threads for each ticket
    all_conversations = []
    
    for ticket in closed_tickets:
        ticket_id = ticket.get("id")
        subject = ticket.get("properties", {}).get("subject", "No subject")
        
        logger.info(f"Processing ticket: {subject} (ID: {ticket_id})")
        
        # Get conversation threads
        conversation_data = get_ticket_conversations(hubspot_client, ticket_id)
        
        # Create a new dictionary with ticket info and conversation data
        ticket_conversation = {
            "ticket_id": ticket_id,
            "ticket_subject": subject,
            "ticket_content": ticket.get("properties", {}).get("content", ""),
            "conversation_data": conversation_data
        }
        
        all_conversations.append(ticket_conversation)
    
    # Save results to file
    output_file = "closed_ticket_conversations.json"
    with open(output_file, "w") as f:
        json.dump(all_conversations, f, indent=2)
    
    logger.info(f"All conversation data saved to {output_file}")
    
    # Print summary
    total_threads = sum(conv.get("conversation_data", {}).get("total_threads", 0) for conv in all_conversations)
    total_messages = sum(conv.get("conversation_data", {}).get("total_messages", 0) for conv in all_conversations)
    
    logger.info(f"Summary: {len(closed_tickets)} tickets, {total_threads} threads, {total_messages} messages")

if __name__ == "__main__":
    main()
