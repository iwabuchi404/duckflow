import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class ArchiveStorage:
    """
    Manages long-term storage of conversation logs in JSONL format.
    Handles archiving of pruned messages and searching through archives.
    """
    
    def __init__(self, base_dir: str = "logs/archives"):
        self.base_dir = Path(base_dir)
        self._ensure_directory()

    def _ensure_directory(self):
        """Ensure the archive directory exists."""
        if not self.base_dir.exists():
            try:
                self.base_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created archive directory: {self.base_dir}")
            except Exception as e:
                logger.error(f"Failed to create archive directory: {e}")

    def _get_today_file_path(self) -> Path:
        """Get the path for today's archive file."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.base_dir / f"{today}.jsonl"

    def archive_messages(self, messages: List[Dict]):
        """
        Append messages to the archive file.
        
        Args:
            messages: List of message dictionaries to archive
        """
        if not messages:
            return

        file_path = self._get_today_file_path()
        
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                for msg in messages:
                    # Add timestamp if missing
                    if "timestamp" not in msg:
                        msg["timestamp"] = datetime.now().isoformat()
                    
                    # Create a record wrapper
                    record = {
                        "timestamp": msg.get("timestamp"),
                        "role": msg.get("role", "unknown"),
                        "content": msg.get("content", ""),
                        "metadata": msg.get("metadata", {})
                    }
                    
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
            logger.info(f"Archived {len(messages)} messages to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to archive messages: {e}")

    def search(
        self, 
        query: str, 
        limit: int = 10,
        date_range: Optional[Tuple[date, date]] = None
    ) -> List[Dict]:
        """
        Search archived messages for keywords.
        
        Args:
            query: Keywords to search for (space-separated for AND search)
            limit: Maximum number of results to return
            date_range: Optional tuple of (start_date, end_date) to limit search
            
        Returns:
            List of matching records, sorted by timestamp (newest first)
        """
        keywords = query.lower().split()
        results = []
        
        # List all jsonl files
        if not self.base_dir.exists():
            return []
            
        files = sorted(list(self.base_dir.glob("*.jsonl")), reverse=True)
        
        count = 0
        for file_path in files:
            if count >= limit:
                break
                
            # Parse date from filename
            try:
                file_date_str = file_path.stem
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                
                # Check date range
                if date_range:
                    start, end = date_range
                    if not (start <= file_date <= end):
                        continue
            except ValueError:
                continue

            # Read file (read from end would be better for performance, but simple read required here)
            # For "newest first", we read lines and process in reverse
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    
                for line in reversed(lines):
                    if count >= limit:
                        break
                        
                    try:
                        record = json.loads(line)
                        content = record.get("content", "").lower()
                        
                        # AND Search
                        if all(kw in content for kw in keywords):
                            results.append(record)
                            count += 1
                            
                    except json.JSONDecodeError:
                        continue
                        
            except Exception as e:
                logger.warning(f"Error reading archive file {file_path}: {e}")
                
        return results
