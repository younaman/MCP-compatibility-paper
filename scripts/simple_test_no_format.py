#!/usr/bin/env python3
"""
测试不使用response_format的API调用
"""

import json
import os
import openai
from auto_llm_compliance_checker import AutoLLMComplianceChecker

def test_no_format():
    """测试不使用response_format的API调用"""
    print("测试不使用response_format的API调用")
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
        
        # 构建简化的提示词
        simple_prompt = f"""
请分析以下MCP规则是否在Python SDK中实现：

规则: {rule_250['rule_text']}
上下文: {rule_250['context']}

请简单回答：已实现、未实现、或需要更多信息。
"""
        
        print(f"发送简化提示词...")
        client = openai.OpenAI(api_key=checker.api_key)
        
        response = client.chat.completions.create(
            model=checker.model,
            messages=[{"role": "user", "content": simple_prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        
        print(f"API调用成功!")
        print(f"响应: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_no_format()






















