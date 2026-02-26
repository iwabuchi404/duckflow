import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from companion.base.llm_client import get_default_client, LLMClient

logger = logging.getLogger(__name__)

class ExecutionSummary(BaseModel):
    """Schema for LLM-generated execution summary."""
    summary: str = Field(..., description="Natural language summary of the execution results")
    highlights: List[str] = Field(default_factory=list, description="Key highlights or important points")
    next_steps: str = Field(default="", description="Suggested next steps or recommendations")

class ResultSummarizer:
    """
    Result Summarizer for Duckflow v4.
    Uses LLM to generate natural language summaries of task execution results.
    """
    
    def __init__(self, llm_client: LLMClient = get_default_client()):
        self.llm = llm_client
    
    async def summarize_execution(self, execution_data: Dict[str, Any]) -> str:
        """
        Generate a natural language summary of task execution results.
        
        Args:
            execution_data: Dictionary containing execution results
                - total: Total number of tasks
                - completed: Number of completed tasks
                - failed: Number of failed tasks
                - execution_log: Detailed log of each task
                
        Returns:
            Natural language summary string
        """
        logger.info("Generating execution summary with LLM...")
        
        # Build prompt for LLM
        prompt = self._build_summary_prompt(execution_data)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes task execution results in a clear and concise manner."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # Call LLM for summary
            summary_obj = await self.llm.chat(messages, response_model=ExecutionSummary)
            
            # Format the summary nicely
            formatted_summary = self._format_summary(summary_obj, execution_data)
            
            logger.info("Execution summary generated successfully")
            return formatted_summary
            
        except Exception as e:
            logger.error(f"Failed to generate LLM summary: {e}")
            # Fallback to simple summary
            return self._simple_summary(execution_data)
    
    def _build_summary_prompt(self, execution_data: Dict[str, Any]) -> str:
        """Build the prompt for LLM summarization."""
        total = execution_data.get("total", 0)
        completed = execution_data.get("completed", 0)
        failed = execution_data.get("failed", 0)
        logs = execution_data.get("execution_log", [])
        
        prompt_parts = [
            f"I executed {total} tasks with the following results:",
            f"- Completed: {completed}",
            f"- Failed: {failed}",
            "",
            "Detailed task results:"
        ]
        
        for i, log_entry in enumerate(logs, 1):
            task_title = log_entry.get("task_title", f"Task {i}")
            status = log_entry.get("status", "unknown")
            
            if status == "completed":
                result = log_entry.get("result", "N/A")
                prompt_parts.append(f"{i}. ✅ {task_title}: {result}")
            else:
                error = log_entry.get("error", "Unknown error")
                prompt_parts.append(f"{i}. ❌ {task_title}: Failed - {error}")
        
        prompt_parts.extend([
            "",
            "Please provide:",
            "1. A concise summary of what was accomplished",
            "2. Key highlights (2-3 bullet points)",
            "3. Suggested next steps if applicable"
        ])
        
        return "\n".join(prompt_parts)
    
    def _format_summary(self, summary_obj: ExecutionSummary, execution_data: Dict[str, Any]) -> str:
        """Format the LLM-generated summary into a nice output."""
        lines = [
            "\n" + "=" * 60,
            "📝 Execution Summary (AI-Generated)",
            "=" * 60,
            "",
            summary_obj.summary,
            ""
        ]
        
        if summary_obj.highlights:
            lines.append("🔑 Key Highlights:")
            for highlight in summary_obj.highlights:
                lines.append(f"  • {highlight}")
            lines.append("")
        
        if summary_obj.next_steps:
            lines.append("➡️  Next Steps:")
            lines.append(f"  {summary_obj.next_steps}")
            lines.append("")
        
        # Add stats
        total = execution_data.get("total", 0)
        completed = execution_data.get("completed", 0)
        failed = execution_data.get("failed", 0)
        success_rate = execution_data.get("success_rate", 0) * 100
        
        lines.extend([
            "📊 Statistics:",
            f"  Total: {total} | Completed: {completed} | Failed: {failed} | Success: {success_rate:.1f}%",
            "=" * 60
        ])
        
        return "\n".join(lines)
    
    def _simple_summary(self, execution_data: Dict[str, Any]) -> str:
        """Fallback to simple summary if LLM fails."""
        total = execution_data.get("total", 0)
        completed = execution_data.get("completed", 0)
        failed = execution_data.get("failed", 0)
        
        lines = [
            "\n" + "=" * 60,
            "📝 Execution Summary (Simple Mode)",
            "=" * 60,
            f"Executed {total} tasks: {completed} succeeded, {failed} failed.",
            "=" * 60
        ]
        
        return "\n".join(lines)
