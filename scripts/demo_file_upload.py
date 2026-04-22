#!/usr/bin/env python3
"""
演示OpenAI Files API上传功能
"""

import os
from auto_llm_compliance_checker import AutoLLMComplianceChecker

def demo_file_upload_approach():
    """演示文件上传方式vs传统方式"""
    print("OpenAI Files API 上传方式演示")
    print("="*60)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("错误: 请设置 OPENAI_API_KEY 环境变量")
        return
    
    # 初始化检查器
    print("1. 初始化检查器（自动上传文件）...")
    checker = AutoLLMComplianceChecker(
        rules_file="mcp_llm_cleaned_rules.json",
        defs_file="out/defs_python.jsonl",
        calls_file="out/calls_python.jsonl",
        source_root="."
    )
    
    print(f"\n2. 文件上传结果:")
    print(f"   defs_file_id: {checker.defs_file_id}")
    print(f"   calls_file_id: {checker.calls_file_id}")
    
    if checker.defs_file_id and checker.calls_file_id:
        print("   ✅ 使用OpenAI Files API方式")
        print("   - 文件已上传到OpenAI服务器")
        print("   - LLM可以直接检索文件内容")
        print("   - 无需在prompt中嵌入大量数据")
        print("   - 更高效，支持更大文件")
    else:
        print("   ⚠️ 回退到传统方式")
        print("   - 在prompt中嵌入数据摘要")
        print("   - 受token限制")
    
    # 测试规则检查
    print(f"\n3. 测试规则检查...")
    test_rule = checker.rules[0]
    print(f"   规则: {test_rule['rule_id']} - {test_rule['rule_type']}")
    print(f"   内容: {test_rule['cleaned_text']}")
    
    result = checker.check_rule(test_rule)
    
    print(f"\n4. 检查结果:")
    print(f"   合规状态: {result.compliance_status}")
    print(f"   置信度: {result.confidence}")
    print(f"   分析文件: {', '.join(result.files_analyzed) if result.files_analyzed else '无'}")
    print(f"   证据: {result.evidence}")
    
    print(f"\n5. 关键优势:")
    print(f"   ✅ 文件直接上传到OpenAI，无需在prompt中嵌入")
    print(f"   ✅ LLM可以智能检索相关文件内容")
    print(f"   ✅ 支持更大的知识库")
    print(f"   ✅ 更高效的token使用")
    print(f"   ✅ 符合OpenAI最佳实践")

def show_uploaded_file_content():
    """展示上传的文件内容格式"""
    print(f"\n" + "="*60)
    print("上传的文件内容格式示例")
    print("="*60)
    
    # 读取并展示转换后的文件格式
    try:
        with open("out/defs_python.txt", 'r', encoding='utf-8') as f:
            content = f.read()
            print("defs文件内容预览:")
            print(content[:500] + "..." if len(content) > 500 else content)
    except FileNotFoundError:
        print("defs.txt文件不存在（可能已被清理）")
    
    try:
        with open("out/calls_python.txt", 'r', encoding='utf-8') as f:
            content = f.read()
            print("\ncalls文件内容预览:")
            print(content[:500] + "..." if len(content) > 500 else content)
    except FileNotFoundError:
        print("calls.txt文件不存在（可能已被清理）")

def main():
    demo_file_upload_approach()
    show_uploaded_file_content()

if __name__ == "__main__":
    main()



