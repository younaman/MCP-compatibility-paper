#!/usr/bin/env python3
"""
演示IR数据如何传递给LLM
"""

from auto_llm_compliance_checker import AutoLLMComplianceChecker

def demo_ir_data_passing():
    """演示IR数据传递的具体实现"""
    
    print("IR数据传递演示")
    print("="*60)
    
    # 初始化检查器
    checker = AutoLLMComplianceChecker(
        rules_file="mcp_llm_cleaned_rules.json",
        defs_file="out/defs_python.jsonl",
        calls_file="out/calls_python.jsonl",
        source_root="."
    )
    
    # 选择一个测试规则
    test_rule = checker.rules[0]  # 第一个规则
    
    print(f"测试规则: {test_rule['rule_id']} - {test_rule['rule_type']}")
    print(f"规则内容: {test_rule['cleaned_text']}")
    print()
    
    # 1. 展示原始IR数据
    print("1. 原始IR数据结构:")
    print("-" * 40)
    print(f"defs_data 包含 {len(checker.defs_data)} 个文件")
    print(f"calls_data 包含 {len(checker.calls_data)} 个文件")
    
    # 展示一个具体的defs条目
    if checker.defs_data:
        sample_defs = checker.defs_data[0]
        print(f"\n示例defs条目:")
        print(f"  文件: {sample_defs.get('file')}")
        print(f"  定义数量: {len(sample_defs.get('definitions', []))}")
        for i, def_item in enumerate(sample_defs.get('definitions', [])[:3]):
            print(f"    {i+1}. {def_item.get('name')} (行 {def_item.get('line')})")
    
    # 展示一个具体的calls条目
    if checker.calls_data:
        sample_calls = checker.calls_data[0]
        print(f"\n示例calls条目:")
        print(f"  文件: {sample_calls.get('file')}")
        print(f"  调用数量: {len(sample_calls.get('calls', []))}")
        for i, call_item in enumerate(sample_calls.get('calls', [])[:3]):
            print(f"    {i+1}. {call_item.get('name')} (行 {call_item.get('line')})")
    
    print("\n" + "="*60)
    
    # 2. 展示构建的摘要
    print("2. 构建的IR数据摘要:")
    print("-" * 40)
    
    defs_summary = checker._build_defs_summary()
    print("函数定义摘要:")
    print(defs_summary[:500] + "..." if len(defs_summary) > 500 else defs_summary)
    
    print("\n函数调用摘要:")
    calls_summary = checker._build_calls_summary()
    print(calls_summary[:500] + "..." if len(calls_summary) > 500 else calls_summary)
    
    print("\n" + "="*60)
    
    # 3. 展示完整的prompt
    print("3. 发送给LLM的完整prompt:")
    print("-" * 40)
    
    full_prompt = checker._create_initial_prompt(test_rule)
    print(f"Prompt总长度: {len(full_prompt)} 字符")
    print("\n完整prompt内容:")
    print(full_prompt)
    
    print("\n" + "="*60)
    print("关键改进点:")
    print("1. 不再只是告诉LLM '有270个文件的数据'")
    print("2. 而是真正传递具体的函数名、行号、文件路径")
    print("3. LLM能够基于真实的函数定义和调用进行分析")
    print("4. 可以智能地请求相关的源文件进行深入分析")

if __name__ == "__main__":
    demo_ir_data_passing()



