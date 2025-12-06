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

class DuckflowParser:
    """Parser for Duckflow Markdown+KV format"""
    
    # Section patterns
    REASONING_PATTERN = re.compile(r'^\[REASONING\]')
    VITAL_PATTERN = re.compile(r'^\[([A-Z_]+)\]\s+(.+)')
    ACTION_PATTERN = re.compile(r'^\[ACTION_(\d+)_([a-zA-Z0-9_]+)\]\s*(.+)?')
    CONTENT_START_PATTERN = re.compile(r'^\[ACTION_(\d+)_CONTENT_START\]')
    CONTENT_END_PATTERN = re.compile(r'^\[ACTION_(\d+)_CONTENT_END\]')
    
    # Known vitals
    KNOWN_VITALS = {'CONFIDENCE', 'MOOD', 'FOCUS', 'STAMINA'}
    
    def parse(self, response: str) -> DuckflowResponse:
        """
        Parse a Duckflow response.
        
        Args:
            response: Raw response string
            
        Returns:
            DuckflowResponse object
        """
        result = DuckflowResponse(raw_text=response)
        
        lines = response.split('\n')
        current_section = None
        reasoning_buffer = []
        
        # Action tracking
        actions_dict: Dict[int, Dict[str, Any]] = {}
        current_action_idx = None
        current_param_name = None  # Track current param for multi-line values
        content_buffer = []
        in_content = False
        
        for line_num, line in enumerate(lines, 1):
            try:
                # Check for REASONING section
                if self.REASONING_PATTERN.match(line):
                    current_section = 'reasoning'
                    current_param_name = None
                    continue
                
                # Check for vitals
                vital_match = self.VITAL_PATTERN.match(line)
                if vital_match:
                    vital_name, vital_value = vital_match.groups()
                    vital_value = vital_value.strip()
                    if vital_name in self.KNOWN_VITALS:
                        try:
                            result.vitals[vital_name.lower()] = float(vital_value)
                        except ValueError:
                            result.parse_errors.append(
                                f"Line {line_num}: Invalid vital value: {vital_value}"
                            )
                    current_section = None
                    current_param_name = None
                    continue
                
                # Check for action content start
                content_start_match = self.CONTENT_START_PATTERN.match(line)
                if content_start_match:
                    action_idx = int(content_start_match.group(1))
                    current_action_idx = action_idx
                    in_content = True
                    content_buffer = []
                    current_section = None
                    current_param_name = None
                    continue
                
                # Check for action content end
                content_end_match = self.CONTENT_END_PATTERN.match(line)
                if content_end_match:
                    action_idx = int(content_end_match.group(1))
                    if action_idx in actions_dict:
                        actions_dict[action_idx]['content'] = '\n'.join(content_buffer)
                    in_content = False
                    content_buffer = []
                    current_action_idx = None
                    current_section = None
                    current_param_name = None
                    continue
                
                # If in content section, collect lines
                if in_content:
                    content_buffer.append(line)
                    continue
                
                # Check for action parameters
                action_match = self.ACTION_PATTERN.match(line)
                if action_match:
                    action_idx = int(action_match.group(1))
                    param_name = action_match.group(2)
                    param_value = action_match.group(3) or ''
                    
                    # Initialize action if needed
                    if action_idx not in actions_dict:
                        actions_dict[action_idx] = {'params': {}}
                    
                    # Store TYPE or params
                    if param_name == 'TYPE':
                        actions_dict[action_idx]['type'] = param_value.strip()
                        current_param_name = None # Type is usually single line
                    else:
                        # Start tracking this param
                        actions_dict[action_idx]['params'][param_name.lower()] = param_value.strip()
                        current_action_idx = action_idx
                        current_param_name = param_name.lower()
                    
                    current_section = None
                    continue
                
                # Collect reasoning text
                if current_section == 'reasoning':
                    reasoning_buffer.append(line)
                    continue

                # Collect multi-line param value
                if current_param_name and current_action_idx is not None:
                    # Append to existing value
                    current_val = actions_dict[current_action_idx]['params'][current_param_name]
                    if current_val:
                        actions_dict[current_action_idx]['params'][current_param_name] = current_val + "\n" + line
                    else:
                        actions_dict[current_action_idx]['params'][current_param_name] = line
                    
            except Exception as e:
                result.parse_errors.append(f"Line {line_num}: {str(e)}")
        
        # Finalize reasoning
        result.reasoning = '\n'.join(reasoning_buffer).strip()
        
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
        
        return result
