#!/usr/bin/env python3
"""
Demo script for LLM-based MCP Compliance Checker

This script demonstrates the LLM compliance checking approach without requiring API calls.
It shows how the system would work and what kind of results to expect.
"""

import json
from pathlib import Path

def demo_rule_analysis():
    """Demonstrate rule analysis without API calls"""
    
    print("LLM-based MCP Compliance Checker Demo")
    print("="*50)
    
    # Load sample data
    try:
        with open("mcp_llm_cleaned_rules.json", 'r', encoding='utf-8') as f:
            rules = json.load(f)
        print(f"✓ Loaded {len(rules)} MCP rules")
    except FileNotFoundError:
        print("❌ Rules file not found. Please run from the correct directory.")
        return
    
    try:
        with open("out/defs_python.jsonl", 'r', encoding='utf-8') as f:
            defs_data = [json.loads(line) for line in f if line.strip()]
        print(f"✓ Loaded {len(defs_data)} files with definitions")
    except FileNotFoundError:
        print("❌ Definitions file not found. Please generate IR data first.")
        return
    
    try:
        with open("out/calls_python.jsonl", 'r', encoding='utf-8') as f:
            calls_data = [json.loads(line) for line in f if line.strip()]
        print(f"✓ Loaded {len(calls_data)} files with calls")
    except FileNotFoundError:
        print("❌ Calls file not found. Please generate IR data first.")
        return
    
    # Analyze rule types
    rule_types = {}
    for rule in rules:
        rule_type = rule['rule_type']
        if rule_type not in rule_types:
            rule_types[rule_type] = 0
        rule_types[rule_type] += 1
    
    print(f"\nRule Type Distribution:")
    for rule_type, count in sorted(rule_types.items()):
        print(f"  {rule_type}: {count} rules")
    
    # Show sample rules
    print(f"\nSample Rules:")
    for i, rule in enumerate(rules[:5]):
        print(f"  {i+1}. Rule {rule['rule_id']} ({rule['rule_type']}): {rule['cleaned_text'][:80]}...")
    
    # Analyze code patterns
    print(f"\nCode Analysis:")
    
    # Count function definitions
    total_defs = sum(len(item.get('definitions', [])) for item in defs_data)
    print(f"  Total function definitions: {total_defs}")
    
    # Count function calls
    total_calls = sum(len(item.get('calls', [])) for item in calls_data)
    print(f"  Total function calls: {total_calls}")
    
    # Analyze function types
    def_types = {}
    for item in defs_data:
        for defn in item.get('definitions', []):
            kind = defn.get('kind', 'unknown')
            def_types[kind] = def_types.get(kind, 0) + 1
    
    print(f"  Function definition types:")
    for kind, count in sorted(def_types.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {kind}: {count}")
    
    # Analyze call types
    call_types = {}
    for item in calls_data:
        for call in item.get('calls', []):
            kind = call.get('kind', 'unknown')
            call_types[kind] = call_types.get(kind, 0) + 1
    
    print(f"  Function call types:")
    for kind, count in sorted(call_types.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    {kind}: {count}")
    
    # Show sample context that would be sent to LLM
    print(f"\nSample Context for LLM (first 2 files):")
    print("-" * 40)
    
    for i, item in enumerate(defs_data[:2]):
        file_path = item.get('file', 'unknown')
        definitions = item.get('definitions', [])
        print(f"\nFile: {file_path}")
        for defn in definitions[:3]:
            print(f"  - {defn.get('kind', 'unknown')}: {defn.get('name', 'unknown')} {defn.get('params', '')}")
    
    for i, item in enumerate(calls_data[:2]):
        file_path = item.get('file', 'unknown')
        calls = item.get('calls', [])
        print(f"\nFile: {file_path}")
        for call in calls[:3]:
            print(f"  - {call.get('kind', 'unknown')}: {call.get('name', 'unknown')} (receiver: {call.get('recv', 'none')})")
    
    # Demonstrate expected LLM prompt
    print(f"\nSample LLM Prompt:")
    print("-" * 40)
    
    sample_rule = rules[0]
    prompt = f"""
You are an expert in analyzing code compliance against MCP (Model Context Protocol) specifications.

TASK: Analyze whether the provided code implementation follows the given MCP rule.

RULE TO CHECK:
Rule ID: {sample_rule['rule_id']}
Rule Type: {sample_rule['rule_type']}
Rule Text: {sample_rule['cleaned_text']}
Function: {sample_rule.get('func', 'N/A')}
Condition: {sample_rule.get('condition', 'N/A')}
Category: {sample_rule.get('category', 'N/A')}

CODE CONTEXT:
[Code context would be inserted here - showing function definitions and calls]

INSTRUCTIONS:
1. Carefully analyze the code context against the rule
2. Look for evidence of compliance or violation
3. Consider the rule type (MUST, SHOULD, SHOULD_NOT, etc.)
4. Provide specific evidence from the code
5. Rate your confidence in the assessment

RESPONSE FORMAT (JSON):
{{
    "compliance_status": "COMPLIANT|VIOLATION|UNCLEAR|NOT_APPLICABLE",
    "evidence": ["specific evidence 1", "specific evidence 2"],
    "confidence": 0.85,
    "explanation": "Detailed explanation of your assessment"
}}
"""
    print(prompt)
    
    # Show expected output format
    print(f"\nExpected Output Format:")
    print("-" * 40)
    
    sample_output = {
        "summary": {
            "total_rules": 275,
            "compliant": 150,
            "violations": 25,
            "unclear": 80,
            "not_applicable": 20
        },
        "results": [
            {
                "rule_id": 1,
                "rule_type": "OPTIONAL",
                "rule_text": "Authorization is OPTIONAL for MCP implementations.",
                "compliance_status": "COMPLIANT",
                "evidence": ["Found optional authorization functions in code"],
                "confidence": 0.85,
                "explanation": "The code implements optional authorization as required by the rule..."
            },
            {
                "rule_id": 2,
                "rule_type": "SHOULD",
                "rule_text": "Implementations using an HTTP-based transport SHOULD conform to this specification.",
                "compliance_status": "VIOLATION",
                "evidence": ["Missing HTTP transport implementation", "No protocol version handling"],
                "confidence": 0.90,
                "explanation": "The code does not implement HTTP-based transport as required..."
            }
        ]
    }
    
    print(json.dumps(sample_output, indent=2))
    
    print(f"\n" + "="*50)
    print("DEMO COMPLETED")
    print("="*50)
    print("This demonstrates how the LLM compliance checker would work.")
    print("To run the actual checker, you need:")
    print("1. Set OPENAI_API_KEY environment variable")
    print("2. Run: python llm_compliance_checker.py")
    print("3. Or run: python test_llm_compliance.py for testing")

def main():
    demo_rule_analysis()

if __name__ == "__main__":
    main()



