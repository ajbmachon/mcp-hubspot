#!/usr/bin/env python
"""
Test script for retrieving closed tickets from HubSpot.
This script directly uses the HubSpot client to test different approaches
to get closed tickets and provides detailed debug output.
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add src directory to path to allow direct imports
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Import HubSpot client
from mcp_server_hubspot.hubspot_client import HubSpotClient
from hubspot import HubSpot
from hubspot.crm.tickets import PublicObjectSearchRequest

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_closed_tickets")

class TicketTester:
    """Test different approaches to get closed tickets from HubSpot."""
    
    def __init__(self, access_token: Optional[str] = None):
        """Initialize with HubSpot API token.
        
        Args:
            access_token: HubSpot API token (if None, uses HUBSPOT_ACCESS_TOKEN env var)
        """
        self.access_token = access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("HUBSPOT_ACCESS_TOKEN environment variable is required")
        
        # Initialize HubSpot client
        self.hubspot_client = HubSpotClient(self.access_token)
        self.direct_client = HubSpot(access_token=self.access_token)
        
        logger.info("HubSpot client initialized")
    
    def test_get_tickets_standard(self):
        """Test getting closed tickets using the standard client method."""
        logger.info("Testing standard client method with 'Closed' value")
        try:
            results = self.hubspot_client.get_tickets(
                criteria="Closed",
                limit=20,
                max_retries=3,
                retry_delay=1.0
            )
            logger.info(f"Results: {json.dumps(results, indent=2)}")
            return results
        except Exception as e:
            logger.error(f"Error using standard method: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def test_get_tickets_lowercase(self):
        """Test getting closed tickets using lowercase 'closed'."""
        logger.info("Testing standard client method with lowercase 'closed' value")
        try:
            # This is a workaround that bypasses type checking
            results = self.hubspot_client.tickets.get_tickets(
                criteria="closed",  # lowercase to match current implementation
                limit=20,
                max_retries=3,
                retry_delay=1.0
            )
            logger.info(f"Results: {json.dumps(results, indent=2)}")
            return results
        except Exception as e:
            logger.error(f"Error using lowercase method: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def test_direct_search_api(self):
        """Test getting closed tickets using direct search API with multiple filters."""
        logger.info("Testing direct search API with multiple filter approaches")
        
        # Try multiple approaches to filter for closed tickets
        filter_groups_approaches = [
            # Approach 1: Using hs_pipeline_stage=closed
            [{
                "filters": [{
                    "propertyName": "hs_pipeline_stage",
                    "operator": "EQ",
                    "value": "closed"
                }]
            }],
            
            # Approach 2: Using hs_pipeline_stage=CLOSED (uppercase)
            [{
                "filters": [{
                    "propertyName": "hs_pipeline_stage",
                    "operator": "EQ",
                    "value": "CLOSED"
                }]
            }],
            
            # Approach 3: Using hs_ticket_status=CLOSED
            [{
                "filters": [{
                    "propertyName": "hs_ticket_status",
                    "operator": "EQ",
                    "value": "CLOSED"
                }]
            }],
            
            # Approach 4: Using status=CLOSED
            [{
                "filters": [{
                    "propertyName": "status",
                    "operator": "EQ",
                    "value": "CLOSED"
                }]
            }],
            
            # Approach 5: Using pipeline stage contains "closed"
            [{
                "filters": [{
                    "propertyName": "hs_pipeline_stage",
                    "operator": "CONTAINS_TOKEN",
                    "value": "closed"
                }]
            }]
        ]
        
        results = []
        
        # Try each approach
        for idx, filter_groups in enumerate(filter_groups_approaches):
            approach_name = f"Approach {idx+1}"
            logger.info(f"Trying {approach_name}")
            try:
                # Create search request
                search_request = PublicObjectSearchRequest(
                    filter_groups=filter_groups,
                    sorts=[{
                        "propertyName": "hs_lastmodifieddate",
                        "direction": "DESCENDING"
                    }],
                    limit=20,
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
                
                # Execute search
                search_response = self.direct_client.crm.tickets.search_api.do_search(
                    public_object_search_request=search_request
                )
                
                # Convert results to dict
                tickets_dict = [ticket.to_dict() for ticket in search_response.results]
                
                # Store results
                result = {
                    "approach": approach_name,
                    "filter": filter_groups,
                    "count": len(tickets_dict),
                    "tickets": tickets_dict
                }
                results.append(result)
                
                logger.info(f"{approach_name} found {len(tickets_dict)} tickets")
                if tickets_dict:
                    # If we found tickets, log the first one's details
                    logger.info(f"First ticket sample: {json.dumps(tickets_dict[0], indent=2)}")
                
            except Exception as e:
                logger.error(f"Error with {approach_name}: {str(e)}", exc_info=True)
                results.append({
                    "approach": approach_name,
                    "filter": filter_groups,
                    "error": str(e)
                })
        
        return results
    
    def test_get_pipelines(self):
        """Test getting pipeline information to understand ticket stages."""
        logger.info("Getting pipeline information")
        try:
            pipelines = self.direct_client.crm.pipelines.pipelines_api.get_all("tickets")
            
            pipeline_data = []
            for pipeline in pipelines.results:
                stages = []
                for stage in pipeline.stages:
                    stages.append({
                        "id": stage.id,
                        "label": stage.label,
                        "display_order": stage.display_order,
                        "is_closed": getattr(stage, "is_closed", False)
                    })
                
                pipeline_data.append({
                    "id": pipeline.id,
                    "label": pipeline.label,
                    "display_order": pipeline.display_order,
                    "stages": stages
                })
            
            logger.info(f"Pipeline data: {json.dumps(pipeline_data, indent=2)}")
            return pipeline_data
        except Exception as e:
            logger.error(f"Error getting pipelines: {str(e)}", exc_info=True)
            return {"error": str(e)}


def main():
    """Run all tests and print results."""
    tester = TicketTester()
    
    # Test 1: Get pipeline information
    print("\n=== Pipeline Information ===")
    pipeline_data = tester.test_get_pipelines()
    print(f"Found {len(pipeline_data)} pipelines")
    
    # Test 2: Standard method
    print("\n=== Standard Method with 'Closed' ===")
    standard_results = tester.test_get_tickets_standard()
    
    # Test 3: Lowercase method
    print("\n=== Lowercase Method with 'closed' ===")
    lowercase_results = tester.test_get_tickets_lowercase()
    
    # Test 4: Direct search API with multiple approaches
    print("\n=== Direct Search API with Multiple Approaches ===")
    direct_results = tester.test_direct_search_api()
    
    # Save all results to a file
    all_results = {
        "timestamp": datetime.now().isoformat(),
        "pipelines": pipeline_data,
        "standard_method": standard_results,
        "lowercase_method": lowercase_results,
        "direct_search": direct_results
    }
    
    output_file = "closed_ticket_test_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nAll test results saved to {output_file}")
    
    # Print summary
    print("\n=== Summary ===")
    print(f"Pipelines: {len(pipeline_data)}")
    
    # Handle standard results
    if isinstance(standard_results, dict) and "error" in standard_results:
        print(f"Standard method: Error - {standard_results['error']}")
    elif isinstance(standard_results, dict):
        print(f"Standard method: {len(standard_results.get('results', []))} tickets")
    else:
        print(f"Standard method: Unexpected result format")
    
    # Handle lowercase results - it might be a JSON string
    if isinstance(lowercase_results, str):
        try:
            # Try to parse it as JSON
            lowercase_dict = json.loads(lowercase_results)
            if "error" in lowercase_dict:
                print(f"Lowercase method: Error - {lowercase_dict['error']}")
            else:
                print(f"Lowercase method: {len(lowercase_dict.get('results', []))} tickets")
        except json.JSONDecodeError:
            print(f"Lowercase method: Error - {lowercase_results}")
    elif isinstance(lowercase_results, dict) and "error" in lowercase_results:
        print(f"Lowercase method: Error - {lowercase_results['error']}")
    elif isinstance(lowercase_results, dict):
        print(f"Lowercase method: {len(lowercase_results.get('results', []))} tickets")
    else:
        print(f"Lowercase method: Unexpected result format")
    
    # Handle direct search results
    print("Direct search results:")
    for result in direct_results:
        if "error" in result:
            print(f"  {result['approach']}: Error")
        else:
            print(f"  {result['approach']}: {result.get('count', 0)} tickets")


if __name__ == "__main__":
    main()
