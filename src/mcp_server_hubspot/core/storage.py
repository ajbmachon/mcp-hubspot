"""
Storage handling for HubSpot conversation threads.
"""
import json
import logging
import pathlib
from typing import Any, Dict

logger = logging.getLogger('mcp_hubspot_client.storage')

class ThreadStorage:
    """Storage handler for conversation threads."""
    
    def __init__(self, storage_dir: pathlib.Path):
        """Initialize storage with directory path.
        
        Args:
            storage_dir: Directory to store thread data
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(exist_ok=True)
        self.threads_file = self.storage_dir / "conversation_threads.json"
        self.threads_cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load conversation threads from cache file if it exists.
        
        Returns:
            Thread data or empty structure
        """
        try:
            if self.threads_file.exists():
                with open(self.threads_file, "r") as f:
                    return json.load(f)
            return {"results": [], "paging": {"next": {"after": None}}}
        except Exception as e:
            logger.error(f"Error loading threads cache: {str(e)}")
            return {"results": [], "paging": {"next": {"after": None}}}
    
    def save_cache(self, threads_data: Dict[str, Any]) -> None:
        """Save conversation threads to cache file.
        
        Args:
            threads_data: Thread data to save
        """
        try:
            with open(self.threads_file, "w") as f:
                json.dump(threads_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving threads cache: {str(e)}")
    
    def get_cached_threads(self) -> Dict[str, Any]:
        """Get the current cached threads.
        
        Returns:
            Cached thread data
        """
        return self.threads_cache
    
    def update_cache(self, threads_data: Dict[str, Any]) -> None:
        """Update the cache with new thread data.
        
        Args:
            threads_data: New thread data
        """
        self.threads_cache = threads_data
        self.save_cache(threads_data)
