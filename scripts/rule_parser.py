#!/usr/bin/env python3
"""
Rule parser for MCP requirements_analysis.json
Maps MCP specification rules to Z3 constraints
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class MCPRule:
    id: int
    type: str  # MUST, SHOULD, SHOULD_NOT, MAY, OPTIONAL, MUST_NOT
    full_text: str
    context: str
    file_path: str
    line_number: int

class RuleParser:
    """Parse MCP requirements and map to Z3 constraints."""
    
    def __init__(self, requirements_file: str):
        self.requirements_file = Path(requirements_file)
        self.rules: List[MCPRule] = []
        self.load_rules()
    
    def load_rules(self):
        """Load rules from requirements_analysis.json"""
        with open(self.requirements_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            rule = MCPRule(
                id=item['id'],
                type=item['type'],
                full_text=item['full_text'],
                context=item['context'],
                file_path=item['file_path'],
                line_number=item['line_number']
            )
            self.rules.append(rule)
    
    def extract_function_calls(self, text: str) -> List[str]:
        """Extract function/method names from rule text."""
        # Look for patterns like "send_*", "receive_*", "validate_*", etc.
        patterns = [
            r'send_(\w+)',
            r'receive_(\w+)', 
            r'validate_(\w+)',
            r'process_(\w+)',
            r'handle_(\w+)',
            r'initialize_(\w+)',
            r'cleanup_(\w+)',
            r'notify_(\w+)',
            r'request_(\w+)',
            r'response_(\w+)',
            r'(\w+)_notification',
            r'(\w+)_request',
            r'(\w+)_response',
            r'(\w+)_message',
            r'(\w+)_token',
            r'(\w+)_metadata',
            # More general patterns
            r'(\w+)\s+notification',
            r'(\w+)\s+request',
            r'(\w+)\s+response',
            r'(\w+)\s+message',
            r'(\w+)\s+token',
            r'(\w+)\s+metadata',
            # Look for quoted function names
            r'"(\w+)"',
            r"'(\w+)'",
            # Look for backtick function names
            r'`(\w+)`',
            # Look for function calls with parentheses
            r'(\w+)\(',
            # Look for method calls with dots
            r'\.(\w+)\(',
            r'\.(\w+)\s',
        ]
        
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            functions.extend(matches)
        
        # Filter out common words that aren't function names
        common_words = {'the', 'and', 'or', 'for', 'with', 'from', 'to', 'in', 'on', 'at', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'must', 'may', 'can', 'this', 'that', 'these', 'those', 'a', 'an', 'of', 'as', 'if', 'when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom', 'whose'}
        
        filtered_functions = [f for f in functions if f.lower() not in common_words and len(f) > 2]
        
        return list(set(filtered_functions))  # Remove duplicates
    
    def extract_sequence_rules(self) -> List[Dict[str, Any]]:
        """Extract rules about call sequences/order."""
        sequence_rules = []
        
        for rule in self.rules:
            text = rule.full_text.lower()
            
            # Look for "before" patterns - more flexible
            if 'before' in text:
                # Extract what must happen before what
                patterns = [
                    r'(\w+)\s+must\s+happen\s+before\s+(\w+)',
                    r'(\w+)\s+must\s+occur\s+before\s+(\w+)',
                    r'(\w+)\s+must\s+be\s+before\s+(\w+)',
                    r'(\w+)\s+before\s+(\w+)',
                    r'before\s+(\w+),\s+(\w+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        sequence_rules.append({
                            'type': 'before',
                            'before': match.group(1),
                            'after': match.group(2),
                            'rule_type': rule.type,
                            'rule_id': rule.id,
                            'text': rule.full_text
                        })
                        break
            
            # Look for "after" patterns - more flexible
            if 'after' in text:
                patterns = [
                    r'(\w+)\s+must\s+happen\s+after\s+(\w+)',
                    r'(\w+)\s+must\s+occur\s+after\s+(\w+)',
                    r'(\w+)\s+must\s+be\s+after\s+(\w+)',
                    r'(\w+)\s+after\s+(\w+)',
                    r'after\s+(\w+),\s+(\w+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        sequence_rules.append({
                            'type': 'after',
                            'before': match.group(2),
                            'after': match.group(1),
                            'rule_type': rule.type,
                            'rule_id': rule.id,
                            'text': rule.full_text
                        })
                        break
        
        return sequence_rules
    
    def extract_mandatory_calls(self) -> List[Dict[str, Any]]:
        """Extract rules about mandatory function calls."""
        mandatory_calls = []
        
        for rule in self.rules:
            if rule.type in ['MUST', 'SHOULD']:
                functions = self.extract_function_calls(rule.full_text)
                if functions:
                    mandatory_calls.append({
                        'functions': functions,
                        'rule_type': rule.type,
                        'rule_id': rule.id,
                        'text': rule.full_text
                    })
        
        return mandatory_calls
    
    def extract_forbidden_calls(self) -> List[Dict[str, Any]]:
        """Extract rules about forbidden function calls."""
        forbidden_calls = []
        
        for rule in self.rules:
            if rule.type in ['MUST_NOT', 'SHOULD_NOT']:
                functions = self.extract_function_calls(rule.full_text)
                if functions:
                    forbidden_calls.append({
                        'functions': functions,
                        'rule_type': rule.type,
                        'rule_id': rule.id,
                        'text': rule.full_text
                    })
        
        return forbidden_calls
    
    def generate_z3_constraints(self) -> List[Dict[str, Any]]:
        """Generate Z3 constraint definitions from MCP rules."""
        constraints = []
        
        # Extract sequence rules
        sequence_rules = self.extract_sequence_rules()
        for rule in sequence_rules:
            constraints.append({
                'type': 'sequence',
                'subtype': rule['type'],
                'before': rule['before'],
                'after': rule['after'],
                'strength': rule['rule_type'],
                'rule_id': rule['rule_id'],
                'description': rule['text']
            })
        
        # Extract mandatory calls
        mandatory_calls = self.extract_mandatory_calls()
        for rule in mandatory_calls:
            for func in rule['functions']:
                constraints.append({
                    'type': 'mandatory',
                    'function': func,
                    'strength': rule['rule_type'],
                    'rule_id': rule['rule_id'],
                    'description': rule['text']
                })
        
        # Extract forbidden calls
        forbidden_calls = self.extract_forbidden_calls()
        for rule in forbidden_calls:
            for func in rule['functions']:
                constraints.append({
                    'type': 'forbidden',
                    'function': func,
                    'strength': rule['rule_type'],
                    'rule_id': rule['rule_id'],
                    'description': rule['text']
                })
        
        return constraints

def main():
    """Test the rule parser."""
    parser = RuleParser("<LOCAL_PATH>/Desktop/MCP/MCP历史版本/modelcontextprotocol-2025-06-18/modelcontextprotocol-2025-06-18/docs/specification/2025-06-18/requirements_analysis.json")
    
    print(f"Loaded {len(parser.rules)} MCP rules")
    
    # Generate constraints
    constraints = parser.generate_z3_constraints()
    print(f"\nGenerated {len(constraints)} Z3 constraints")
    
    # Show constraint types
    constraint_types = {}
    for c in constraints:
        constraint_types[c['type']] = constraint_types.get(c['type'], 0) + 1
    
    print("\nConstraint types:")
    for ctype, count in constraint_types.items():
        print(f"  {ctype}: {count}")
    
    # Show sample constraints
    print("\nSample constraints:")
    for i, constraint in enumerate(constraints[:10]):
        if constraint['type'] == 'sequence':
            print(f"{i+1}. {constraint['type']} - {constraint['before']} {constraint['subtype']} {constraint['after']} ({constraint['strength']})")
        else:
            print(f"{i+1}. {constraint['type']} - {constraint.get('function', 'N/A')} ({constraint['strength']})")
    
    # Show some detailed examples
    print("\nDetailed examples:")
    for i, constraint in enumerate(constraints[:5]):
        print(f"\n{i+1}. {constraint['type'].upper()} constraint:")
        print(f"   Description: {constraint['description'][:100]}...")
        if constraint['type'] == 'sequence':
            print(f"   Rule: {constraint['before']} {constraint['subtype']} {constraint['after']}")
        else:
            print(f"   Function: {constraint.get('function', 'N/A')}")
        print(f"   Strength: {constraint['strength']}")
        print(f"   Rule ID: {constraint['rule_id']}")

if __name__ == "__main__":
    main()

