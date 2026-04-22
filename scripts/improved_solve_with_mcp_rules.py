#!/usr/bin/env python3
"""
改进的MCP规则求解器 - 基于实际函数调用序列
带 witness 约束和条件 token 过滤
"""

import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from z3 import *

# 添加scripts目录到路径
sys.path.append(str(Path(__file__).parent))

# 固定路径
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"

@dataclass
class CallIR:
    name: str
    kind: str
    recv: str
    cond: str
    order: int
    line: int
    col: int
    file: str = ""

def load_function_aliases():
    with open(ROOT / "func_aliases.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_calls_by_lang(lang: str) -> List[CallIR]:
    calls_file = OUT_DIR / f"calls_{lang}.jsonl"
    if not calls_file.exists():
        return []

    calls = []
    with open(calls_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                if "calls" in data:
                    for call_data in data["calls"]:
                        file_path = call_data.get("file", "")
                        calls.append(CallIR(
                            name=call_data.get("name", ""),
                            kind=call_data.get("kind", ""),
                            recv=call_data.get("recv", ""),
                            cond=call_data.get("cond", ""),
                            order=call_data.get("order", 0),
                            line=call_data.get("line", 0),
                            col=call_data.get("col", 0),
                            file=file_path
                        ))
    return calls

def load_llm_rules():
    with open(ROOT / "mcp_llm_cleaned_rules.json", "r", encoding="utf-8") as f:
        return json.load(f)

def extract_tokens(cond: str) -> List[str]:
    """从规则条件里抽事件 token"""
    cond = cond.lower()
    tokens = re.findall(r'(?:has_occurred|before|after)\s*\(\s*([a-z0-9_:-]+)\s*\)', cond)
    tokens += re.findall(r'(?:state|event)\s*==\s*([a-z0-9_:-]+)', cond)
    return sorted(set(tokens))

class ImprovedMCPRuleModel:
    def __init__(self, calls: List[CallIR], function_aliases: Dict[str, List]):
        self.calls = calls
        self.function_aliases = function_aliases
        self.solver = Solver()
        self.v_orders = [Int(f"order_{i}") for i in range(len(calls))]

        for i in range(len(calls)):
            self.solver.add(self.v_orders[i] == calls[i].order)

    def _map_function_name(self, func_name: str, lang: str) -> List[str]:
        # 精确匹配
        direct_matches = [call.name for call in self.calls if func_name.lower() in call.name.lower()]
        if direct_matches:
            return direct_matches
        if func_name in self.function_aliases:
            aliases = self.function_aliases[func_name]
            matches = []
            for alias in aliases:
                matches.extend([call.name for call in self.calls if alias.lower() in call.name.lower()])
            if matches:
                return matches
        return []

    def _find_function_calls(self, func_name: str, cond_tokens: List[str]) -> List[int]:
        indices = []
        for i, call in enumerate(self.calls):
            # 排除测试目录
            if "test" in call.file.lower() or "spec" in call.file.lower():
                continue
            if func_name.lower() not in call.name.lower():
                continue
            # cond token 检查
            if cond_tokens:
                cond_str = call.cond.lower() if call.cond else ""
                if cond_str == "true":  # true 当未知，不算匹配
                    continue
                if not any(tok in cond_str for tok in cond_tokens):
                    continue
            indices.append(i)
        return indices

    def apply_rule(self, rule: Dict[str, Any], lang: str) -> bool:
        func = rule.get('func')
        condition = rule.get('condition')
        rid = rule.get('rule_id')

        if not func or not condition:
            return False

        cond_tokens = extract_tokens(condition)
        mapped_funcs = self._map_function_name(func, lang)
        if not mapped_funcs:
            print(f"[skip] 规则 {rid}: 未找到函数 {func} 的映射")
            return False

        target_indices = []
        for mapped_func in mapped_funcs:
            target_indices.extend(self._find_function_calls(mapped_func, cond_tokens))

        # witness 存在性约束
        w = Int(f"witness_{rid}_{lang}")
        if target_indices:
            self.solver.add(Or([w == i for i in target_indices]))
            print(f"✅ 规则 {rid}: {func} -> {mapped_funcs}, 候选 {len(target_indices)}")
        else:
            # 无候选，直接 UNSAT
            self.solver.add(False)
            print(f"❌ 规则 {rid}: {func} 无候选调用 (lang={lang})")
            return False

        return True

    def check(self) -> Tuple[bool, Optional[Any]]:
        res = self.solver.check()
        if res == sat:
            return True, self.solver.model()
        return False, None

def analyze_lang_with_improved_rules(lang: str):
    print(f"\n=== 分析 {lang.upper()} 语言 ===")
    calls = load_calls_by_lang(lang)
    function_aliases = load_function_aliases()
    rules = load_llm_rules()

    print(f"加载了 {len(calls)} 个函数调用")
    print(f"加载了 {len(rules)} 个规则")

    if not calls:
        print("没有函数调用数据")
        return

    model = ImprovedMCPRuleModel(calls, function_aliases)
    applied_rules = 0
    for rule in rules:
        if model.apply_rule(rule, lang):
            applied_rules += 1

    print(f"应用了 {applied_rules} 个规则")

    is_sat, _ = model.check()
    if is_sat:
        print(f"✅ {lang.upper()}: SAT (满足约束)")
    else:
        print(f"❌ {lang.upper()}: UNSAT (违反约束)")

def main():
    print("=== 改进的MCP规则求解器 ===")
    available_langs = [calls_file.stem.replace("calls_", "") for calls_file in OUT_DIR.glob("calls_*.jsonl")]
    print(f"发现 {len(available_langs)} 种语言: {available_langs}")

    for lang in available_langs:
        analyze_lang_with_improved_rules(lang)

if __name__ == "__main__":
    main()

