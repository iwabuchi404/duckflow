from typing import List, Optional
from companion.modules.archive import ArchiveStorage

class MemoryTool:
    """
    Tools for accessing long-term memory (archives).
    """
    def __init__(self):
        self.storage = ArchiveStorage()

    def search_archives(self, query: str, limit: int = 5) -> str:
        """
        Search past conversation logs (archives) for specific keywords.
        Use this when you need to recall details that are no longer in the current context.
        
        Args:
            query: Keywords to search for (space-separated for AND search)
            limit: Maximum number of results to return (default: 5)
            
        Returns:
            Formatted string of found messages
        """
        results = self.storage.search(query, limit=limit)
        
        if not results:
            return f"No archives found matching query: '{query}'"
            
        formatted = []
        for msg in results:
            timestamp = msg.get("timestamp", "")[:19] # Truncate microseconds
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            
            # Truncate content if too long for preview
            if len(content) > 300:
                content = content[:297] + "..."
                
            formatted.append(f"[{timestamp}] {role}: {content}")
            
        count = len(results)
        return f"Found {count} archived messages:\n\n" + "\n\n".join(formatted)
