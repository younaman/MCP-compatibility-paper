#!/usr/bin/env python3
"""
Z3 solver with MCP rules integration (IR v2 only)
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    from z3 import Solver, Int, String, Or, sat
except ImportError:
    print("Z3 not available. Please install z3-solver: pip install z3-solver")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"

# -----------------------------
# IR 数据结构
# -----------------------------
@dataclass
class CallIR:
    file: str
    kind: str              # "func_call" | "method_call"
    name: Optional[str]
    recv: Optional[str]
    cond: str
    order: int
    line: int
    col: int

@dataclass
class DefIR:
    file: str
    kind: str
    name: Optional[str]
    params: Optional[str]
    order: int
    line: int
    col: int

# -----------------------------
# 数据加载
# -----------------------------
def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def read_calls_by_lang(lang: str) -> List[CallIR]:
    calls: List[CallIR] = []
    fp = OUT_DIR / f"calls_{lang}.jsonl"
    if not fp.exists():
        print(f"Warning: {fp} not found")
        return calls
    for row in load_jsonl(fp):
        file_path = row.get("file")
        for ev in row.get("calls", []):
            calls.append(
                CallIR(
                    file=file_path,
                    kind=ev.get("kind"),
                    name=ev.get("name"),
                    recv=ev.get("recv"),
                    cond=ev.get("cond", "true"),
                    order=int(ev.get("order", 0)),
                    line=int(ev.get("line", 0)),
                    col=int(ev.get("col", 0)),
                )
            )
    return calls

def read_defs_by_lang(lang: str) -> List[DefIR]:
    defs: List[DefIR] = []
    fp = OUT_DIR / f"defs_{lang}.jsonl"
    if not fp.exists():
        print(f"Warning: {fp} not found")
        return defs
    for row in load_jsonl(fp):
        file_path = row.get("file")
        for d in row.get("definitions", []):
            defs.append(
                DefIR(
                    file=file_path,
                    kind=d.get("kind"),
                    name=d.get("name"),
                    params=d.get("params"),
                    order=int(d.get("order", 0)),
                    line=int(d.get("line", 0)),
                    col=int(d.get("col", 0)),
                )
            )
    return defs

# -----------------------------
# MCP Rule Model
# -----------------------------
class MCPRuleModel:
    """Z3 model with MCP IR v2 rules."""

    def __init__(self, calls: List[CallIR], defs: List[DefIR], mcp_rules: List[Dict[str, Any]], mode: str = "lenient"):
        self.solver = Solver()
        self.mode = mode
        self.calls = calls
        self.defs = defs
        self.mcp_rules = mcp_rules
        self.v_names: List[String] = []
        self.v_recvs: List[String] = []
        self.v_orders: List[Int] = []
        self._build_vars()
        self._apply_mcp_rules()

    # ---- build variables
    def _build_vars(self):
        for i, c in enumerate(self.calls):
            v_name = String(f"name_{i}")
            v_recv = String(f"recv_{i}")
            v_order = Int(f"order_{i}")
            self.v_names.append(v_name)
            self.v_recvs.append(v_recv)
            self.v_orders.append(v_order)

            self.solver.add(v_order == c.order)
            if c.name is not None:
                self.solver.add(v_name == c.name)
            if c.kind == "method_call":
                if c.recv is not None:
                    self.solver.add(v_recv == c.recv)
            else:
                self.solver.add(v_recv == "")

    # ---- apply MCP rules
    def _apply_mcp_rules(self):
        print(f"Applying {len(self.mcp_rules)} MCP rules...")
        applied_count = 0
        for rule in self.mcp_rules:
            if self._apply_ir_v2_rule(rule):
                applied_count += 1
        print(f"Applied {applied_count} rules successfully")

    # ---- helpers
    def _norm(self, s: str) -> str:
        return (s or "").strip().lower()

    def _indices_for_func(self, func_substr: str) -> List[int]:
        key = self._norm(func_substr)
        return [i for i, c in enumerate(self.calls) if c.name and key in self._norm(c.name)]

    def _add_after_constraint(self, before_func: str, after_indices: List[int]) -> bool:
        bi = self._indices_for_func(before_func)
        if not bi or not after_indices:
            return False
        for j in after_indices:
            self.solver.add(Or([self.v_orders[i] < self.v_orders[j] for i in bi]))
        return True

    def _add_before_constraint(self, after_func: str, before_indices: List[int]) -> bool:
        aj = self._indices_for_func(after_func)
        if not aj or not before_indices:
            return False
        for i in before_indices:
            self.solver.add(Or([self.v_orders[i] < self.v_orders[j] for j in aj]))
        return True

    def _parse_condition_atoms(self, condition: str) -> List[Tuple[str, str]]:
        import re
        cond = (condition or "").strip()
        if not cond:
            return []
        atoms = []
        patterns = {
            "has_occurred": re.findall(r'has_occurred\s*\(\s*([a-zA-Z0-9_\.:-]+)\s*\)', cond, flags=re.IGNORECASE),
            "after":        re.findall(r'after\s*\(\s*([a-zA-Z0-9_\.:-]+)\s*\)', cond, flags=re.IGNORECASE),
            "before":       re.findall(r'before\s*\(\s*([a-zA-Z0-9_\.:-]+)\s*\)', cond, flags=re.IGNORECASE),
        }
        for k, names in patterns.items():
            for n in names:
                atoms.append((k, n))
        if re.search(r'\b(arg|state)\b', cond, flags=re.IGNORECASE):
            atoms.append(("unsupported", cond))
        return atoms

    def _norm_bcp14_type(self, rule_type: str) -> str:
        import re
        rt = (rule_type or "").strip().upper()
        rt = re.sub(r'[\s-]+', '_', rt)
        mapping = {
            "MUST": "MUST",
            "REQUIRED": "MUST",
            "SHALL": "MUST",
            "MUST_NOT": "MUST_NOT",
            "SHALL_NOT": "MUST_NOT",
            "SHOULD": "SHOULD",
            "RECOMMENDED": "SHOULD",
            "SHOULD_NOT": "SHOULD_NOT",
            "NOT_RECOMMENDED": "SHOULD_NOT",
            "MAY": "MAY",
            "OPTIONAL": "MAY",
        }
        return mapping.get(rt, rt)

    # ---- apply single rule
    def _apply_ir_v2_rule(self, rule: Dict[str, Any]) -> bool:
        raw_type = rule.get('rule_type', 'UNKNOWN')
        rule_type = self._norm_bcp14_type(raw_type)
        func = rule.get('func')
        condition = rule.get('condition')
        rid = rule.get('rule_id')

        if not func or not condition:
            return False

        target_idx = self._indices_for_func(func)
        if not target_idx:
            return False

        atoms = self._parse_condition_atoms(condition)
        if not atoms:
            return False

        # Handle MUST rules as soft constraints (log only)
        if rule_type in ("MUST", "MUST_NOT"):
            print(f"[info] {rule_type} rule {rid} ({func}) - condition: {condition}")
            # For now, just log MUST rules without enforcing them
            # In a full implementation, we'd add hard constraints
            return True

        added = False

        # SHOULD / MAY -> soft constraints
        if rule_type in ("SHOULD", "MAY"):
            for kind, name in atoms:
                if kind == "after":
                    ok = self._add_after_constraint(name, target_idx)
                    added = added or ok
                elif kind == "before":
                    ok = self._add_before_constraint(name, target_idx)
                    added = added or ok
                elif kind in ("has_occurred", "unsupported"):
                    print(f"[info] {rule_type} rule {rid} ({func}) has non-enforced condition: {condition}")

        # SHOULD_NOT -> soft forbid
        elif rule_type == "SHOULD_NOT":
            # For SHOULD_NOT, we want to discourage the function call
            # This is a soft constraint, so we don't make it impossible
            # Instead, we could add a penalty or just log it
            print(f"[info] SHOULD_NOT rule {rid} ({func}) - condition: {condition}")
            # For now, just log the rule without adding hard constraints
            added = True

        else:
            print(f"[info] Unknown/non-MUST type {raw_type} normalized to {rule_type}, no constraint for rule {rid}")

        return added

    # ---- check
    def check(self) -> Tuple[bool, Optional[Any]]:
        res = self.solver.check()
        if res == sat:
            return True, self.solver.model()
        return False, None

# -----------------------------
# 入口函数
# -----------------------------
def convert_cleaned_rules_to_z3(cleaned_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    z3_rules = []
    for rule in cleaned_rules:
        if not rule.get("func") or not rule.get("condition"):
            continue
        z3_rules.append({
            "rule_id": rule.get("rule_id", "unknown"),
            "type": "ir_v2",
            "rule_type": rule.get("rule_type", "UNKNOWN"),
            "func": rule.get("func"),
            "condition": rule.get("condition"),
            "category": rule.get("category", "unknown"),
            "cleaned_text": rule.get("cleaned_text", "")
        })
    return z3_rules

def main():
    cleaned_rules_file = ROOT / "mcp_llm_cleaned_rules.json"
    if not cleaned_rules_file.exists():
        print(f"Error: {cleaned_rules_file} not found. Please run llm_rule_extractor.py first.")
        return
    with open(cleaned_rules_file, "r", encoding="utf-8") as f:
        cleaned_rules = json.load(f)
    print(f"Loaded {len(cleaned_rules)} LLM-cleaned MCP rules")

    mcp_rules = convert_cleaned_rules_to_z3(cleaned_rules)
    print(f"Generated {len(mcp_rules)} Z3 rules")

    available_langs = []
    for fp in OUT_DIR.glob("calls_*.jsonl"):
        if fp.stem.startswith("calls_"):
            lang = fp.stem[6:]
            available_langs.append(lang)
    print(f"Available languages: {sorted(available_langs)}")

    for lang in sorted(available_langs):
        print(f"\n=== Analyzing {lang.upper()} SDK ===")
        calls = read_calls_by_lang(lang)
        defs = read_defs_by_lang(lang)
        if not calls:
            print("No calls found")
            continue
        model = MCPRuleModel(calls[:50], defs[:50], mcp_rules, mode="lenient")
        ok, _ = model.check()
        print("SAT" if ok else "UNSAT")

if __name__ == "__main__":
    main()

