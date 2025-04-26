"""
MCP server module for HubSpot integration.
Provides tools for interacting with HubSpot API through an MCP server interface.
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
import json
from dotenv import load_dotenv

from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions
import mcp.types as types
from mcp.server import Server
import mcp.server.stdio
from pydantic import AnyUrl

from sentence_transformers import SentenceTransformer

from .hubspot_client import HubSpotClient, ApiException
from .faiss_manager import FaissManager
from .utils import store_in_faiss, search_in_faiss
from .handlers.company_handler import CompanyHandler
from .handlers.contact_handler import ContactHandler
from .handlers.conversation_handler import ConversationHandler
from .handlers.ticket_handler import TicketHandler
from .handlers.search_handler import SearchHandler

logger = logging.getLogger('mcp_hubspot_server')

load_dotenv()

async def main(access_token: Optional[str] = None):
    """Run the HubSpot MCP server."""
    logger.info("Server starting")
    
    # Initialize dependencies
    embedding_model = initialize_embedding_model()
    faiss_manager = initialize_faiss_manager(embedding_model)
    hubspot_client = initialize_hubspot_client(access_token)
    
    # Initialize handlers with dependencies
    company_handler = CompanyHandler(hubspot_client, faiss_manager, embedding_model)
    contact_handler = ContactHandler(hubspot_client, faiss_manager, embedding_model)
    conversation_handler = ConversationHandler(hubspot_client, faiss_manager, embedding_model)
    ticket_handler = TicketHandler(hubspot_client, faiss_manager, embedding_model)
    search_handler = SearchHandler(faiss_manager, embedding_model)
    
    # Create server
    server = create_server_with_handlers(
        company_handler, 
        contact_handler,
        conversation_handler,
        ticket_handler,
        search_handler
    )
    
    # Based on MCP implementation, use stdio_server as a context manager that yields streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        # Log server start
        logger.info("Server running with stdio transport")
        
        # Create initialization options with capabilities
        initialization_options = InitializationOptions(
            server_name="hubspot-manager",
            server_version="0.2.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        )
        
        # Run the server with the provided streams and options
        await server.run(read_stream, write_stream, initialization_options)

def initialize_embedding_model() -> SentenceTransformer:
    """Initialize and return the embedding model."""
    logger.info("Loading embeddings model")
    
    local_model_path = '/app/models/all-MiniLM-L6-v2'
    if os.path.exists(local_model_path):
        logger.info(f"Using local model from {local_model_path}")
        embedding_model = SentenceTransformer(local_model_path)
    else:
        logger.info("Local model not found, downloading from HuggingFace")
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    embedding_dim = embedding_model.get_sentence_embedding_dimension()
    logger.info(f"Embeddings model loaded with dimension: {embedding_dim}")
    
    return embedding_model

def initialize_faiss_manager(embedding_model: SentenceTransformer) -> FaissManager:
    """Initialize and return the FAISS manager."""
    storage_dir = os.getenv("HUBSPOT_STORAGE_DIR_LOCAL", "/storage")
    logger.info(f"Using storage directory: {storage_dir}")
    
    embedding_dim = embedding_model.get_sentence_embedding_dimension()
    faiss_manager = FaissManager(
        storage_dir=storage_dir,
        embedding_dimension=embedding_dim
    )
    logger.info(f"FAISS manager initialized with dimension {embedding_dim}")
    
    return faiss_manager

def initialize_hubspot_client(access_token: Optional[str]) -> HubSpotClient:
    """Initialize and return the HubSpot client."""
    return HubSpotClient(access_token)

def create_server_with_handlers(
    company_handler: CompanyHandler,
    contact_handler: ContactHandler,
    conversation_handler: ConversationHandler,
    ticket_handler: TicketHandler,
    search_handler: SearchHandler
) -> Server:
    """Create and configure the MCP server with all handlers."""
    server = Server("hubspot-manager")
    
    # Register resource handlers
    register_resource_handlers(server)
    
    # Register tool definitions
    register_tool_definitions(server, 
                             company_handler, 
                             contact_handler, 
                             conversation_handler, 
                             ticket_handler, 
                             search_handler)
    
    # Register tool call handler
    register_tool_call_handler(server, 
                              company_handler, 
                              contact_handler, 
                              conversation_handler, 
                              ticket_handler, 
                              search_handler)
            
    return server

def register_resource_handlers(server: Server) -> None:
    """Register resource-related handlers with the server.
    
    Args:
        server: MCP server instance
    """
    @server.list_resources()
    async def handle_list_resources() -> list[types.Resource]:
        return []

    @server.read_resource()
    async def handle_read_resource(uri: AnyUrl) -> str:
        if uri.scheme != "hubspot":
            raise ValueError(f"Unsupported URI scheme: {uri.scheme}")
        path = str(uri).replace("hubspot://", "")
        return ""

def register_tool_definitions(
    server: Server,
    company_handler: CompanyHandler,
    contact_handler: ContactHandler,
    conversation_handler: ConversationHandler,
    ticket_handler: TicketHandler,
    search_handler: SearchHandler
) -> None:
    """Register tool definitions with the server.
    
    Args:
        server: MCP server instance
        company_handler: Handler for company operations
        contact_handler: Handler for contact operations
        conversation_handler: Handler for conversation operations
        ticket_handler: Handler for ticket operations
        search_handler: Handler for search operations
    """
    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """List available tools"""
        return [
            # Company tools
            types.Tool(
                name="hubspot_create_company",
                description="Create a new company in HubSpot",
                inputSchema=company_handler.get_create_company_schema(),
            ),
            types.Tool(
                name="hubspot_get_company_activity",
                description="Get activity history for a specific company",
                inputSchema=company_handler.get_company_activity_schema(),
            ),
            types.Tool(
                name="hubspot_get_active_companies",
                description="Get most recently active companies from HubSpot",
                inputSchema=company_handler.get_active_companies_schema(),
            ),
            
            # Contact tools
            types.Tool(
                name="hubspot_create_contact",
                description="Create a new contact in HubSpot",
                inputSchema=contact_handler.get_create_contact_schema(),
            ),
            types.Tool(
                name="hubspot_get_active_contacts",
                description="Get most recently active contacts from HubSpot",
                inputSchema=contact_handler.get_active_contacts_schema(),
            ),
            
            # Conversation tools
            types.Tool(
                name="hubspot_get_recent_conversations",
                description="Get recent conversation threads from HubSpot with their messages",
                inputSchema=conversation_handler.get_recent_conversations_schema(),
            ),
            
            # Ticket tools
            types.Tool(
                name="hubspot_get_tickets",
                description="Get tickets from HubSpot based on configurable selection criteria",
                inputSchema=ticket_handler.get_tickets_schema(),
            ),
            types.Tool(
                name="hubspot_get_ticket_conversation_threads",
                description="Get conversation threads associated with a specific ticket",
                inputSchema=ticket_handler.get_ticket_conversation_threads_schema(),
            ),
            
            # Search tools
            types.Tool(
                name="hubspot_search_data",
                description="Search for similar data in stored HubSpot API responses",
                inputSchema=search_handler.get_search_data_schema(),
            ),
        ]

def register_tool_call_handler(
    server: Server,
    company_handler: CompanyHandler,
    contact_handler: ContactHandler,
    conversation_handler: ConversationHandler,
    ticket_handler: TicketHandler,
    search_handler: SearchHandler
) -> None:
    """Register tool call handler with the server.
    
    Args:
        server: MCP server instance
        company_handler: Handler for company operations
        contact_handler: Handler for contact operations
        conversation_handler: Handler for conversation operations
        ticket_handler: Handler for ticket operations
        search_handler: Handler for search operations
    """
    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle tool execution requests"""
        try:
            # Route to appropriate handler based on tool name
            if name == "hubspot_create_company":
                return company_handler.create_company(arguments)
            elif name == "hubspot_get_company_activity":
                return company_handler.get_company_activity(arguments)
            elif name == "hubspot_get_active_companies":
                return company_handler.get_active_companies(arguments)
            elif name == "hubspot_create_contact":
                return contact_handler.create_contact(arguments)
            elif name == "hubspot_get_active_contacts":
                return contact_handler.get_active_contacts(arguments)
            elif name == "hubspot_get_recent_conversations":
                return conversation_handler.get_recent_conversations(arguments)
            elif name == "hubspot_get_tickets":
                return ticket_handler.get_tickets(arguments)
            elif name == "hubspot_get_ticket_conversation_threads":
                return ticket_handler.get_ticket_conversation_threads(arguments)
            elif name == "hubspot_search_data":
                return search_handler.search_data(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        except ApiException as e:
            return [types.TextContent(type="text", text=f"HubSpot API error: {str(e)}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="HubSpot MCP Server")
    parser.add_argument("--access-token", help="HubSpot API access token")
    
    args = parser.parse_args()
    
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    asyncio.run(main(args.access_token))
