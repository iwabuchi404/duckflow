#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Optional, Dict, Any
from companion.base.llm_client import LLMClient
from companion.prompts.sub_llm_prompts import (
    SUMMARIZER_SYSTEM_PROMPT,
    ANALYZER_SYSTEM_PROMPT,
    CODEGEN_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

class SubLLMManager:
    """
    Manages delegation of tasks to specialized Sub-LLMs with guardrails.
    """
    
    # 1 character ≈ 0.25 tokens. 32,000 chars ≈ 8,000 tokens.
    MAX_CHAR_LIMIT = 32000 
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def validate_input_size(self, text: str) -> bool:
        """
        Check if the input size is within safety limits.
        """
        return len(text) <= self.MAX_CHAR_LIMIT

    async def call_worker(
        self, 
        system_prompt: str, 
        user_content: str,
        temperature: float = 0.2
    ) -> str:
        """
        Invoke a Sub-LLM worker.
        """
        # Guardrail check
        if not self.validate_input_size(user_content):
            error_msg = (
                f"Error: Input context size exceeded the safety limit ({self.MAX_CHAR_LIMIT} chars).\n"
                "Please reduce the context range or split the task."
            )
            logger.error(error_msg)
            return error_msg

        logger.info(f"Delegating to Sub-LLM worker (input size: {len(user_content)} chars)")
        
        # Prepare messages for Sub-LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            # Note: We use the same LLM client for now as per user request.
            # In the future, we can map to cheaper models here.
            response = await self.llm.chat(
                messages=messages,
                temperature=temperature,
                raw=True
            )
            return response.strip()
        except Exception as e:
            error_msg = f"Sub-LLM Worker Error: {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def summarize(self, text: str) -> str:
        """Compress text using Summarization Sub-LLM."""
        return await self.call_worker(SUMMARIZER_SYSTEM_PROMPT, text)

    async def analyze_structure(self, code: str) -> str:
        """Analyze code structure using Analyzer Sub-LLM."""
        return await self.call_worker(ANALYZER_SYSTEM_PROMPT, code)

    async def generate_code(self, instruction: str, context: str) -> str:
        """Generate code using CodeGen Sub-LLM."""
        prompt = f"[Instruction]\n{instruction}\n\n[Context]\n{context}"
        return await self.call_worker(CODEGEN_SYSTEM_PROMPT, prompt, temperature=0.7)
