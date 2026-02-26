#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import logging
from typing import Optional, List, Dict, Any
from companion.modules.sub_llm_manager import SubLLMManager
from companion.tools.file_ops import file_ops
from companion.ui import ui

logger = logging.getLogger(__name__)

class SubLLMTools:
    """
    Sub-LLM powered tools for context compression, analysis, and code generation.
    """
    
    def __init__(self, manager: SubLLMManager):
        self.manager = manager

    async def summarize_context(self, content: str) -> str:
        """
        Summarize long text or conversation logs into a concise bullet-point format.
        Use this to manage context window consumption.

        Args:
            content: 要約対象のテキスト（会話ログ、ファイル内容等）

        Returns:
            箇条書き形式の要約テキスト
        """
        logger.info("Tool summarize_context called")
        return await self.manager.summarize(content)

    async def analyze_structure(self, path: str) -> str:
        """
        Generate a structural outline (Code Map) of a file.
        Includes classes, functions, and their signatures without bodies.

        Args:
            path: Path to the target source file.

        Returns:
            クラス・関数のシグネチャ一覧（コード本体なし）、またはエラーメッセージ
        """
        logger.info(f"Tool analyze_structure called for {path}")
        try:
            # Read entire file (for initial analysis)
            res = await file_ops.read_file(path, max_lines=5000)
            if "error" in res:
                return f"Error reading file: {res['error']}"
            
            code = res["content"]
            return await self.manager.analyze_structure(code)
        except Exception as e:
            return f"Error analyzing structure: {str(e)}"

    async def generate_code(self, path: str, content: str) -> str:
        """
        Generate code using a specialized Sub-LLM worker.
        Returns a Sym-Ops formatted response summary without code body.

        **Main LLM Usage Guide:**
        - Purpose: Generate code based on instructions and context.
        - Usage:
          1. Gather necessary context (e.g., `read_file` on related files).
          2. Call `generate_code` with `[Instruction]` and `[Context]` sections.
          3. The tool handles saving. **You will NOT receive the generated code content back.**
          4. You will receive a status summary (Success/Fail/Line count).
          5. If you need to verify the saved content, use `read_file` afterwards.

        **Constraints:**
        - This tool requires user confirmation. Do NOT use inside `::execute_batch`.
        - Ensure `[Context]` contains relevant existing code for style consistency.

        Sym-Ops format:
        ::generate_code @new_module.py
        <<<
        [Instruction]
        Implement a function that validates email addresses using regex.

        [Context]
        utils.py:1-20
        >>>

        Args:
            path: Target file path to save the generated code.
            content: Instruction and Context block using [Instruction] and [Context] sections.
                     [Context] can include 'filename:start-end' or 'filename'.
        """
        logger.info(f"Tool generate_code called for {path}")

        # 1. Parse content sections
        # メインLLMが正しいフォーマットで渡してくれない場合のフォールバック
        instruction = ""
        context = ""

        inst_match = re.search(r'\[Instruction\](.*?)(?=\[Context\]|$)', content, re.DOTALL | re.IGNORECASE)
        ctx_match = re.search(r'\[Context\](.*?)(?=\[Instruction\]|$)', content, re.DOTALL | re.IGNORECASE)

        if inst_match:
            instruction = inst_match.group(1).strip()
        else:
            instruction = content  # フォールバック

        if ctx_match:
            context = ctx_match.group(1).strip()

        if not instruction:
            return (
                f"::status error\n"
                f"::generate_code @{path}\n"
                f"<<<\n"
                f"Error: No [Instruction] section found.\n"
                f">>>"
            )

        try:
            # 2. Fetch context contents if context references are provided
            context_text = ""
            if not context:
                # Contextセクションがない場合
                context_text = ""
            elif '\n' in context and self._is_file_references(context):
                # Contextにファイル参照（filename:start-end または filename）が含まれている場合
                context_refs = [line.strip() for line in context.split('\n') if line.strip()]
                context_text = await self._fetch_all_context(context_refs)
                logger.info(f"Context fetched from files (length: {len(context_text)} chars)")
            else:
                # Contextに直接コードが含まれている場合
                context_text = context
                logger.info(f"Direct code context provided (length: {len(context_text)} chars)")

            # 3. Call Sub-LLM worker
            logger.info("Calling Sub-LLM worker for code generation...")
            generated_code = await self.manager.generate_code(instruction, context_text)

            if generated_code.startswith("Error:"):
                logger.error(f"Sub-LLM returned error: {generated_code}")
                return (
                    f"::status error\n"
                    f"::generate_code @{path}\n"
                    f"<<<\n"
                    f"{generated_code}\n"
                    f">>>"
                )

            logger.info(f"Code generated successfully (length: {len(generated_code)} chars)")

            # 4. Preview and Confirm
            ui.print_info(f"🛠️ Code generation for [bold]{path}[/bold]")
            ui.print_code(generated_code, language=self._guess_language(path))

            logger.info("Waiting for user confirmation...")
            confirmed = ui.confirm_action(f"Apply this generated code to {path}?")
            logger.info(f"User confirmation: {confirmed}")

            if confirmed:
                try:
                    logger.info("Writing generated code to file...")
                    await file_ops.write_file(path, generated_code)
                    lines_count = len(generated_code.splitlines())
                    logger.info(f"File written successfully: {lines_count} lines")

                    # Success Response: コード本体は返さず、結果概要のみ返す
                    return (
                        f"::status ok\n"
                        f"::generate_code @{path}\n"
                        f"<<<\n"
                        f"Success: Code saved.\n"
                        f"Lines: {lines_count}\n"
                        f">>>"
                    )
                except Exception as e:
                    logger.error(f"Error saving generated code: {e}", exc_info=True)
                    return (
                        f"::status error\n"
                        f"::generate_code @{path}\n"
                        f"<<<\n"
                        f"File Write Error: {str(e)}\n"
                        f">>>"
                    )
            else:
                # Cancelled Response
                logger.info("User cancelled code generation")
                return (
                    f"::status cancelled\n"
                    f"::generate_code @{path}\n"
                    f"<<<\n"
                    f"User cancelled. No changes made.\n"
                    f">>>"
                )

        except Exception as e:
            logger.error(f"Error in generate_code: {e}", exc_info=True)
            return (
                f"::status error\n"
                f"::generate_code @{path}\n"
                f"<<<\n"
                f"Internal Error: {str(e)}\n"
                f">>>"
            )

    async def _fetch_all_context(self, refs: List[str]) -> str:
        """Resolve and read all context files/ranges."""
        parts = []
        for ref in refs:
            try:
                if ':' in ref:
                    # e.g. "path/file.py:10-50"
                    f_path, line_range = ref.rsplit(':', 1)
                    if '-' in line_range:
                        start, end = line_range.split('-', 1)
                        start_line = int(start)
                        max_lines = max(1, int(end) - start_line + 1)
                    else:
                        start_line = int(line_range)
                        max_lines = 1
                    res = await file_ops.read_file(f_path, start_line=start_line, max_lines=max_lines)
                else:
                    res = await file_ops.read_file(ref)
                
                if "error" in res:
                    parts.append(f"--- {ref} ---\nError: {res['error']}")
                else:
                    parts.append(f"--- {res['path']} (lines {res['showing_lines']}) ---\n{res['content']}")
            except Exception as e:
                parts.append(f"--- {ref} ---\nError loading context: {str(e)}")
        
        return "\n\n".join(parts)

    def _is_file_references(self, text: str) -> bool:
        """
        Check if the given text contains file references (filename or filename:start-end format).

        A file reference is identified by:
        - Contains a filename with extension (e.g., .py, .js, .md)
        - May include line range (e.g., file.py:10-50 or file.py:10)

        Returns:
            True if text appears to contain file references, False otherwise.
        """
        # Common code file extensions
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
                        '.rb', '.php', '.c', '.cpp', '.h', '.hpp', '.cs',
                        '.swift', '.kt', '.dart', '.lua', '.sh', '.bash',
                        '.yml', '.yaml', '.json', '.xml', '.html', '.css',
                        '.md', '.txt', '.sql', '.pl', '.r', '.m'}

        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line contains a file extension (heuristic for file references)
            for ext in code_extensions:
                if ext in line:
                    # Additional check: if it looks like a file path (contains / or . or ends with ext)
                    if '/' in line or '.' in line or line.endswith(ext):
                        return True

        return False

    def _guess_language(self, path: str) -> str:
        ext = path.split('.')[-1].lower()
        mapping = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'html': 'html',
            'css': 'css',
            'md': 'markdown',
            'json': 'json',
            'yml': 'yaml',
            'yaml': 'yaml'
        }
        return mapping.get(ext, 'text')
