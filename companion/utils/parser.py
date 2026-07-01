import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class Action:
    """Represents a single action"""
    type: str
    params: Dict[str, str] = field(default_factory=dict)
    content: Optional[str] = None
    
@dataclass
class DuckflowResponse:
    """Parsed Duckflow response"""
    reasoning: str = ""
    vitals: Dict[str, float] = field(default_factory=dict)
    actions: List[Action] = field(default_factory=list)
    raw_text: str = ""
    parse_errors: List[str] = field(default_factory=list)
    is_batch: bool = False  # Sym-Ops v3.2: batch execution flag

class DuckflowParser:
    """Parser for Duckflow Markdown+KV format"""
    
    # Section patterns
    REASONING_PATTERN = re.compile(r'^>>\s*(.*)$')
    VITAL_PATTERN = re.compile(r'^::c([0-1]\.[0-9])\s+::s([0-1]\.[0-9])\s+::m([0-1]\.[0-9])\s+::f([0-1]\.[0-9])$')
    ACTION_PATTERN = re.compile(r'^::([a-zA-Z_]+)\s+@(.+)$')
    BATCH_START_PATTERN = re.compile(r'^::execute_batch$')
    BATCH_SEPARATOR = re.compile(r'^%%%(?:\s*|$)')
    CONTENT_START = re.compile(r'^<<<$')
    CONTENT_END = re.compile(r'^>>>$')
    
    # Known vitals
    KNOWN_VITALS = {'confidence', 'safety', 'memory', 'focus'}
    
    def parse(self, response: str) -> DuckflowResponse:
        """
        Parse a Duckflow response.
        
        Args:
            :: response @ : Raw response string
            
        Returns:
            DuckflowResponse object
        """
        result = DuckflowResponse(raw_text=response)
        
        lines = response.split('\n')
        reasoning_buffer = []
        
        # Action tracking
        actions_dict: Dict[int, Dict[str, Any]] = {}
        current_action_idx = 0
        in_content = False
        content_buffer = []
        current_action_data = None
        
        # Batch execution tracking
        is_batch = False
        batch_actions = []
        
        for line_num, line in enumerate(lines, 1):
            try:
                # Check for reasoning (Sym-Ops v3.2: >> format)
                if line.strip().startswith('>>'):
                    reasoning_match = self.REASONING_PATTERN.match(line.strip())
                    if reasoning_match:
                        reasoning_buffer.append(reasoning_match.group(1))
                    continue
                
                # Check for vitals (Sym-Ops v3.2: ::c0.9 ::s1.0 format)
                vital_match = self.VITAL_PATTERN.match(line.strip())
                if vital_match:
                    confidence, safety, memory, focus = vital_match.groups()
                    result.vitals = {
                        'confidence': float(confidence),
                        'safety': float(safety),
                        'memory': float(memory),
                        'focus': float(focus)
                    }
                    continue
                
                # Check for batch start
                if self.BATCH_START_PATTERN.match(line.strip()):
                    is_batch = True
                    continue
                
                # Check for batch separator
                if self.BATCH_SEPARATOR.match(line.strip()):
                    if current_action_data and 'type' in current_action_data:
                        actions_dict[current_action_idx] = current_action_data
                        current_action_idx += 1
                    current_action_data = None
                    continue
                
                # Check for content start
                if line.strip() == '<<<':
                    in_content = True
                    content_buffer = []
                    continue
                
                # Check for content end
                if line.rstrip() == '>>>':
                    if current_action_data:
                        content = '\n'.join(content_buffer)
                        # Extract YAML front matter if present
                        if content.startswith('---'):
                            parts = content.split('---', 2)
                            if len(parts) >= 3:
                                yaml_str = parts[1].strip()
                                for y_line in yaml_str.split('\n'):
                                    if ':' in y_line:
                                        k, v = y_line.split(':', 1)
                                        current_action_data['params'][k.strip()] = v.strip()
                                content = parts[2].strip()
                        current_action_data['content'] = content
                    in_content = False
                    continue
                
                # If in content section, collect lines
                if in_content:
                    content_buffer.append(line)
                    continue
                
                # Check for action (Sym-Ops v3.2: ::action_name @path params)
                action_match = self.ACTION_PATTERN.match(line.strip())
                if action_match:
                    action_name = action_match.group(1)
                    target_raw = action_match.group(2)
                    
                    # Split target into path and key=value params
                    # Path is everything before the first " key=" pattern
                    param_start = re.search(r'\s+(\w+)=', target_raw)
                    if param_start:
                        target = target_raw[:param_start.start()].strip()
                        params_str = target_raw[param_start.start():].strip()
                    else:
                        target = target_raw.strip()
                        params_str = ''
                    
                    # Parse params
                    params = {}
                    if params_str:
                        for param in params_str.split():
                            param = param.strip()
                            if '=' in param:
                                parts = param.split('=', 1)
                                if len(parts) == 2:
                                    params[parts[0]] = parts[1]
                    
                    current_action_data = {
                        'type': action_name,
                        'params': params,
                        'target': target
                    }
                    
                    # If not in batch mode, add immediately
                    if not is_batch:
                        actions_dict[current_action_idx] = current_action_data
                        current_action_idx += 1
                        current_action_data = None
                    
                    continue
                
                # Collect reasoning text
                if reasoning_buffer and not line.strip():
                    continue
                    
            except Exception as e:
                result.parse_errors.append(f"Line {line_num}: {str(e)}")
        
        # Finalize reasoning
        result.reasoning = ' '.join(reasoning_buffer).strip()
        
        # Finalize last action if in batch
        if current_action_data and 'type' in current_action_data:
            actions_dict[current_action_idx] = current_action_data
        
        # Convert actions_dict to Action objects
        for idx in sorted(actions_dict.keys()):
            action_data = actions_dict[idx]
            if 'type' not in action_data:
                result.parse_errors.append(f"Action {idx}: Missing TYPE")
                continue
            
            result.actions.append(Action(
                type=action_data['type'],
                params=action_data.get('params', {}),
                content=action_data.get('content')
            ))
        
        # Set batch flag if multiple actions or explicit batch
        result.is_batch = len(result.actions) > 1 or is_batch
        
        return result
