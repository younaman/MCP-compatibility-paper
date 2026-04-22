#!/usr/bin/env python3
"""
测试脚本：验证提示词中的动态文件名和扩展名是否正确生成
"""

from pathlib import Path

class TestComplianceChecker:
    def __init__(self, defs_file: str, calls_file: str):
        self.defs_file = defs_file
        self.calls_file = calls_file
    
    def _get_language_extension(self) -> str:
        """根据文件名推断语言扩展名"""
        defs_name = Path(self.defs_file).name.lower()
        if 'python' in defs_name:
            return 'py'
        elif 'go' in defs_name:
            return 'go'
        elif 'java' in defs_name:
            return 'java'
        elif 'kotlin' in defs_name:
            return 'kt'
        elif 'c_sharp' in defs_name or 'csharp' in defs_name:
            return 'cs'
        elif 'php' in defs_name:
            return 'php'
        elif 'ruby' in defs_name:
            return 'rb'
        elif 'rust' in defs_name:
            return 'rs'
        elif 'swift' in defs_name:
            return 'swift'
        elif 'typescript' in defs_name:
            return 'ts'
        else:
            return 'py'  # 默认返回py
    
    def generate_test_prompt(self) -> str:
        """生成测试提示词"""
        return f"""
You are an MCP protocol compliance checker.

## Knowledge Base Structure

### 1. IR Files (Function Index)

**{Path(self.defs_file).name}** - Function Definitions
Format: Each line contains complete information for one file
```json
{{
  "file": "absolute_path",
  "definitions": [
    {{"kind": "func_def", "name": "function_name", "line":  line_number, ...}}
  ]
}}
```

**{Path(self.calls_file).name}** - Function Calls
Format: Each line contains complete information for one file
```json
{{
  "file": "absolute_path",
  "calls": [
    {{"kind": "func_call", "name": "function_name", "line": line_number, ...}}
  ]
}}
```

### 2. Source Code Files (Complete Implementation, Multi-language)

- All SDK source files (Python, TypeScript, Go, Rust, etc.)
- Each file has an absolute path marker at the beginning:
  
  Python/Shell files:
  ```python
  # ============================================
  # FILE_PATH: /path/to/file.{self._get_language_extension()}
  # ============================================
  ```
  
  JavaScript/TypeScript/Java/C++ files:
  ```javascript
  // ============================================
  // FILE_PATH: /path/to/file.ts
  // ============================================
  ```

## 🎯 Retrieval Strategy (Phased Approach to Avoid Information Overload)

### Phase 1: Quick Location (IR Only)

**1.1 Find Function Definitions**
- Search in {Path(self.defs_file).name}
- Keywords: function_name + "func_def"
- Record: which file, which line

**1.2 Check Call Relationships**
- Search in {Path(self.calls_file).name}
- Keywords: function_name + "func_call"
- Understand: who calls whom

### Phase 2: Source Code Verification (Only When Necessary)

**2.1 Precise Search for Source Files**
- Use complete path search
- Format: `"FILE_PATH: complete_path"`
- For example: `"FILE_PATH: C:\\Users\\95250\\...\\server.{self._get_language_extension()}"`

**Find Source Code:**
```
"FILE_PATH: server.{self._get_language_extension()}"
or: "FILE_PATH: C:\\Users\\...\\server.{self._get_language_extension()}"
```

## 📊 Output Format

```json
{{
  "action": "final_judgment",
  "status": "COMPLIANT" | "NON_COMPLIANT" | "UNCLEAR",
  "confidence": 0.0-1.0,
  "explanation": "Detailed explanation of the judgment basis",
  "evidence": [
    "Phase 1-IR: Found function X in {Path(self.defs_file).name}, defined in file.{self._get_language_extension()}:45",
    "Phase 1-IR: Confirmed main calls X in {Path(self.calls_file).name}",
    "Phase 2-Source Code: Verified implementation in FILE_PATH: file.{self._get_language_extension()}"
  ],
  "files_analyzed": ["Actual viewed file paths"],
  "code_snippets": ["Key code snippets"]
}}
```

## Mandatory Constraints
1. **Do not provide final conclusions without reading IR** (`{Path(self.defs_file).name}` or `{Path(self.calls_file).name}`).
2. **For each file you read**, add the absolute path in the header `FILE_PATH: ...` to the `files_analyzed` array.
3. When returning `UNCLEAR`, **also** write down "why it's unclear" and "which IR/source code files you've checked".

Remember: You have a complete knowledge base, but don't need to read it all at once.
Like a detective, follow the clues step by step!
"""

def test_all_languages():
    """测试所有语言的提示词生成"""
    languages = [
        ("out/defs_python.jsonl", "out/calls_python.jsonl"),
        ("out/defs_go.jsonl", "out/calls_go.jsonl"),
        ("out/defs_java.jsonl", "out/calls_java.jsonl"),
        ("out/defs_kotlin.jsonl", "out/calls_kotlin.jsonl"),
        ("out/defs_c_sharp.jsonl", "out/calls_c_sharp.jsonl"),
        ("out/defs_php.jsonl", "out/calls_php.jsonl"),
        ("out/defs_ruby.jsonl", "out/calls_ruby.jsonl"),
        ("out/defs_rust.jsonl", "out/calls_rust.jsonl"),
        ("out/defs_swift.jsonl", "out/calls_swift.jsonl"),
        ("out/defs_typescript.jsonl", "out/calls_typescript.jsonl"),
    ]
    
    print("=" * 80)
    print("测试所有语言的提示词生成")
    print("=" * 80)
    
    for defs_file, calls_file in languages:
        print(f"\n🔍 测试语言: {Path(defs_file).name}")
        print("-" * 50)
        
        checker = TestComplianceChecker(defs_file, calls_file)
        prompt = checker.generate_test_prompt()
        
        # 提取关键信息进行验证
        defs_name = Path(defs_file).name
        calls_name = Path(calls_file).name
        ext = checker._get_language_extension()
        
        print(f"✅ defs文件名: {defs_name}")
        print(f"✅ calls文件名: {calls_name}")
        print(f"✅ 语言扩展名: {ext}")
        
        # 验证提示词中的关键部分
        if defs_name in prompt and calls_name in prompt:
            print("✅ 文件名正确嵌入提示词")
        else:
            print("❌ 文件名未正确嵌入提示词")
            
        if f"file.{ext}" in prompt:
            print("✅ 扩展名正确嵌入提示词")
        else:
            print("❌ 扩展名未正确嵌入提示词")
            
        # 显示示例输出
        print(f"📝 示例输出: 'Phase 1-IR: Found function X in {defs_name}, defined in file.{ext}:45'")

if __name__ == "__main__":
    test_all_languages()
















