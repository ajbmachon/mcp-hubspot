"""
Handler for contact-related HubSpot operations.
"""
from typing import Any, Dict, List, Optional
import json

import mcp.types as types

from ..hubspot_client import ApiException
from .base_handler import BaseHandler

class ContactHandler(BaseHandler):
    """Handler for contact-related HubSpot tools."""
    
    def __init__(self, hubspot_client, faiss_manager, embedding_model):
        """Initialize the contact handler.
        
        Args:
            hubspot_client: HubSpot client
            faiss_manager: FAISS vector store manager
            embedding_model: Sentence transformer model
        """
        super().__init__(hubspot_client, faiss_manager, embedding_model, "contact_handler")
    
    def get_create_contact_schema(self) -> Dict[str, Any]:
        """Get the input schema for creating a contact.
        
        Returns:
            Schema definition dictionary
        """
        return {
            "type": "object",
            "properties": {
                "firstname": {"type": "string", "description": "Contact's first name"},
                "lastname": {"type": "string", "description": "Contact's last name"},
                "email": {"type": "string", "description": "Contact's email address"},
                "properties": {"type": "object", "description": "Additional contact properties"}
            },
            "required": ["firstname", "lastname"]
        }
    
    def get_active_contacts_schema(self) -> Dict[str, Any]:
        """Get the input schema for active contacts.
        
        Returns:
            Schema definition dictionary
        """
        return {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of contacts to return (default: 10)"}
            }
        }
    
    def create_contact(self, arguments: Optional[Dict[str, Any]]) -> List[types.TextContent]:
        """Create a new contact in HubSpot.
        
        Args:
            arguments: Tool arguments containing contact information
            
        Returns:
            Text response with result
        """
        self.validate_required_arguments(arguments, ["firstname", "lastname"])
        
        try:
            from hubspot.crm.contacts import PublicObjectSearchRequest
            
            firstname = arguments["firstname"]
            lastname = arguments["lastname"]
            company = arguments.get("properties", {}).get("company")
            
            # Search for existing contacts with same name and company
            filter_groups = [{
                "filters": [
                    {
                        "propertyName": "firstname",
                        "operator": "EQ",
                        "value": firstname
                    },
                    {
                        "propertyName": "lastname",
                        "operator": "EQ",
                        "value": lastname
                    }
                ]
            }]
            
            # Add company filter if provided
            if company:
                filter_groups[0]["filters"].append({
                    "propertyName": "company",
                    "operator": "EQ",
                    "value": company
                })
            
            search_request = PublicObjectSearchRequest(
                filter_groups=filter_groups
            )
            
            search_response = self.hubspot.client.crm.contacts.search_api.do_search(
                public_object_search_request=search_request
            )
            
            if search_response.total > 0:
                # Contact already exists
                return self.create_text_response(
                    f"Contact already exists: {search_response.results[0].to_dict()}"
                )
            
            # If no existing contact found, proceed with creation
            properties = {
                "firstname": firstname,
                "lastname": lastname
            }
            
            # Add email if provided
            if "email" in arguments:
                properties["email"] = arguments["email"]
            
            # Add any additional properties
            if "properties" in arguments:
                properties.update(arguments["properties"])
            
            # Create contact using SimplePublicObjectInputForCreate
            from hubspot.crm.contacts import SimplePublicObjectInputForCreate
            
            simple_public_object_input = SimplePublicObjectInputForCreate(
                properties=properties
            )
            
            api_response = self.hubspot.client.crm.contacts.basic_api.create(
                simple_public_object_input_for_create=simple_public_object_input
            )
            return self.create_text_response(str(api_response.to_dict()))
                
        except ApiException as e:
            return self.create_text_response(f"HubSpot API error: {str(e)}")
        except Exception as e:
            return self.create_text_response(f"Error: {str(e)}")
    
    def get_active_contacts(self, arguments: Optional[Dict[str, Any]]) -> List[types.TextContent]:
        """Get most recently active contacts from HubSpot.
        
        Args:
            arguments: Tool arguments containing limit parameter
            
        Returns:
            Text response with contact data
        """
        limit = self.get_argument_with_default(arguments, "limit", 10)
        
        # Ensure limit is an integer
        limit = int(limit) if limit is not None else 10
        
        results = self.hubspot.get_recent_contacts(limit=limit)
        
        # Store in FAISS for future reference
        try:
            data = json.loads(results)
            metadata_extras = {"limit": limit}
            self.store_in_faiss_safely(data, "contact", metadata_extras)
        except Exception as e:
            self.logger.error(f"Error parsing contact data: {str(e)}")
        
        return self.create_text_response(results)
