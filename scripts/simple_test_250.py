#!/usr/bin/env python3
"""
简单测试第250条规则
"""

import json
import os
import openai
from auto_llm_compliance_checker import AutoLLMComplianceChecker

def simple_test_250():
    """简单测试第250条规则"""
    print("简单测试第250条规则")
    print("="*50)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("错误: 请设置 OPENAI_API_KEY 环境变量")
        return
    
    try:
        checker = AutoLLMComplianceChecker(
            rules_file="requirements_analysis.json",
            defs_file="out/defs_python.jsonl",
            calls_file="out/calls_python.jsonl",
            source_root=".",
            language="python"
        )
        
        # 获取第250条规则
        rule_250 = [r for r in checker.rules if r['rule_id'] == 250][0]
        
        print(f"规则250: {rule_250['rule_text']}")
        print(f"开始检查...")
        
        # 直接调用check_rule方法，但不保存进度
        result = checker.check_rule(rule_250)
        
        print(f"\n检查完成!")
        print(f"合规状态: {result.compliance_status}")
        print(f"置信度: {result.confidence}")
        print(f"证据: {result.evidence}")
        print(f"解释: {result.explanation}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_test_250()






















