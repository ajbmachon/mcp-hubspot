"""
Client for HubSpot company-related operations.
"""
import json
import logging
from typing import Any, Dict, List

from hubspot import HubSpot
from hubspot.crm.companies import PublicObjectSearchRequest
from hubspot.crm.contacts.exceptions import ApiException

from ..core.formatters import convert_datetime_fields
from ..core.error_handler import handle_hubspot_errors

logger = logging.getLogger('mcp_hubspot_client.company')

class CompanyClient:
    """Client for HubSpot company-related operations."""
    
    def __init__(self, hubspot_client: HubSpot, access_token: str):
        """Initialize with HubSpot client instance.
        
        Args:
            hubspot_client: Initialized HubSpot client
            access_token: HubSpot API access token
        """
        self.client = hubspot_client
        self.access_token = access_token
    
    @handle_hubspot_errors
    def get_recent(self, limit: int = 10) -> str:
        """Get most recently active companies from HubSpot.
        
        Args:
            limit: Maximum number of companies to return (default: 10)
            
        Returns:
            JSON string with company data
        """
        search_request = self._create_company_search_request(limit)
        search_response = self.client.crm.companies.search_api.do_search(
            public_object_search_request=search_request
        )
        
        companies_dict = [company.to_dict() for company in search_response.results]
        converted_companies = convert_datetime_fields(companies_dict)
        return json.dumps(converted_companies)
    
    def _create_company_search_request(self, limit: int) -> PublicObjectSearchRequest:
        """Create a search request for companies sorted by last modified date.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            Configured search request object
        """
        return PublicObjectSearchRequest(
            sorts=[{
                "propertyName": "lastmodifieddate",
                "direction": "DESCENDING"
            }],
            limit=limit,
            properties=["name", "domain", "website", "phone", "industry", "hs_lastmodifieddate"]
        )
        
    @handle_hubspot_errors
    def get_activity(self, company_id: str) -> str:
        """Get activity history for a specific company.
        
        Args:
            company_id: HubSpot company ID
            
        Returns:
            JSON string with company activity data
        """
        associated_engagements = self._get_company_engagements(company_id)
        engagement_ids = self._extract_engagement_ids(associated_engagements)
        activities = self._get_engagement_details(engagement_ids)
        
        converted_activities = convert_datetime_fields(activities)
        return json.dumps(converted_activities)
        
    def _get_company_engagements(self, company_id: str) -> Any:
        """Get all engagement IDs associated with the company.
        
        Args:
            company_id: HubSpot company ID
            
        Returns:
            Association response object
        """
        return self.client.crm.associations.v4.basic_api.get_page(
            object_type="companies",
            object_id=company_id,
            to_object_type="engagements",
            limit=500
        )
        
    def _extract_engagement_ids(self, associated_engagements: Any) -> List[str]:
        """Extract engagement IDs from the associations response.
        
        Args:
            associated_engagements: Response from associations API
            
        Returns:
            List of engagement IDs
        """
        engagement_ids = []
        if hasattr(associated_engagements, 'results'):
            for result in associated_engagements.results:
                engagement_ids.append(result.to_object_id)
        return engagement_ids
        
    def _get_engagement_details(self, engagement_ids: List[str]) -> List[Dict[str, Any]]:
        """Get detailed information for each engagement.
        
        Args:
            engagement_ids: List of engagement IDs to retrieve
            
        Returns:
            List of formatted engagement details
        """
        activities = []
        for engagement_id in engagement_ids:
            try:
                engagement_response = self.client.api_request({
                    "method": "GET",
                    "path": f"/engagements/v1/engagements/{engagement_id}"
                }).json()
                
                formatted_engagement = self._format_engagement(engagement_response)
                activities.append(formatted_engagement)
            except Exception as e:
                logger.error(f"Error retrieving engagement {engagement_id}: {str(e)}")
        
        return activities
        
    def _format_engagement(self, engagement_response: Dict[str, Any]) -> Dict[str, Any]:
        """Format the engagement response into a standardized structure.
        
        Args:
            engagement_response: Raw engagement data from API
            
        Returns:
            Formatted engagement data
        """
        engagement_data = engagement_response.get('engagement', {})
        metadata = engagement_response.get('metadata', {})
        
        formatted_engagement = {
            "id": engagement_data.get("id"),
            "type": engagement_data.get("type"),
            "created_at": engagement_data.get("createdAt"),
            "last_updated": engagement_data.get("lastUpdated"),
            "created_by": engagement_data.get("createdBy"),
            "modified_by": engagement_data.get("modifiedBy"),
            "timestamp": engagement_data.get("timestamp"),
            "associations": engagement_response.get("associations", {})
        }
        
        # Add type-specific content formatting
        engagement_type = engagement_data.get("type")
        if engagement_type:
            formatted_engagement["content"] = self._format_engagement_content(
                engagement_type, metadata
            )
        
        return formatted_engagement
    
    def _format_engagement_content(self, engagement_type: str, 
                                 metadata: Dict[str, Any]) -> Any:
        """Format the content of an engagement based on its type.
        
        Args:
            engagement_type: Type of engagement (NOTE, EMAIL, TASK, etc.)
            metadata: Engagement metadata
            
        Returns:
            Formatted content specific to the engagement type
        """
        if engagement_type == "NOTE":
            return metadata.get("body", "")
        elif engagement_type == "EMAIL":
            return self._format_email_content(metadata)
        elif engagement_type == "TASK":
            return self._format_task_content(metadata)
        elif engagement_type == "MEETING":
            return self._format_meeting_content(metadata)
        elif engagement_type == "CALL":
            return self._format_call_content(metadata)
        return {}
    
    def _format_email_content(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Format email-specific content.
        
        Args:
            metadata: Email metadata
            
        Returns:
            Formatted email content
        """
        return {
            "subject": metadata.get("subject", ""),
            "from": self._format_email_participant(metadata.get("from", {})),
            "to": [self._format_email_participant(recipient) 
                  for recipient in metadata.get("to", [])],
            "cc": [self._format_email_participant(recipient) 
                 for recipient in metadata.get("cc", [])],
            "bcc": [self._format_email_participant(recipient) 
                  for recipient in metadata.get("bcc", [])],
            "sender": {
                "email": metadata.get("sender", {}).get("email", "")
            },
            "body": metadata.get("text", "") or metadata.get("html", "")
        }
    
    def _format_email_participant(self, participant: Dict[str, Any]) -> Dict[str, Any]:
        """Format an email participant (recipient, sender, etc.).
        
        Args:
            participant: Participant data
            
        Returns:
            Formatted participant
        """
        return {
            "raw": participant.get("raw", ""),
            "email": participant.get("email", ""),
            "firstName": participant.get("firstName", ""),
            "lastName": participant.get("lastName", "")
        }
    
    def _format_task_content(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Format task-specific content.
        
        Args:
            metadata: Task metadata
            
        Returns:
            Formatted task content
        """
        return {
            "subject": metadata.get("subject", ""),
            "body": metadata.get("body", ""),
            "status": metadata.get("status", ""),
            "for_object_type": metadata.get("forObjectType", "")
        }
    
    def _format_meeting_content(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Format meeting-specific content.
        
        Args:
            metadata: Meeting metadata
            
        Returns:
            Formatted meeting content
        """
        return {
            "title": metadata.get("title", ""),
            "body": metadata.get("body", ""),
            "start_time": metadata.get("startTime"),
            "end_time": metadata.get("endTime"),
            "internal_notes": metadata.get("internalMeetingNotes", "")
        }
    
    def _format_call_content(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Format call-specific content.
        
        Args:
            metadata: Call metadata
            
        Returns:
            Formatted call content
        """
        return {
            "body": metadata.get("body", ""),
            "from_number": metadata.get("fromNumber", ""),
            "to_number": metadata.get("toNumber", ""),
            "duration_ms": metadata.get("durationMilliseconds"),
            "status": metadata.get("status", ""),
            "disposition": metadata.get("disposition", "")
        }
