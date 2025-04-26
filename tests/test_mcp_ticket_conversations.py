#!/usr/bin/env python
"""
Test script for retrieving closed tickets and their conversation threads using the MCP tools.
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional

# Add src directory to path to allow direct imports
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Import HubSpot client
from mcp_server_hubspot.hubspot_client import HubSpotClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_mcp_ticket_conversations")

def test_get_closed_tickets(hubspot_client: HubSpotClient) -> List[Dict[str, Any]]:
    """Test getting closed tickets using the MCP tool.
    
    Args:
        hubspot_client: Initialized HubSpot client
        
    Returns:
        List of closed tickets
    """
    logger.info("=== Testing hubspot_get_tickets with 'Closed' criteria ===")
    
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
    
    # Print ticket details
    for i, ticket in enumerate(tickets):
        ticket_id = ticket.get("id")
        subject = ticket.get("properties", {}).get("subject", "No subject")
        content = ticket.get("properties", {}).get("content", "No content")
        pipeline_stage = ticket.get("properties", {}).get("hs_pipeline_stage", "Unknown")
        
        logger.info(f"Ticket {i+1}:")
        logger.info(f"  ID: {ticket_id}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  Content: {content}")
        logger.info(f"  Pipeline Stage: {pipeline_stage}")
    
    return tickets

def test_get_ticket_conversation_threads(hubspot_client: HubSpotClient, ticket_id: str) -> Dict[str, Any]:
    """Test getting conversation threads for a specific ticket using the MCP tool.
    
    Args:
        hubspot_client: Initialized HubSpot client
        ticket_id: ID of the ticket to retrieve conversations for
        
    Returns:
        Conversation thread data
    """
    logger.info(f"=== Testing hubspot_get_ticket_conversation_threads for ticket {ticket_id} ===")
    
    # Get conversation threads
    try:
        threads_response = hubspot_client.get_ticket_conversation_threads(ticket_id=ticket_id)
        
        # Log response details
        total_threads = threads_response.get("total_threads", 0)
        total_messages = threads_response.get("total_messages", 0)
        threads = threads_response.get("threads", [])
        
        logger.info(f"Found {total_threads} conversation threads with {total_messages} total messages")
        
        # Print thread details
        for i, thread in enumerate(threads):
            thread_id = thread.get("id")
            messages = thread.get("messages", [])
            
            logger.info(f"Thread {i+1} (ID: {thread_id}):")
            logger.info(f"  Messages: {len(messages)}")
            
            # Print message details
            for j, message in enumerate(messages):
                sender_type = message.get("sender_type", "Unknown")
                text = message.get("text", "No text")
                created_at = message.get("created_at", "Unknown")
                
                logger.info(f"  Message {j+1}:")
                logger.info(f"    Sender: {sender_type}")
                logger.info(f"    Created: {created_at}")
                logger.info(f"    Text: {text[:100]}..." if len(text) > 100 else f"    Text: {text}")
        
        return threads_response
    
    except Exception as e:
        logger.error(f"Error getting conversation threads: {str(e)}")
        return {"error": str(e)}

def main():
    """Run the test script."""
    # Initialize HubSpot client
    access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not access_token:
        logger.error("HUBSPOT_ACCESS_TOKEN environment variable is required")
        sys.exit(1)
    
    hubspot_client = HubSpotClient(access_token)
    logger.info("HubSpot client initialized")
    
    # Test getting closed tickets
    closed_tickets = test_get_closed_tickets(hubspot_client)
    
    if not closed_tickets:
        logger.info("No closed tickets found to test conversation threads")
        return
    
    # Test getting conversation threads for each closed ticket
    for ticket in closed_tickets:
        ticket_id = ticket.get("id")
        subject = ticket.get("properties", {}).get("subject", "No subject")
        
        logger.info(f"Testing conversation threads for ticket: {subject} (ID: {ticket_id})")
        
        # Get conversation threads
        test_get_ticket_conversation_threads(hubspot_client, ticket_id)
        
        # Add a separator between tickets
        logger.info("=" * 80)

if __name__ == "__main__":
    main()
