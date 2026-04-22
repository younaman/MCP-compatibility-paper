#!/usr/bin/env python3
"""
简化版合规检查器：直接遍历源码目录
不依赖 IR 来收集文件列表
"""

import json
import time
import tempfile
import os
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, asdict
import openai


@dataclass
class ComplianceResult:
    rule_id: int
    rule_type: str
    rule_text: str
    compliance_status: str
    evidence: List[str]
    confidence: float
    explanation: str
    files_analyzed: List[str]
    code_snippets: List[str]


class SimplifiedComplianceChecker:
    """
    简化版：直接遍历源码目录上传所有 Python 文件
    """
    
    def __init__(self, rules_file: str, defs_file: str, calls_file: str,
                 source_root: str = ".", api_key: str = None,
                 model: str = "gpt-4o", debug: bool = False,
                 max_source_files: int = 100,
                 skip_patterns: List[str] = None,
                 cleanup: bool = True):
        self.rules_file = rules_file
        self.defs_file = defs_file
        self.calls_file = calls_file
        self.source_root = Path(source_root)
        self.model = model
        self.debug = debug
        self.max_source_files = max_source_files
        self.cleanup = cleanup
        
        # 默认跳过的模式
        self.skip_patterns = skip_patterns or [
            "test", "tests", "__pycache__", "venv", ".venv",
            "example", "examples", "demo", "docs", ".git",
            "build", "dist", "*.egg-info"
        ]

        self.client = openai.OpenAI(api_key=api_key)
        self.rules = self._load_rules()
        
        # 记录创建的资源（用于清理）
        self.created_file_ids = []
        self.vector_store_id = None
        self.assistant_id = None
        self.file_id_map = {}

        self._setup_assistant()

    def _dbg(self, *args):
        if self.debug:
            print(*args)

    @staticmethod
    def _strip_rule_metadata(rule: Dict) -> Dict:
        """移除可能误导模型的来源信息（如 file_path/line_number）"""
        return {k: v for k, v in rule.items() if k not in ("file_path", "line_number")}

    def _load_rules(self) -> List[Dict]:
        with open(self.rules_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _should_skip(self, file_path: Path) -> bool:
        """判断是否应该跳过某个文件"""
        path_str = str(file_path).lower()
        
        for pattern in self.skip_patterns:
            if pattern in path_str:
                return True
        
        return False

    def _collect_source_files(self) -> List[Path]:
        """递归遍历源码目录，收集所有源代码文件"""
        print("📋 递归遍历源码目录...")
        
        source_files = []
        
        # 递归查找所有文件（不限制类型）
        for file_path in self.source_root.rglob("*"):
            # 只处理文件，跳过目录
            if not file_path.is_file():
                continue
            
            # 跳过无关文件
            if self._should_skip(file_path):
                self._dbg(f"  跳过: {file_path.name}")
                continue
            
            source_files.append(file_path)
        
        # 排序（为了可重现性）
        source_files = sorted(source_files)
        
        # 限制数量（max_source_files <= 0 表示不限制）
        if self.max_source_files and self.max_source_files > 0:
            if len(source_files) > self.max_source_files:
                print(f"⚠️  源文件过多（{len(source_files)}），只上传前 {self.max_source_files} 个")
                print(f"   提示：可以通过 --max-source-files 调整限制（0 或负数表示不限制）")
                source_files = source_files[:self.max_source_files]
        
        print(f"✓ 找到 {len(source_files)} 个源文件（所有类型）")
        
        # 显示文件类型统计
        if source_files:
            from collections import Counter
            extensions = Counter(f.suffix for f in source_files)
            print(f"\n  文件类型分布:")
            for ext, count in extensions.most_common(10):
                ext_display = ext if ext else "(无扩展名)"
                print(f"    {ext_display}: {count} 个")
        
        # 显示一些文件样例
        if self.debug and source_files:
            print("\n  样例文件:")
            for f in source_files[:5]:
                try:
                    rel = f.relative_to(self.source_root)
                    print(f"    - {rel}")
                except:
                    print(f"    - {f.name}")
            if len(source_files) > 5:
                print(f"    ... 还有 {len(source_files) - 5} 个文件")
        
        return source_files

    def _prepare_source_file(self, file_path: Path) -> str:
        """在文件开头添加绝对路径标记"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            original_content = f.read()
        
        # 使用绝对路径（Windows 兼容）
        abs_path = file_path.resolve()
        
        # 根据文件类型选择注释格式
        ext = file_path.suffix.lower()
        
        # 不同语言的注释格式
        if ext in ['.py', '.sh', '.yml', '.yaml', '.rb', '.pl', '.r']:
            # Python, Shell, YAML, Ruby, Perl, R
            header = f"""# ============================================
# FILE_PATH: {abs_path}
# ============================================

"""
        elif ext in ['.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.cc', '.h', '.hpp', '.cs', '.go', '.rs', '.swift', '.kt']:
            # JavaScript, TypeScript, Java, C/C++, C#, Go, Rust, Swift, Kotlin
            header = f"""// ============================================
// FILE_PATH: {abs_path}
// ============================================

"""
        elif ext in ['.html', '.xml', '.svg']:
            # HTML, XML
            header = f"""<!-- ============================================
FILE_PATH: {abs_path}
============================================ -->

"""
        elif ext in ['.css', '.scss', '.sass', '.less']:
            # CSS
            header = f"""/* ============================================
FILE_PATH: {abs_path}
============================================ */

"""
        elif ext in ['.md', '.markdown']:
            # Markdown
            header = f"""[//]: # (FILE_PATH: {abs_path})

"""
        else:
            # 默认：使用 # 注释（大多数语言支持）
            header = f"""# FILE_PATH: {abs_path}

"""
        
        return header + original_content

    def _get_upload_suffix(self, file_path: Path) -> str:
        """获取上传时应该使用的扩展名"""
        # OpenAI 支持的扩展名（完整列表）
        supported = {
            '.c', '.cpp', '.cs', '.css', '.csv', '.doc', '.docx',
            '.go', '.html', '.java', '.js', '.json',
            '.md', '.pdf', '.php', '.pptx', '.py', '.rb',
            '.sh', '.tex', '.ts', '.txt'
        }
        
        original = file_path.suffix.lower()
        
        if original in supported:
            return original
        else:
            # 不支持的扩展名转为 .txt
            return '.txt'
    
    def _upload_file_with_path(self, file_path: Path) -> str:
        """上传文件（添加路径标记，处理不支持的扩展名）"""
        try:
            # 准备内容（添加 FILE_PATH 标记）
            content = self._prepare_source_file(file_path)
            
            # 获取上传时的扩展名
            upload_suffix = self._get_upload_suffix(file_path)
            original_suffix = file_path.suffix.lower()
            
            # 如果需要转换，记录日志
            if upload_suffix != original_suffix:
                self._dbg(f"  转换: {file_path.name} ({original_suffix} → {upload_suffix})")
            
            # 创建临时文件（使用支持的扩展名）
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix=upload_suffix,
                delete=False,
                encoding='utf-8'
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # 上传临时文件
                with open(tmp_path, "rb") as f:
                    file_obj = self.client.files.create(file=f, purpose="assistants")
                
                # 记录文件 ID ↔ 路径
                self.file_id_map[file_obj.id] = str(file_path.resolve())
                self._dbg(f"  ✓ {file_path.name} → {file_obj.id}")
                return file_obj.id
            finally:
                # 删除临时文件
                os.unlink(tmp_path)
            
        except Exception as e:
            print(f"  ✗ 上传失败 {file_path.name}: {e}")
            return None

    def _upload_ir_file(self, file_path: str, display_name: str) -> str:
        """上传 IR 文件（JSONL 需要改扩展名）"""
        original_path = Path(file_path)
        
        # OpenAI 不支持 .jsonl，需要改成 .json
        if original_path.suffix == '.jsonl':
            # 创建临时 .json 文件
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                delete=False,
                encoding='utf-8'
            ) as tmp:
                with open(original_path, 'r', encoding='utf-8') as f:
                    tmp.write(f.read())
                tmp_path = tmp.name
            
            # 上传临时文件
            try:
                with open(tmp_path, "rb") as f:
                    file_obj = self.client.files.create(file=f, purpose="assistants")
                file_id = file_obj.id
                # 记录 IR 文件映射
                self.file_id_map[file_id] = str(original_path.resolve())
            finally:
                # 删除临时文件
                os.unlink(tmp_path)
        else:
            # 其他格式直接上传
            with open(original_path, "rb") as f:
                file_obj = self.client.files.create(file=f, purpose="assistants")
            file_id = file_obj.id
            # 记录 IR 文件映射
            self.file_id_map[file_id] = str(original_path.resolve())
        
        print(f"  ✓ {display_name} → {file_id}")
        return file_id

    def _setup_assistant(self):
        """设置 Assistant"""
        print("\n" + "="*60)
        print("初始化 Assistant")
        print("="*60)
        
        # 1. 上传 IR 文件
        print("\n📤 上传 IR 文件...")
        
        defs_file_id = self._upload_ir_file(self.defs_file, Path(self.defs_file).name)
        self.created_file_ids.append(defs_file_id)
        
        calls_file_id = self._upload_ir_file(self.calls_file, Path(self.calls_file).name)
        self.created_file_ids.append(calls_file_id)

        # 2. 遍历并上传源文件
        print("\n📤 上传源代码文件...")
        source_files = self._collect_source_files()
        source_file_ids = []
        
        print("  开始上传...")
        for i, source_file in enumerate(source_files, 1):
            if i % 10 == 0 or i == len(source_files):
                print(f"  进度: {i}/{len(source_files)}", end="\r")
            
            file_id = self._upload_file_with_path(source_file)
            if file_id:
                source_file_ids.append(file_id)
                self.created_file_ids.append(file_id)
        
        print(f"\n✓ 成功上传 {len(source_file_ids)} 个源文件")

        # 3. 创建 Vector Store
        print("\n🗄️  创建 Vector Store...")
        all_file_ids = [defs_file_id, calls_file_id] + source_file_ids
        
        self.vector_store = self.client.vector_stores.create(
            name="MCP Knowledge Base",
            file_ids=all_file_ids
        )
        self.vector_store_id = self.vector_store.id
        print(f"  ✓ Vector Store ID: {self.vector_store_id}")
        print(f"  ✓ 包含 {len(all_file_ids)} 个文件")

        # 4. 等待索引完成（加超时和未完成文件提示）
        print("\n⏳ 等待文件索引...")
        max_wait = 120
        start_time = time.time()
        last_status = None

        while True:
            vs = self.client.vector_stores.retrieve(self.vector_store_id)

            completed = vs.file_counts.completed
            total = vs.file_counts.total
            failed = vs.file_counts.failed
            cancelled = getattr(vs.file_counts, "cancelled", 0)

            if completed == total:
                elapsed = int(time.time() - start_time)
                print(f"\n✓ 索引完成（{completed}/{total}，耗时 {elapsed}s）")
                break

            if time.time() - start_time > max_wait:
                print(f"\n⚠️ 等待超时：索引停在 {completed}/{total}")
                print(f"\n✓ 索引状态（成功 {completed} 个，失败 {failed} 个，取消 {cancelled} 个，总数 {total}）")
                # 打印可能未完成的文件（通过映射表找到路径）
                indexed = set(getattr(vs, 'file_ids', []) or [])
                all_files = set(self.file_id_map.keys())
                pending = all_files - indexed
                if pending:
                    print("⚠️ 未完成的文件：")
                    for fid in list(pending)[:5]:
                        path = self.file_id_map.get(fid, "(未知路径)")
                        print(f"   - {path} ({fid})")
                    if len(pending) > 5:
                        print(f"   ... 还有 {len(pending)-5} 个文件未完成")
                else:
                    print("⚠️ 但未能找到具体未完成的文件映射。")

                print("⚠️ 继续执行（跳过未完成文件）")
                break

            status = f"  进度: {completed}/{total}"
            if status != last_status:
                print(status, end="\r")
                last_status = status

            time.sleep(3)
        print("\n✅ 初始化完成")
        print("="*60 + "\n")

        # 5. 创建 Assistant
        print("\n🤖 创建 Assistant...")
        self.assistant = self.client.beta.assistants.create(
            model=self.model,
            name="MCP Compliance Checker",
            instructions="""
You are an MCP protocol compliance checker.

## Knowledge Base Structure

### 1. IR Files (Function Index)

**defs_python.jsonl** - Function Definitions
Format: Each line contains complete information for one file
```json
{
  "file": "absolute_path",
  "definitions": [
    {"kind": "func_def", "name": "function_name", "line":  line_number, ...}
  ]
}
```

**calls_python.jsonl** - Function Calls
Format: Each line contains complete information for one file
```json
{
  "file": "absolute_path",
  "calls": [
    {"kind": "func_call", "name": "function_name", "line": line_number, ...}
  ]
}
```

### 2. Source Code Files (Complete Implementation, Multi-language)

- All SDK source files (Python, TypeScript, Go, Rust, etc.)
- Each file has an absolute path marker at the beginning:
  
  Python/Shell files:
  ```python
  # ============================================
  # FILE_PATH: /path/to/file.py
  # ============================================
  ```
  
  JavaScript/TypeScript/Java/C++ files:
  ```javascript
  // ============================================
  // FILE_PATH: /path/to/file.ts
  // ============================================
  ```
  
  HTML/XML files:
  ```html
  <!-- FILE_PATH: /path/to/file.html -->
  ```

## 🎯 Retrieval Strategy (Phased Approach to Avoid Information Overload)

### Phase 1: Quick Location (IR Only)

**1.1 Find Function Definitions**
- Search in defs_python.jsonl
- Keywords: function_name + "func_def"
- Record: which file, which line

**1.2 Check Call Relationships**
- Search in calls_python.jsonl
- Keywords: function_name + "func_call"
- Understand: who calls whom

**1.3 Initial Assessment**
- Based on IR information, can compliance be determined?
- Yes → Direct conclusion
- No → Explain which file's source code to check

### Phase 2: Source Code Verification (Only When Necessary)

**2.1 Precise Search for Source Files**
- Use complete path search
- Format: `"FILE_PATH: complete_path"`
- For example: `"FILE_PATH: C:\\Users\\<ANON_ID>\\...\\server.py"`

**2.2 Verify Implementation Details**
- Review the complete code
- Confirm if it conforms to the rule

### Phase 3: Comprehensive Judgment

Return JSON formatted result

## 🔍 Search Techniques

**Find Function Definitions:**
```
"name": "initialize"
or: "initialize" "func_def"
```

**Find Function Calls:**
```
"name": "initialize" "func_call"
or: "who calls initialize"
```

**Find Source Code:**
```
"FILE_PATH: server.py"
or: "FILE_PATH: C:\\Users\\...\\server.py"
```

**Trace Call Chain:**
```
1. Find function definition in defs → know which file
2. Find call relationship in calls → know who calls whom
3. Verify implementation in source code → confirm details
```

## 📊 Output Format

```json
{
  "action": "final_judgment",
  "status": "COMPLIANT" | "NON_COMPLIANT" | "UNCLEAR",
  "confidence": 0.0-1.0,
  "explanation": "Detailed explanation of the judgment basis",
  "evidence": [
    "Phase 1-IR: Found function X in defs, defined in file.py:45",
    "Phase 1-IR: Confirmed main calls X in calls",
    "Phase 2-Source Code: Verified implementation in FILE_PATH: file.py"
  ],
  "files_analyzed": ["Actual viewed file paths"],
  "code_snippets": ["Key code snippets"]
}
```

## ⚡ Efficiency Principles

1. IR First, Source Later**: If IR can determine compliance, don't check source
2. **Precise Search**: Use complete path, avoid fuzzy queries
3. **Step by Step**: One problem at a time
4. **Explain Intention**: Explain what you're looking for and why before each search

## Mandatory Constraints
1. **Do not provide final conclusions without reading IR** (`defs_python.jsonl` or `calls_python.jsonl`).
2. **For each file you read**, add the absolute path in the header `FILE_PATH: ...` to the `files_analyzed` array.
3. When returning `UNCLEAR`, **also** write down "why it's unclear" and "which IR/source code files you've checked".

Remember: You have a complete knowledge base, but don't need to read it all at once.
Like a detective, follow the clues step by step!

## Fallback Mode
If IR phase or first search doesn't locate source code, or your result has empty files_analyzed:
1.Temporarily ignore IR, only use source code for judgment;
2.Do extensive search on the entire codebase: First use keywords extracted from rule text (e.g., ping/heartbeat/keepalive/interval/timeout/notify/backoff, etc.), expand synonyms if necessary;
3. Actually open and read source code (at least 10 files, or stop when sufficient evidence is found). Each time you read a file, record its `FILE_PATH:` in `files_analyzed`;
4. Then output the JSON of `action=final_judgment`, and `files_analyzed` must not be empty.
5. Do not output action=final_judgment when files_analyzed is empty.
6. If the first search doesn't hit, must enter fallback mode before giving the final JSON.

            """,
            tools=[{"type": "file_search"}],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [self.vector_store.id]
                }
            }
        )
        
        self.assistant_id = self.assistant.id
        print(f"  ✓ Assistant ID: {self.assistant_id}")
        print("\n" + "="*60)
        print("✅ 初始化完成")
        print("="*60 + "\n")

    def check_rule(self, rule: Dict) -> ComplianceResult:
        """检查单条规则"""
        rule_id = rule.get("id") or rule.get("rule_id")
        print(f"\n{'='*60}")
        print(f"🔎 检查规则 {rule_id}")
        print(f"{'='*60}")

        thread = self.client.beta.threads.create()

        clean_rule = self._strip_rule_metadata(rule)

        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"""
Please check the compliance of the following MCP rule:

{json.dumps(clean_rule, indent=2, ensure_ascii=False)}

## ⚠️ Important: SDK's Responsibility

You are checking an **SDK framework**, not application code.

For SDK frameworks, the "SHOULD" and "MUST" requirements in rules mean:
- **SDK should implement and encapsulate these behaviors**
- **not** let application developers implement themselves
- **The value of SDK** is that developers don't need to care about protocol details

### Example

Rule: Servers should send notifications when the tool list changes

❌ Non-compliant SDK:
```python
# Only provide field definitions, let developers send notifications themselves
class ToolsCapability:
    listChanged: bool
```

✅ Compliant SDK:
```python
# SDK automatically handles notifications
class Server:
    def add_tool(self, tool):
        self.tools.append(tool)
        if self.capabilities.listChanged:
            self._send_notification()  # SDK automatically sends notifications
```

## Inspection Standards

### For rules of type "SHOULD/MUST send notification":

**Must find the following evidence to determine COMPLIANT:**
1. ✅ Ability definition (e.g., `listChanged` field)
2. ✅ **Internal notification sending logic within SDK**
   - For example: in add_tool/remove_tool methods
   - Automatically call send_notification() or similar methods
   - No need for developers to manually call

**If only the first item is found, and the second item is not found → NON_COMPLIANT**

Reason: The SDK did not implement the behavior required by the rule, and shifted the responsibility to the developers

## Inspection Steps (Must be in order)

### 🔍 Phase 1: IR Analysis

1. Find related function definitions in defs_python.jsonl
2. Check call relationships in calls_python.jsonl
3. Initial assessment: Is IR information enough?

### 🔬 Phase 2: Source Code Verification (Only When Necessary)

4. Use precise path search for source files
5. Verify specific implementation details
6. **Check**：SDK 是否自动处理了规则要求的行为
SDK automatically handles the behavior required by the rule

### ✅ Phase 3: Final Judgment

7. Return JSON formatted result

## ⚠️ Important Reminders

- Use IR to locate, then check source code
- Explain intention before each search
- Use complete path (FILE_PATH)
- Avoid broad searches
- don't judge compliant just because "ability definition" is found
- must find the automatic implementation logic of the SDK

Start analyzing!
"""
        )

        # 多轮交互
        max_turns = 25
        for turn in range(max_turns):
            self._dbg(f"\n--- 第 {turn + 1} 轮 ---")

            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )

            while True:
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )

                if run.status == "completed":
                    break
                elif run.status in ["failed", "cancelled", "expired"]:
                    print(f"❌ 失败: {run.status}")
                    if run.last_error:
                        print(f"   错误: {run.last_error}")
                    return self._create_unclear_result(rule, f"失败: {run.status}")

                time.sleep(2)

            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id,
                order="desc",
                limit=1
            )

            if not messages.data:
                continue

            assistant_message = messages.data[0]
            if assistant_message.role != "assistant":
                continue

            content = assistant_message.content[0].text.value
            
            if self.debug:
                print(f"\n💬 LLM：\n{content[:600]}...\n")

            # 解析最终判断
            try:
                json_str = content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()

                response_data = json.loads(json_str)
                
                if response_data and isinstance(response_data, dict) and response_data.get("action", "").lower() == "final_judgment":
#                if response_data.get("action") == "final_judgment":
                    print("✅ 获得最终判断")
                    
                    files_analyzed = response_data.get("files_analyzed", [])
                    print(f"📊 实际查看的文件数: {len(files_analyzed)}")
                    
                    return ComplianceResult(
                        rule_id=rule_id,
                        rule_type=rule.get("type", ""),
                        rule_text=rule.get("context", rule.get("full_text", "")),
                        compliance_status=response_data.get("status", "UNCLEAR"),
                        evidence=response_data.get("evidence", []),
                        confidence=response_data.get("confidence", 0.0),
                        explanation=response_data.get("explanation", ""),
                        files_analyzed=files_analyzed,
                        code_snippets=response_data.get("code_snippets", [])
                    )
            except json.JSONDecodeError:
                continue

        print("⏱️  超时")
        return self._create_unclear_result(rule, "超时")

    

    
    def _create_unclear_result(self, rule: Dict, reason: str) -> ComplianceResult:
        rule_id = rule.get("id") or rule.get("rule_id")
        return ComplianceResult(
            rule_id=rule_id,
            rule_type=rule.get("type", ""),
            rule_text=rule.get("context", rule.get("full_text", "")),
            compliance_status="UNCLEAR",
            evidence=[],
            confidence=0.0,
            explanation=reason,
            files_analyzed=[],
            code_snippets=[]
        )

    def check_rule_by_id(self, rule_id: int):
        """按 ID 检查单条规则"""
        for r in self.rules:
            if r.get("id") == rule_id or r.get("rule_id") == rule_id:
                return self.check_rule(r)
        raise ValueError(f"规则 {rule_id} 未找到")

    def check_all_rules(self) -> List[ComplianceResult]:
        """检查所有规则"""
        results = []
        for i, rule in enumerate(self.rules, 1):
            print(f"\n{'='*60}")
            print(f"进度: {i}/{len(self.rules)}")
            print(f"{'='*60}")
            result = self.check_rule(rule)
            results.append(result)
        return results

    def check_rules_batch(self, start_rule: int = None, end_rule: int = None, 
                         existing_results: List[ComplianceResult] = None) -> List[ComplianceResult]:
        """分批检查规则，支持断点续传"""
        # 过滤规则范围
        filtered_rules = []
        for rule in self.rules:
            rule_id = rule.get("id") or rule.get("rule_id")
            if rule_id is None:
                continue
            if start_rule and rule_id < start_rule:
                continue
            if end_rule and rule_id > end_rule:
                continue
            filtered_rules.append(rule)
        
        # 获取已处理的规则ID
        processed_ids = set()
        if existing_results:
            processed_ids = {r.rule_id for r in existing_results}
        
        # 过滤掉已处理的规则
        pending_rules = []
        for rule in filtered_rules:
            rule_id = rule.get("id") or rule.get("rule_id")
            if rule_id not in processed_ids:
                pending_rules.append(rule)
        
        print(f"📋 规则范围: {start_rule or '开始'} - {end_rule or '结束'}")
        print(f"📋 总规则数: {len(filtered_rules)}")
        print(f"📋 已处理: {len(processed_ids)}")
        print(f"📋 待处理: {len(pending_rules)}")
        
        if not pending_rules:
            print("✅ 所有规则已处理完成")
            return existing_results or []
        
        # 处理待处理的规则
        results = existing_results or []
        for i, rule in enumerate(pending_rules, 1):
            rule_id = rule.get("id") or rule.get("rule_id")
            print(f"\n{'='*60}")
            print(f"进度: {i}/{len(pending_rules)} (规则 {rule_id})")
            print(f"{'='*60}")
            result = self.check_rule(rule)
            results.append(result)
        
        return results

    def load_existing_results(self, output_file: str) -> List[ComplianceResult]:
        """从 JSONL 文件加载已有结果"""
        if not Path(output_file).exists():
            return []
        
        results = []
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        results.append(ComplianceResult(**data))
        except Exception as e:
            print(f"⚠️ 加载已有结果失败: {e}")
            return []
        
        print(f"📂 已加载 {len(results)} 个已有结果")
        return results

    def cleanup_resources(self):
        """清理创建的资源"""
        if not self.cleanup:
            print("\n⚠️  跳过资源清理（--no-cleanup）")
            return
        
        print("\n" + "="*60)
        print("🧹 清理资源")
        print("="*60)
        
        # 1. 删除 Assistant
        if self.assistant_id:
            try:
                self.client.beta.assistants.delete(self.assistant_id)
                print(f"✓ 已删除 Assistant: {self.assistant_id}")
            except Exception as e:
                print(f"✗ 删除 Assistant 失败: {e}")
        
        # 2. 删除 Vector Store
        if self.vector_store_id:
            try:
                self.client.vector_stores.delete(self.vector_store_id)
                print(f"✓ 已删除 Vector Store: {self.vector_store_id}")
            except Exception as e:
                print(f"✗ 删除 Vector Store 失败: {e}")
        
        # 3. 删除上传的文件
        if self.created_file_ids:
            print(f"🗑️  删除 {len(self.created_file_ids)} 个上传的文件...")
            success_count = 0
            for i, file_id in enumerate(self.created_file_ids, 1):
                try:
                    self.client.files.delete(file_id)
                    success_count += 1
                    if i % 10 == 0 or i == len(self.created_file_ids):
                        print(f"  进度: {i}/{len(self.created_file_ids)}", end="\r")
                except Exception as e:
                    self._dbg(f"  ✗ 删除文件 {file_id} 失败: {e}")
            
            print(f"\n✓ 成功删除 {success_count}/{len(self.created_file_ids)} 个文件")
        
        print("\n✅ 资源清理完成")
    
    def __enter__(self):
        """支持 with 语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """with 语句结束时自动清理"""
        self.cleanup_resources()
        return False


    # old code
    def check_all_rules(self) -> List[ComplianceResult]:
        """检查所有规则"""
        results = []
        for i, rule in enumerate(self.rules, 1):
            print(f"\n{'='*60}")
            print(f"进度: {i}/{len(self.rules)}")
            print(f"{'='*60}")
            result = self.check_rule(rule)
            results.append(result)
        return results


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="MCP 合规性检查工具（简化版：直接遍历源码目录）"
    )
    parser.add_argument("--rules", required=True,
                       help="规则文件路径")
    parser.add_argument("--defs", required=True,
                       help="函数定义 IR 文件")
    parser.add_argument("--calls", required=True,
                       help="函数调用 IR 文件")
    parser.add_argument("--source-root", required=True,
                       help="SDK 源码根目录（支持多语言）")
    parser.add_argument("--rule-id", type=int,
                       help="只检查指定 ID 的规则")
    parser.add_argument("--api-key",
                       help="OpenAI API Key（或设置环境变量 OPENAI_API_KEY）")
    parser.add_argument("--model", default="gpt-4o",
                       help="使用的模型")
    parser.add_argument("--max-source-files", type=int, default=100,
                       help="最多上传多少个源文件（0 或负数表示不限制）")
    parser.add_argument("--skip-patterns", nargs="+",
                       help="跳过的文件模式（如 test demo）")
    parser.add_argument("--no-cleanup", action="store_true",
                       help="不清理资源（保留 Vector Store 和文件）")
    parser.add_argument("--debug", action="store_true",
                       help="显示详细日志和 LLM 思考过程")
    parser.add_argument("--output", default="compliance_report.json",
                       help="输出报告文件路径")
    parser.add_argument("--output-format", choices=["json", "jsonl"], default="json",
                       help="输出格式：json（汇总报告）或 jsonl（逐条结果）")
    parser.add_argument("--start-rule", type=int,
                       help="开始规则ID（用于分批处理）")
    parser.add_argument("--end-rule", type=int,
                       help="结束规则ID（用于分批处理）")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="每批处理的规则数量（默认50）")
    args = parser.parse_args()

    # 使用 with 语句自动清理资源
    with SimplifiedComplianceChecker(
        rules_file=args.rules,
        defs_file=args.defs,
        calls_file=args.calls,
        source_root=args.source_root,
        api_key=args.api_key,
        model=args.model,
        max_source_files=args.max_source_files,
        skip_patterns=args.skip_patterns,
        cleanup=not args.no_cleanup,
        debug=args.debug
    ) as checker:
        if args.rule_id:
            result = checker.check_rule_by_id(args.rule_id)
            print("\n" + "="*60)
            print("检查结果")
            print("="*60)
            if args.output_format == "jsonl":
                with open(args.output.replace('.json', '.jsonl'), 'w', encoding='utf-8') as f:
                    f.write(json.dumps(asdict(result), ensure_ascii=False) + '\n')
                print(f"✅ 单条结果已保存到: {args.output.replace('.json', '.jsonl')}")
            else:
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        else:
            # 分批处理逻辑
            if args.start_rule or args.end_rule:
                # 加载已有结果（如果使用 JSONL 格式）
                existing_results = []
                if args.output_format == "jsonl":
                    output_file = args.output.replace('.json', '.jsonl')
                    existing_results = checker.load_existing_results(output_file)
                
                # 分批处理
                results = checker.check_rules_batch(
                    start_rule=args.start_rule,
                    end_rule=args.end_rule,
                    existing_results=existing_results
                )
            else:
                # 全量处理
                results = checker.check_all_rules()

            # 输出结果
            if args.output_format == "jsonl":
                # JSONL 格式：逐条追加
                output_file = args.output.replace('.json', '.jsonl')
                mode = 'a' if (args.start_rule or args.end_rule) else 'w'
                with open(output_file, mode, encoding='utf-8') as f:
                    for result in results:
                        f.write(json.dumps(asdict(result), ensure_ascii=False) + '\n')
                
                print(f"\n✅ JSONL 报告已生成: {output_file}")
                print(f"   总规则数: {len(results)}")
            else:
                # JSON 格式：汇总报告
                report = {
                    "summary": {
                        "total": len(results),
                        "compliant": sum(1 for r in results if r.compliance_status == "COMPLIANT"),
                        "non_compliant": sum(1 for r in results if r.compliance_status == "NON_COMPLIANT"),
                        "unclear": sum(1 for r in results if r.compliance_status == "UNCLEAR"),
                        "avg_files_per_rule": sum(len(r.files_analyzed) for r in results) / len(results) if results else 0
                    },
                    "results": [asdict(r) for r in results]
                }

                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)

                print(f"\n✅ 报告已生成: {args.output}")
                print(f"   合规: {report['summary']['compliant']}")
                print(f"   不合规: {report['summary']['non_compliant']}")
                print(f"   不确定: {report['summary']['unclear']}")
                print(f"   平均每条规则查看 {report['summary']['avg_files_per_rule']:.1f} 个文件")
    
    # with 语句结束时会自动调用 cleanup_resources()


if __name__ == "__main__":
    main()

