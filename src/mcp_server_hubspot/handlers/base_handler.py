"""
Base handler for HubSpot API operations.
Provides common functionality for all specialized handlers.
"""
from typing import Any, Dict, List, Optional
import logging
import json

import mcp.types as types
from sentence_transformers import SentenceTransformer

from ..hubspot_client import HubSpotClient
from ..faiss_manager import FaissManager
from ..utils import store_in_faiss

class BaseHandler:
    """Base class for all HubSpot tool handlers."""
    
    def __init__(
        self, 
        hubspot_client: HubSpotClient, 
        faiss_manager: FaissManager,
        embedding_model: SentenceTransformer,
        logger_name: str = "base_handler"
    ):
        """Initialize the base handler with common dependencies.
        
        Args:
            hubspot_client: HubSpot client
            faiss_manager: FAISS vector store manager
            embedding_model: Sentence transformer model
            logger_name: Name for this handler's logger
        """
        self.hubspot = hubspot_client
        self.faiss_manager = faiss_manager
        self.embedding_model = embedding_model
        self.logger = logging.getLogger(f'mcp_hubspot_server.{logger_name}')
    
    def store_in_faiss_safely(
        self, 
        data: Any, 
        data_type: str, 
        metadata_extras: Optional[Dict[str, Any]] = None
    ) -> None:
        """Safely store data in FAISS with error handling.
        
        Args:
            data: Data to store
            data_type: Type of data being stored
            metadata_extras: Additional metadata to store
        """
        try:
            if not data:
                self.logger.debug(f"No {data_type} data to store in FAISS")
                return
                
            self.logger.debug(f"Storing {data_type} data in FAISS")
            
            if metadata_extras:
                self.logger.debug(f"With metadata: {metadata_extras}")
                
            store_in_faiss(
                faiss_manager=self.faiss_manager,
                data=data,
                data_type=data_type,
                model=self.embedding_model,
                metadata_extras=metadata_extras
            )
            
            # Save the index
            self.logger.debug("Saving FAISS index")
            self.faiss_manager.save_today_index()
            self.logger.debug("FAISS index saved")
            
        except Exception as e:
            self.logger.error(f"Error storing {data_type} in FAISS: {str(e)}", exc_info=True)
    
    def create_text_response(self, content: Any) -> List[types.TextContent]:
        """Create a text response from content.
        
        Args:
            content: Content to return (will be converted to JSON if not string)
            
        Returns:
            List containing a TextContent object
        """
        if not isinstance(content, str):
            content = json.dumps(content)
            
        return [types.TextContent(type="text", text=content)]
    
    def validate_required_arguments(self, arguments: Optional[Dict[str, Any]], required_keys: List[str]) -> None:
        """Validate that required arguments are present.
        
        Args:
            arguments: Dictionary of arguments
            required_keys: List of required keys
            
        Raises:
            ValueError: If any required key is missing
        """
        if not arguments:
            raise ValueError(f"Missing arguments. Required: {', '.join(required_keys)}")
            
        for key in required_keys:
            if key not in arguments:
                raise ValueError(f"Missing required argument: {key}")
                
    def get_argument_with_default(
        self, 
        arguments: Optional[Dict[str, Any]], 
        key: str, 
        default: Any
    ) -> Any:
        """Get an argument with a default value if not provided.
        
        Args:
            arguments: Dictionary of arguments
            key: Argument key
            default: Default value
            
        Returns:
            Argument value or default
        """
        if not arguments:
            return default
            
        return arguments.get(key, default)
