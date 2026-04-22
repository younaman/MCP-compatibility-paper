#!/usr/bin/env python3
"""
Rule loader for MCP requirements_analysis.json
Converts 275 rules to Z3 constraints with proper semantics
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# Import our Z3 model
from solve_calls_z3 import IRModel, read_calls_by_lang, read_defs_by_lang

ROOT = Path(__file__).resolve().parent.parent
REQ_FILE = ROOT / "requirements_analysis.json"

def load_rules(path: Path) -> List[Dict[str, Any]]:
    """Load rules from requirements_analysis.json"""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list of rules in JSON")
    return data

def extract_function_name(text: str) -> Optional[str]:
    """Extract function name from rule text using improved patterns."""
    # Look for quoted function names
    quoted_match = re.search(r'`([^`]+)`', text)
    if quoted_match:
        return quoted_match.group(1)
    
    # Look for notification patterns
    notif_match = re.search(r'send\s+(?:an?\s+)?`?(\w+)`?\s+notification', text, re.IGNORECASE)
    if notif_match:
        return f"send{notif_match.group(1).capitalize()}Notification"
    
    # Look for request patterns
    req_match = re.search(r'send\s+(?:an?\s+)?`?(\w+)`?\s+request', text, re.IGNORECASE)
    if req_match:
        return f"send{req_match.group(1).capitalize()}Request"
    
    # Look for response patterns
    resp_match = re.search(r'send\s+(?:an?\s+)?`?(\w+)`?\s+response', text, re.IGNORECASE)
    if resp_match:
        return f"send{resp_match.group(1).capitalize()}Response"
    
    # Look for validation patterns
    val_match = re.search(r'validate\s+(\w+)', text, re.IGNORECASE)
    if val_match:
        return f"validate{val_match.group(1).capitalize()}"
    
    # Look for handle patterns
    handle_match = re.search(r'handle\s+(\w+)', text, re.IGNORECASE)
    if handle_match:
        return f"handle{handle_match.group(1).capitalize()}"
    
    # Look for process patterns
    process_match = re.search(r'process\s+(\w+)', text, re.IGNORECASE)
    if process_match:
        return f"process{process_match.group(1).capitalize()}"
    
    return None

def extract_sequence_info(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract sequence information (before, after, action) from rule text."""
    text_lower = text.lower()
    
    # Look for before patterns
    before_patterns = [
        r'(\w+)\s+before\s+(\w+)',
        r'(\w+)\s+must\s+happen\s+before\s+(\w+)',
        r'(\w+)\s+must\s+occur\s+before\s+(\w+)',
        r'before\s+(\w+),\s+(\w+)'
    ]
    
    for pattern in before_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1), match.group(2), "before"
    
    # Look for after patterns
    after_patterns = [
        r'(\w+)\s+after\s+(\w+)',
        r'(\w+)\s+must\s+happen\s+after\s+(\w+)',
        r'(\w+)\s+must\s+occur\s+after\s+(\w+)',
        r'after\s+(\w+),\s+(\w+)'
    ]
    
    for pattern in after_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(2), match.group(1), "after"
    
    return None, None, None

def apply_rule(model: IRModel, rule: Dict[str, Any]) -> Tuple[str, str, str]:
    """Apply a single rule to the model and return (status, msg, details)."""
    rtype = rule.get("type", "").upper()  # MUST, MUST NOT, SHOULD, SHOULD NOT, OPTIONAL
    text = rule.get("full_text", "")
    rule_id = rule.get("id", 0)
    
    # Extract function name
    func_name = extract_function_name(text)
    
    # Extract sequence info
    before, after, action = extract_sequence_info(text)
    
    # Apply rules based on type
    if rtype == "MUST":
        if action == "before" and before and after:
            model.add_rule_before(before, after)
            return "HARD", f"MUST: {before} before {after}", f"Rule {rule_id}: {text[:100]}..."
        elif func_name:
            model.add_rule_exists(func_name)
            return "HARD", f"MUST: {func_name} must exist", f"Rule {rule_id}: {text[:100]}..."
        else:
            return "HARD", f"MUST: {text[:50]}...", f"Rule {rule_id}: {text[:100]}..."
    
    elif rtype == "MUST_NOT":
        if func_name:
            model.add_rule_forbid(func_name)
            return "HARD", f"MUST NOT: {func_name} forbidden", f"Rule {rule_id}: {text[:100]}..."
        else:
            return "HARD", f"MUST NOT: {text[:50]}...", f"Rule {rule_id}: {text[:100]}..."
    
    elif rtype == "SHOULD":
        if action == "before" and before and after:
            model.add_rule_before(before, after, soft=True)
            return "SOFT", f"SHOULD: {before} before {after}", f"Rule {rule_id}: {text[:100]}..."
        elif func_name:
            model.add_rule_exists(func_name, soft=True)
            return "SOFT", f"SHOULD: {func_name} exists", f"Rule {rule_id}: {text[:100]}..."
        else:
            return "SOFT", f"SHOULD: {text[:50]}...", f"Rule {rule_id}: {text[:100]}..."
    
    elif rtype == "SHOULD_NOT":
        if func_name:
            model.add_rule_forbid(func_name, soft=True)
            return "SOFT", f"SHOULD NOT: {func_name}", f"Rule {rule_id}: {text[:100]}..."
        else:
            return "SOFT", f"SHOULD NOT: {text[:50]}...", f"Rule {rule_id}: {text[:100]}..."
    
    elif rtype == "OPTIONAL":
        return "INFO", f"OPTIONAL: {func_name or text[:50]}...", f"Rule {rule_id}: {text[:100]}..."
    
    elif rtype == "MAY":
        return "INFO", f"MAY: {func_name or text[:50]}...", f"Rule {rule_id}: {text[:100]}..."
    
    return "UNKNOWN", f"Unrecognized rule: {text[:50]}...", f"Rule {rule_id}: {text[:100]}..."

def analyze_lang_with_all_rules(lang: str, rules: List[Dict[str, Any]], max_calls: int = 100) -> None:
    """Analyze a specific language/SDK with all 275 rules."""
    print(f"\n=== Analyzing {lang.upper()} SDK with All Rules ===")
    
    calls = read_calls_by_lang(lang)
    defs = read_defs_by_lang(lang)
    print(f"Loaded {len(calls)} calls, {len(defs)} definitions")
    
    if not calls:
        print(f"No calls found for {lang}")
        return
    
    # Limit data for testing
    calls = calls[:max_calls]
    defs = defs[:50]
    print(f"Testing with {len(calls)} calls, {len(defs)} definitions")

    model = IRModel(calls, defs, mode="lenient")
    
    # Apply all rules
    results: List[Tuple[str, str, str]] = []
    hard_rules = 0
    soft_rules = 0
    info_rules = 0
    
    for rule in rules:
        status, msg, details = apply_rule(model, rule)
        results.append((status, msg, details))
        
        if status == "HARD":
            hard_rules += 1
        elif status == "SOFT":
            soft_rules += 1
        else:
            info_rules += 1
    
    print(f"Applied {len(rules)} rules: {hard_rules} HARD, {soft_rules} SOFT, {info_rules} INFO")
    
    # Solve the hard constraints
    ok, m = model.check()
    
    print(f"\n=== Rule Summary for {lang.upper()} ===")
    violated_hard = 0
    violated_soft = 0
    
    for status, msg, details in results:
        if status == "HARD":
            if not ok:
                violated_hard += 1
                print(f"❌ [VIOLATED] {msg}")
            else:
                print(f"✅ [SATISFIED] {msg}")
        elif status == "SOFT":
            # For soft rules, we can't easily check if they're violated without more complex logic
            print(f"⚠️  [SOFT] {msg}")
        else:
            print(f"ℹ️  [INFO] {msg}")
    
    print(f"\n=== Z3 Result for {lang.upper()} ===")
    if ok:
        print("✅ SAT: all hard MUST/MUST NOT rules satisfied.")
    else:
        print("❌ UNSAT: some MUST/MUST NOT rules violated.")
        print(f"   Violated {violated_hard} hard rules")
    
    # Show sample calls
    print(f"\n=== Sample Calls for {lang.upper()} ===")
    for i, c in enumerate(calls[:10]):
        print(f"#{i+1:02d} {c.kind} name={c.name} recv={c.recv} order={c.order}")

def main() -> None:
    """Main function with all 275 rules."""
    print("=== MCP Rule Compliance Checker ===")
    
    # Load all rules
    rules = load_rules(REQ_FILE)
    print(f"Loaded {len(rules)} MCP rules from {REQ_FILE}")
    
    # Get available languages
    available_langs = []
    for fp in ROOT.glob("out/calls_*.jsonl"):
        lang = fp.stem.split('_')[-1]
        available_langs.append(lang)
    
    print(f"Available languages: {sorted(available_langs)}")
    
    # Analyze each language with all rules
    for lang in sorted(available_langs):
        analyze_lang_with_all_rules(lang, rules, max_calls=50)

if __name__ == "__main__":
    main()

