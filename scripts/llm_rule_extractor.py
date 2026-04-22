#!/usr/bin/env python3
"""
LLM-based Rule Extractor for MCP requirements_analysis.json
- 输入: requirements_analysis.json (275条原始规则)
- 输出: mcp_llm_cleaned_rules.json (干净的Z3映射友好规则)
- 特点: 利用LLM清洗/标准化规则，转换成Z3能懂的约束
"""

import json
from pathlib import Path
from openai import OpenAI

# 配置
ROOT = Path(__file__).resolve().parent.parent
REQ_FILE = ROOT / "requirements_analysis.json"
OUTPUT_FILE = ROOT / "mcp_llm_cleaned_rules.json"

def clean_rule_with_llm(rule: dict) -> dict:
    """
    使用 LLM API 清洗单条规则，转换成Z3约束格式
    """
    text = rule.get("full_text") or rule.get("original_text", "")
    rid = rule.get("id", "unknown")

    prompt = f"""
You are an expert in Model Context Protocol (MCP) specifications.
Please analyze the following rule and convert it into structured JSON
for Z3 constraint encoding.

Guidelines:
- Always identify the main action as a function (e.g., log, store, send, encrypt, validate, notify), even if not explicitly called a function.
- Extract constraints as conditions using this DSL:
  * has_occurred(f) - function f has been called before
  * state == value - system state check
  * arg.field <op> value - parameter/field constraints
  * Combine with &&, ||, ! operators
- For MUST: func can only be executed if condition is true
- For MUST_NOT: func cannot be executed if condition is true

Rule text:
\"\"\"{text}\"\"\"

Original rule ID: {rid}

Return JSON fields:
- rule_id: {rid} (use the original rule id provided above)
- rule_type: MUST | MUST_NOT | SHOULD | SHOULD_NOT | OPTIONAL | MAY
- func: the main function/action of this rule (never null if there's any action)
- condition: permission/forbidden condition using DSL (has_occurred, state, arg.field)
- category: message_specific | architectural | unknown
- cleaned_text: cleaned version of the rule

Examples:
1. "Clients MUST call initialize before sendRequest"
{{
  "rule_id": 12,
  "rule_type": "MUST",
  "func": "sendRequest",
  "condition": "has_occurred(initialize)",
  "category": "message_specific",
  "cleaned_text": "Clients MUST call initialize before sendRequest"
}}

2. "Access tokens MUST NOT be logged"
{{
  "rule_id": 27,
  "rule_type": "MUST_NOT",
  "func": "log",
  "condition": "arg.token == access_token",
  "category": "architectural",
  "cleaned_text": "Access tokens MUST NOT be logged"
}}

3. "Servers MUST validate request format before processing"
{{
  "rule_id": 45,
  "rule_type": "MUST",
  "func": "process",
  "condition": "has_occurred(validate) && arg.format == valid",
  "category": "message_specific",
  "cleaned_text": "Servers MUST validate request format before processing"
}}

4. "Error responses MUST include error code"
{{
  "rule_id": 78,
  "rule_type": "MUST",
  "func": "send_error_response",
  "condition": "arg.error_code != null",
  "category": "message_specific",
  "cleaned_text": "Error responses MUST include error code"
}}

5. "When tools change, send notification"
{{
  "rule_id": 250,
  "rule_type": "SHOULD",
  "func": "send_notification",
  "condition": "state == tools_changed",
  "category": "message_specific",
  "cleaned_text": "When tools change, send notification"
}}

6. "Never call shutdown during active session"
{{
  "rule_id": 89,
  "rule_type": "MUST_NOT",
  "func": "shutdown",
  "condition": "state == active_session",
  "category": "architectural",
  "cleaned_text": "Never call shutdown during active session"
}}

IMPORTANT: Return ONLY valid JSON, no markdown formatting, code blocks, or explanations.
"""

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional spec-to-Z3 rule extractor with deep understanding of MCP protocols."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=800,
            timeout=30
        )

        result_text = resp.choices[0].message.content.strip()
        data = json.loads(result_text)
        return data
        
    except Exception as e:
        print(f"  [Error] Rule {rid} failed: {e}")
        return {
            "rule_id": rid,
            "rule_type": rule.get("type", "UNKNOWN"),
            "func": None,
            "condition": None,
            "category": "unknown",
            "cleaned_text": text,
            "original_text": text
        }

def main():
    print("=== MCP LLM Rule Extractor ===")

    # 加载原始规则
    if not REQ_FILE.exists():
        print(f"Error: {REQ_FILE} not found")
        return
    
    with open(REQ_FILE, "r", encoding="utf-8") as f:
        rules = json.load(f)
    
    print(f"Loaded {len(rules)} rules from {REQ_FILE}")

    # 清洗规则
    cleaned_rules = []
    total_rules = len(rules)
    
    print(f"📋 开始转换 {total_rules} 条规则为Z3约束格式")
    print("=" * 50)
    
    for i, rule in enumerate(rules, 1):
        rid = rule.get("id", f"idx-{i}")
        percentage = (i / total_rules) * 100
        
        print(f"🔄 [{i}/{total_rules}] ({percentage:.1f}%) 转换规则 {rid}...")
        
        try:
            cleaned = clean_rule_with_llm(rule)
            cleaned_rules.append(cleaned)
            
            # 显示转换结果
            func = cleaned.get("func", "无")
            condition = cleaned.get("condition", "无")
            rule_type = cleaned.get("rule_type", "UNKNOWN")
            
            print(f"   ✅ 完成 - 类型: {rule_type}, 函数: {func}, 条件: {condition}")
            
        except Exception as e:
            print(f"   ❌ 错误: {e}")
            cleaned_rules.append({
                "rule_id": rid,
                "rule_type": "ERROR",
                "func": None,
                "condition": None,
                "category": "error",
                "cleaned_text": f"Error: {e}",
                "original_text": rule.get("full_text", "")
            })

    # 保存结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned_rules, f, ensure_ascii=False, indent=2)
    print(f"✅ Z3约束规则已保存到 {OUTPUT_FILE}")

    # 生成统计
    stats = {
        "total": len(cleaned_rules),
        "by_type": {},
        "with_functions": 0,
        "with_conditions": 0
    }
    
    for r in cleaned_rules:
        rt = r.get("rule_type", "UNKNOWN")
        stats["by_type"][rt] = stats["by_type"].get(rt, 0) + 1
        
        if r.get("func"):
            stats["with_functions"] += 1
        if r.get("condition"):
            stats["with_conditions"] += 1

    print("\n" + "=" * 50)
    print("🎉 规则转换完成！")
    print("=" * 50)
    print(f"📊 转换统计:")
    print(f"   • 总规则数: {stats['total']}")
    print(f"   • 包含函数约束: {stats['with_functions']}")
    print(f"   • 包含条件约束: {stats['with_conditions']}")
    print(f"\n📋 按类型分布:")
    for rule_type, count in stats['by_type'].items():
        print(f"   • {rule_type}: {count}")
    print("=" * 50)

if __name__ == "__main__":
    main()

