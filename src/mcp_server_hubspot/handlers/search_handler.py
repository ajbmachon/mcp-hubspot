"""
Handler for search operations on indexed HubSpot data.
"""
from typing import Any, Dict, List, Optional
import json

import mcp.types as types
from sentence_transformers import SentenceTransformer

from ..faiss_manager import FaissManager
from ..utils import search_in_faiss
from .base_handler import BaseHandler

class SearchHandler(BaseHandler):
    """Handler for search operations on indexed HubSpot data."""
    
    def __init__(
        self, 
        faiss_manager: FaissManager,
        embedding_model: SentenceTransformer,
    ):
        """Initialize the search handler.
        
        Args:
            faiss_manager: FAISS vector store manager
            embedding_model: Sentence transformer model
        """
        # Note: This handler doesn't need the HubSpot client, only the FAISS components
        super().__init__(None, faiss_manager, embedding_model, "search_handler")
    
    def get_search_data_schema(self) -> Dict[str, Any]:
        """Get the input schema for data search.
        
        Returns:
            Schema definition dictionary
        """
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text query to search for"},
                "limit": {"type": "integer", "description": "Maximum number of results to return (default: 10)"}
            },
            "required": ["query"]
        }
    
    def search_data(self, arguments: Optional[Dict[str, Any]]) -> List[types.TextContent]:
        """Search for similar data in stored HubSpot API responses.
        
        Args:
            arguments: Tool arguments containing search query and limit
            
        Returns:
            Text response with search results
        """
        # Validate required parameters
        self.validate_required_arguments(arguments, ["query"])
        
        query = arguments["query"]
        limit = self.get_argument_with_default(arguments, "limit", 10)
        limit = int(limit) if limit is not None else 10
        
        try:
            results, _ = search_in_faiss(
                faiss_manager=self.faiss_manager,
                query=query,
                model=self.embedding_model,
                limit=limit
            )
            
            return self.create_text_response(results)
        except Exception as e:
            self.logger.error(f"Error searching in FAISS: {str(e)}")
            return self.create_text_response(f"Error searching data: {str(e)}")
