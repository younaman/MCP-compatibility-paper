#!/usr/bin/env python3
import json, re, math
from pathlib import Path
from typing import List, Dict, Any, Tuple

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
RULES_FILE = ROOT / "mcp_llm_cleaned_rules.json"
OUTPUT_FILE = ROOT / "func_aliases.json"

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def tokenize(name: str) -> List[str]:
    if not name:
        return []
    s = name.strip()
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)   # camel -> words
    s = s.replace(".", " ").replace("/", " ").replace("-", " ").replace("_", " ")
    toks = [t.lower() for t in s.split() if t]
    return toks

def jaccard(a: List[str], b: List[str]) -> float:
    A, B = set(a), set(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

def lev(a: str, b: str) -> int:
    # Levenshtein distance (simple)
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    dp = list(range(len(b)+1))
    for i, ca in enumerate(a, 1):
        prev, dp[0] = dp[0], i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            dp[j], prev = min(dp[j]+1, dp[j-1]+1, prev+cost), dp[j]
    return dp[-1]

def score(rule_func: str, cand_name: str) -> float:
    """综合评分：子串/前缀/词交集/编辑距离"""
    rf, cn = rule_func.lower(), cand_name.lower()
    toks_rf, toks_cn = tokenize(rule_func), tokenize(cand_name)

    s = 0.0
    if rf in cn: s += 2.0
    if cn.startswith(rf) or rf.startswith(cn): s += 1.0
    s += 3.0 * jaccard(toks_rf, toks_cn)

    # 编辑距离的惩罚（越小越好）
    L = max(len(rf), 1)
    s += 1.5 * (1.0 - min(lev(rf, cn), L) / L)

    # 常见动词同义（可自行扩充）
    syn = {
        "initialize": {"init", "initialize", "setup"},
        "send_notification": {"send", "notify", "emit"},
        "log": {"log", "debug", "info", "warn", "error"},
        "parse": {"parse", "decode", "read"},
        "encode": {"encode", "serialize", "write"},
        "verify": {"verify", "check", "validate"},
        "serve": {"serve", "start", "listen"},
        "set": {"set", "put", "assign"},
        "redirect": {"redirect", "forward"},
        "include": {"include", "attach", "add"},
    }
    for k, vs in syn.items():
        if k in rf:
            if any(v in toks_cn for v in vs): s += 0.5

    return s

def main():
    if not RULES_FILE.exists():
        print(f"Missing {RULES_FILE}, run llm_rule_extractor first.")
        return

    # 1) 收集规则里的 func（只要 IR v2 有 func/condition 的）
    rules = json.load(open(RULES_FILE, "r", encoding="utf-8"))
    rule_funcs = sorted({r["func"] for r in rules if r.get("func") and r.get("condition")})

    # 2) 汇总所有语言 defs
    cand_funcs: List[str] = []
    for fp in OUT_DIR.glob("defs_*.jsonl"):
        for row in load_jsonl(fp):
            for d in row.get("definitions", []):
                name = d.get("name")
                if name:
                    cand_funcs.append(name)
    cand_funcs = sorted(set(cand_funcs))

    print(f"Collected {len(rule_funcs)} rule funcs; {len(cand_funcs)} candidate defs.")

    # 3) 为每个规则 func 打分取 Top-K
    aliases: Dict[str, List[str]] = {}
    TOPK = 8
    MIN_SCORE = 1.5  # 阈值可调：越高越严格

    for rf in rule_funcs:
        scored: List[Tuple[float, str]] = []
        for cn in cand_funcs:
            s = score(rf, cn)
            if s >= MIN_SCORE:
                scored.append((s, cn))
        scored.sort(reverse=True)
        aliases[rf] = [name for _, name in scored[:TOPK]]

    # 4) 输出别名表
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)
    print(f"Saved aliases to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()


