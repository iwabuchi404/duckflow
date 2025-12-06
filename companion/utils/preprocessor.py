"""
Sym-Ops v2 Preprocessor
Converts various LLM output formats to valid Sym-Ops v2
"""
import re
from typing import Tuple, List
from datetime import datetime


class SymOpsPreprocessor:
    """
    Phase 1: Basic preprocessing
    - Remove preamble
    - Unwrap markdown blocks
    """
    
    def preprocess(self, text: str) -> Tuple[str, List[str]]:
        """
        Apply Phase 1 preprocessing
        
        Returns:
            (processed_text, corrections_applied)
        """
        corrections = []
        original = text
        
        # Remove preamble
        text = self._remove_preamble(text)
        if text != original:
            corrections.append('preamble_removed')
        
        # Unwrap outer markdown block
        original = text
        text = self._unwrap_markdown_block(text)
        if text != original:
            corrections.append('markdown_unwrapped')
        
        return text, corrections
    
    def _remove_preamble(self, text: str) -> str:
        """
        Remove text before first protocol marker
        Handles: "Sure! Here's...", "I'll help you..."
        """
        # Protocol start markers
        markers = ['>>', '::', '<<<']
        
        lines = text.split('\n')
        start_index = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(stripped.startswith(marker) for marker in markers):
                start_index = i
                break
        
        if start_index is None:
            return text  # No markers found
        
        # Skip empty lines before first marker
        while start_index > 0 and not lines[start_index - 1].strip():
            start_index -= 1
        
        return '\n'.join(lines[start_index:])
    
    def _unwrap_markdown_block(self, text: str) -> str:
        """
        Remove outer markdown code block wrapping
        """
        text = text.strip()
        
        # Pattern: ```language\ncontent\n```
        pattern = r'^```[\w]*\n(.*)\n```$'
        match = re.match(pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        
        # Fallback: Remove first and last ``` lines
        lines = text.split('\n')
        
        if lines and lines[0].strip().startswith('```'):
            lines = lines[1:]
        
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        
        return '\n'.join(lines)


class PlainMarkdownConverter:
    """
    Phase 1.5: Plain Markdown → Sym-Ops v2 conversion
    """
    
    def __init__(self):
        self.lang_extensions = {
            'python': 'py',
            'javascript': 'js',
            'typescript': 'ts',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'go': 'go',
            'rust': 'rs',
            'ruby': 'rb',
            'php': 'php',
            'swift': 'swift',
            'kotlin': 'kt',
            'shell': 'sh',
            'bash': 'sh',
            'yaml': 'yaml',
            'json': 'json',
            'sql': 'sql',
            'html': 'html',
            'css': 'css',
        }
    
    def convert(self, text: str) -> Tuple[str, bool]:
        """
        Convert plain markdown to Sym-Ops v2
        
        Returns:
            (converted_text, was_converted)
        """
        # Check if already Sym-Ops format
        if self._has_symops_markers(text):
            return text, False
        
        # Check if looks like markdown
        if self._looks_like_markdown(text):
            text = self._convert_markdown_to_symops(text)
            return text, True
        
        # Plain text → wrap in response
        if text.strip():
            text = self._wrap_in_response(text)
            return text, True
        
        return text, False
    
    def _has_symops_markers(self, text: str) -> bool:
        """Check for Sym-Ops markers"""
        markers = ['>>', '::', '<<<', '>>>']
        lines = text.split('\n')
        # Need at least 2 different markers to be considered Sym-Ops
        found_markers = set()
        for line in lines:
            for marker in markers:
                if line.strip().startswith(marker):
                    found_markers.add(marker)
        return len(found_markers) >= 2
    
    def _looks_like_markdown(self, text: str) -> bool:
        """Detect markdown patterns"""
        patterns = [
            r'^#{1,6}\s+',      # Headers
            r'```',             # Code blocks
            r'^\* ',            # Lists
            r'^\d+\. ',         # Numbered lists
        ]
        return any(re.search(p, text, re.MULTILINE) for p in patterns)
    
    def _convert_markdown_to_symops(self, text: str) -> str:
        """Convert markdown to Sym-Ops v2"""
        # Convert headers to thoughts
        text = self._convert_headers(text)
        
        # Convert code blocks to actions
        text = self._convert_code_blocks(text)
        
        # Add estimated vitals if missing
        text = self._add_vitals(text)
        
        return text
    
    def _convert_headers(self, text: str) -> str:
        """Convert # Headers to >> thoughts"""
        lines = text.split('\n')
        result = []
        
        for line in lines:
            if re.match(r'^#{1,6}\s+', line):
                # Remove # and convert to thought
                content = re.sub(r'^#{1,6}\s+', '', line)
                result.append(f'>> {content}')
            else:
                result.append(line)
        
        return '\n'.join(result)
    
    def _convert_code_blocks(self, text: str) -> str:
        """Convert ```code``` to ::create_file"""
        lines = text.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Detect code block start
            if line.strip().startswith('```'):
                lang = line.strip()[3:].strip() or 'txt'
                
                # Infer filename from context
                context = result[-10:] if len(result) >= 10 else result
                filename = self._infer_filename(context, lang)
                
                # Collect code
                i += 1
                code_lines = []
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                
                # Add Sym-Ops action
                result.append('')
                result.append(f'::create_file @{filename}')
                result.append('<<<')
                result.extend(code_lines)
                result.append('>>>')
            else:
                result.append(line)
            
            i += 1
        
        return '\n'.join(result)
    
    def _infer_filename(self, context_lines: List[str], lang: str) -> str:
        """Infer filename from context"""
        context = ' '.join(context_lines).lower()
        
        # Keyword patterns
        patterns = {
            r'\bauth(?:entication)?\b': 'auth',
            r'\btest\b': 'test',
            r'\bconfig\b': 'config',
            r'\butil(?:ity|s)?\b': 'util',
            r'\bhelper\b': 'helper',
            r'\bmain\b': 'main',
            r'\bapp(?:lication)?\b': 'app',
            r'\bserver\b': 'server',
            r'\bclient\b': 'client',
            r'\bmodel\b': 'model',
            r'\bview\b': 'view',
            r'\bcontroller\b': 'controller',
        }
        
        for pattern, name in patterns.items():
            if re.search(pattern, context):
                ext = self.lang_extensions.get(lang, lang)
                return f'{name}.{ext}'
        
        # Fallback: timestamped filename
        timestamp = datetime.now().strftime('%H%M%S')
        ext = self.lang_extensions.get(lang, 'txt')
        return f'generated_{timestamp}.{ext}'
    
    def _add_vitals(self, text: str) -> str:
        """Add estimated vitals if missing"""
        if not re.search(r'::c[\d.]', text):
            # Find first >> and insert vitals after
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith('>>'):
                    # Insert vitals after first thought
                    lines.insert(i + 1, '')
                    lines.insert(i + 2, '::c0.70 ::m0.75 ::f0.80 ::s0.75')
                    break
            text = '\n'.join(lines)
        return text
    
    def _wrap_in_response(self, text: str) -> str:
        """Wrap plain text in response action"""
        return (
            '>> Providing response\n\n'
            '::c0.60 ::m0.70 ::f0.75 ::s0.70\n\n'
            '::response\n'
            '<<<\n'
            f'{text}\n'
            '>>>'
        )
