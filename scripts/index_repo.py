import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Any, Tuple

from pathspec import PathSpec
from tree_sitter import Parser, Query
from tqdm import tqdm

# Prefer new language pack, fall back to old one
_new_get_language = None
_old_get_language = None
try:
    try:
        from tree_sitter_language_pack import get_language as _new_get_language  # type: ignore
    except Exception:
        import tree_sitter_language_pack as _tslp  # type: ignore
        if hasattr(_tslp, "get_language"):
            _new_get_language = getattr(_tslp, "get_language")
except Exception:
    pass

if _new_get_language is None:
    try:
        from tree_sitter_languages import get_language as _old_get_language  # type: ignore
    except Exception:
        _old_get_language = None


def load_language(lang_id: str):
    if _new_get_language is not None:
        try:
            return _new_get_language(lang_id)
        except Exception:
            pass
    if _old_get_language is not None:
        try:
            return _old_get_language(lang_id)
        except Exception:
            pass
    return None

ROOT = Path(__file__).resolve().parent.parent

# Map language key -> (suffixes, tree-sitter language id)
LANG_CONFIG: Dict[str, Tuple[List[str], str]] = {
    "python": ([".py"], "python"),
    "typescript": ([".ts", ".mts"], "typescript"),
    "go": ([".go"], "go"),
    "java": ([".java"], "java"),
    "c_sharp": ([".cs"], "csharp"),
    "kotlin": ([".kt", ".kts"], "kotlin"),
    "php": ([".php"], "php"),
    "ruby": ([".rb"], "ruby"),
    "rust": ([".rs"], "rust"),
    "swift": ([".swift"], "swift"),
}

LANG_BY_ID = {}
for lang_key, (_, lang_id) in LANG_CONFIG.items():
    lang = load_language(lang_id)
    if lang is not None:
        LANG_BY_ID[lang_key] = lang

PARSERS: Dict[str, Parser] = {k: Parser() for k in LANG_BY_ID.keys()}
for k, p in PARSERS.items():
    p.language = LANG_BY_ID[k]

QUERIES: Dict[str, Query] = {}
DEF_QUERIES: Dict[str, Query] = {}

# PY_QUERY 现在通过 load_python_queries() 动态加载

# 动态加载查询文件
def load_queries(lang):
    try:
        with open(f"scripts/queries/{lang}-queries.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None

# 动态加载Go调用查询文件
def load_go_calls_queries():
    go_calls_query = load_queries("go-calls")
    if go_calls_query:
        return go_calls_query
    # 回退到内联查询
    return r"""
(call_expression
  function: (selector_expression
    operand: (_) @recv
    field: (field_identifier) @method)) @mcall
(call_expression
  function: (identifier) @func) @fcall
"""

# 动态加载Go定义查询文件
def load_go_defs_queries():
    go_defs_query = load_queries("go-defs")
    if go_defs_query:
        return go_defs_query
    # 回退到内联查询
    return r"""
(function_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @func_def
(method_declaration
  receiver: (parameter_list) @receiver
  name: (field_identifier) @name
  parameters: (parameter_list) @params) @method_def
"""

# 动态加载Python调用查询文件
def load_python_calls_queries():
    python_calls_query = load_queries("python-calls")
    if python_calls_query:
        return python_calls_query
    # 回退到内联查询
    return r"""
(call
  function: (attribute
    object: (_) @recv
    attribute: (identifier) @method)) @mcall
(call
  function: (identifier) @func) @fcall
"""

# 动态加载Python定义查询文件
def load_python_defs_queries():
    python_defs_query = load_queries("python-defs")
    if python_defs_query:
        return python_defs_query
    # 回退到内联查询
    return r"""
(function_definition
  name: (identifier) @name
  parameters: (parameters) @params) @func_def
(class_definition
  name: (identifier) @name) @class_def
"""

# 动态加载Rust查询文件
def load_rust_queries():
    rust_query = load_queries("rust")
    if rust_query:
        return rust_query
    # 回退到内联查询
    return r"""
(call_expression
  function: (field_expression
    value: (_) @recv
    field: (field_identifier) @method)) @mcall
(call_expression
  function: (identifier) @func) @fcall
"""

# 动态加载Rust定义查询文件
def load_rust_def_queries():
    try:
        with open("scripts/queries/rust-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(function_item
  name: (identifier) @name
  parameters: (parameters) @params) @func_def
(struct_item
  name: (type_identifier) @name) @struct_def
(enum_item
  name: (type_identifier) @name) @enum_def
(trait_item
  name: (type_identifier) @name) @trait_def
"""

# 动态加载TypeScript调用查询文件
def load_typescript_calls_queries():
    try:
        with open("scripts/queries/typescript-calls.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(call_expression
  function: (member_expression
    object: (_) @recv
    property: (property_identifier) @method)) @mcall
(call_expression
  function: (identifier) @func) @fcall
(new_expression
  constructor: (identifier) @func) @fcall
"""

# 动态加载TypeScript定义查询文件
def load_typescript_defs_queries():
    try:
        with open("scripts/queries/typescript-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(function_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @func_def
(method_definition
  name: (property_identifier) @name
  parameters: (formal_parameters) @params) @method_def
(class_declaration
  name: (type_identifier) @name) @class_def
(interface_declaration
  name: (type_identifier) @name) @interface_def
(type_alias_declaration
  name: (type_identifier) @name) @type_def
(enum_declaration
  name: (identifier) @name) @enum_def
"""

# 动态加载Java调用查询文件
def load_java_calls_queries():
    try:
        with open("scripts/queries/java-calls.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(method_invocation
  name: (identifier) @func) @fcall
(method_invocation
  object: (_) @recv
  name: (identifier) @method) @mcall
"""

# 动态加载Java定义查询文件
def load_java_defs_queries():
    try:
        with open("scripts/queries/java-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(method_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @method_def
(constructor_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @ctor_def
(class_declaration
  name: (identifier) @name) @class_def
(interface_declaration
  name: (identifier) @name) @interface_def
(enum_declaration
  name: (identifier) @name) @enum_def
(record_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @record_def
"""

# 动态加载C#调用查询文件
def load_csharp_calls_queries():
    try:
        with open("scripts/queries/c-sharp-calls.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(invocation_expression
  function: (member_access_expression
    expression: (_) @recv
    name: (_) @method)) @mcall
(invocation_expression
  function: (identifier) @func) @fcall
(object_creation_expression
  type: (_) @func) @fcall
"""

# 动态加载C#定义查询文件
def load_csharp_defs_queries():
    try:
        with open("scripts/queries/c-sharp-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(local_function_statement
  name: (identifier) @name
  parameters: (parameter_list) @params) @func_def
(method_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @method_def
(constructor_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @constructor_def
(destructor_declaration
  name: (identifier) @name) @destructor_def
(class_declaration
  name: (identifier) @name) @class_def
(struct_declaration
  name: (identifier) @name) @struct_def
(interface_declaration
  name: (identifier) @name) @interface_def
(enum_declaration
  name: (identifier) @name) @enum_def
(delegate_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @delegate_def
(record_declaration
  name: (identifier) @name) @record_def
"""

# 动态加载Ruby调用查询文件
def load_ruby_calls_queries():
    try:
        with open("scripts/queries/ruby-calls.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(call
  method: (identifier) @func) @call
(call
  receiver: (_) @recv
  method: (identifier) @method) @mcall
(command_call
  method: (identifier) @func
  arguments: (argument_list)?) @ccall
(_call
  receiver: (_) @recv
  method: (identifier) @method) @chained
"""

# 动态加载Ruby定义查询文件
def load_ruby_defs_queries():
    try:
        with open("scripts/queries/ruby-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(method
  name: (identifier) @name
  parameters: (method_parameters)? @params) @method_def
(singleton_method
  name: (identifier) @name
  parameters: (method_parameters)? @params) @singleton_def
(class
  name: (constant) @classname
  body: (body_statement)?) @class_def
(module
  name: (constant) @modname
  body: (body_statement)?) @module_def
"""

# 动态加载PHP调用查询文件
def load_php_calls_queries():
    try:
        with open("scripts/queries/php-calls.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(function_call_expression
  function: (name) @func_name
  arguments: (arguments)? @args) @fcall
(scoped_call_expression
  scope: (_) @class
  (name) @method_name
  arguments: (arguments)? @args) @scall
(member_call_expression
  object: (_) @recv
  (name) @method_name
  arguments: (arguments)? @args) @mcall
(nullsafe_member_call_expression
  object: (_) @recv
  (name) @method_name
  arguments: (arguments)? @args) @nmcall
"""

# 动态加载PHP定义查询文件
def load_php_defs_queries():
    try:
        with open("scripts/queries/php-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(function_definition
  name: (name) @name
  parameters: (formal_parameters)? @params
  body: (compound_statement) @body) @func_def
(method_declaration
  name: (name) @name
  parameters: (formal_parameters)? @params
  body: (compound_statement)? @body) @method_def
(anonymous_function
  parameters: (formal_parameters)? @params
  body: (compound_statement) @body) @anon_func
(arrow_function
  parameters: (formal_parameters)? @params
  body: (expression) @body) @arrow_func
(class_declaration
  name: (name) @classname
  body: (declaration_list) @body) @class_def
(interface_declaration
  name: (name) @iname
  body: (declaration_list) @body) @interface_def
(trait_declaration
  name: (name) @tname
  body: (declaration_list) @body) @trait_def
(enum_declaration
  name: (name) @ename
  body: (enum_declaration_list) @body) @enum_def
"""

# 动态加载Swift调用查询文件
def load_swift_calls_queries():
    try:
        with open("scripts/queries/swift-calls.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(call_expression
  function: (identifier) @func
  arguments: (argument_list)? ) @fcall
(call_expression
  function: (navigation_expression
    target: (_) @recv
    suffix: (identifier) @method)
  arguments: (argument_list)? ) @mcall
"""

# 动态加载Swift定义查询文件
def load_swift_defs_queries():
    try:
        with open("scripts/queries/swift-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(function_declaration
  name: (identifier) @name
  signature: (function_signature) @params) @func_def
(init_declaration
  name: (identifier) @name
  signature: (function_signature) @params) @init_def
(class_declaration
  name: (type_identifier) @name) @class_def
(struct_declaration
  name: (type_identifier) @name) @struct_def
(protocol_declaration
  name: (type_identifier) @name) @protocol_def
(enum_declaration
  name: (type_identifier) @name) @enum_def
"""

# 动态加载Kotlin调用查询文件
def load_kotlin_calls_queries():
    try:
        with open("scripts/queries/kotlin-calls.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(call_expression
  (simple_identifier) @func) @fcall
(call_expression
  (navigation_expression
    (simple_identifier) @method)) @mcall
(call_expression
  (simple_identifier) @func
  (call_suffix
    (type_arguments))) @fcall
(call_expression
  (simple_identifier) @func
  (call_suffix
    (annotated_lambda) @lambda)) @fcall_with_lambda
"""

# 动态加载Kotlin定义查询文件
def load_kotlin_defs_queries():
    try:
        with open("scripts/queries/kotlin-defs.scm", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 回退到内联查询
        return r"""
(function_declaration
  (simple_identifier) @name
  (function_value_parameters) @params) @func_def
(function_declaration
  (receiver_type) @receiver
  (simple_identifier) @name
  (function_value_parameters) @params) @method_def
(lambda_literal) @anon_func_def
(anonymous_function) @anon_func_def
"""

GO_QUERY = load_go_calls_queries()
GO_DEF_QUERY = load_go_defs_queries()
PY_QUERY = load_python_calls_queries()
PY_DEF_QUERY = load_python_defs_queries()
RUST_QUERY = load_rust_queries()
RUST_DEF_QUERY = load_rust_def_queries()
TS_QUERY = load_typescript_calls_queries()
TS_DEF_QUERY = load_typescript_defs_queries()
JAVA_QUERY = load_java_calls_queries()
JAVA_DEF_QUERY = load_java_defs_queries()
CS_QUERY = load_csharp_calls_queries()
CS_DEF_QUERY = load_csharp_defs_queries()
RUBY_QUERY = load_ruby_calls_queries()
RUBY_DEF_QUERY = load_ruby_defs_queries()
PHP_QUERY = load_php_calls_queries()
PHP_DEF_QUERY = load_php_defs_queries()
SWIFT_QUERY = load_swift_calls_queries()
SWIFT_DEF_QUERY = load_swift_defs_queries()
KOTLIN_QUERY = load_kotlin_calls_queries()
KOTLIN_DEF_QUERY = load_kotlin_defs_queries()

# TS_QUERY 现在通过 load_typescript_calls_queries() 动态加载

# JAVA_QUERY 现在通过 load_java_calls_queries() 动态加载

# CS_QUERY 现在通过 load_csharp_calls_queries() 动态加载

# RUST_QUERY 现在通过 load_rust_queries() 动态加载

# RUBY_QUERY 现在通过 load_ruby_calls_queries() 动态加载

# PHP_QUERY 现在通过 load_php_calls_queries() 动态加载

# SWIFT_QUERY 现在通过 load_swift_calls_queries() 动态加载

# KOTLIN_QUERY 现在通过 load_kotlin_calls_queries() 动态加载

QUERY_BY_LANG = {
    "python": PY_QUERY,
    "go": GO_QUERY,
    "typescript": TS_QUERY,
    "java": JAVA_QUERY,
    "c_sharp": CS_QUERY,
    "rust": RUST_QUERY,
    "ruby": RUBY_QUERY,
    "php": PHP_QUERY,
    "swift": SWIFT_QUERY,
    "kotlin": KOTLIN_QUERY,
}

for lang, qsrc in QUERY_BY_LANG.items():
    if lang in LANG_BY_ID:
        try:
            QUERIES[lang] = Query(LANG_BY_ID[lang], qsrc)
        except Exception:
            pass

# Definition queries for each language - 基于实际 AST 分析结果
# PY_DEF_QUERY 现在通过 load_python_defs_queries() 动态加载

# GO_DEF_QUERY 已合并到 GO_QUERY 中

# TS_DEF_QUERY 现在通过 load_typescript_defs_queries() 动态加载

JAVA_DEF_QUERY = r"""
(method_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @method_def
(class_declaration
  name: (identifier) @name) @class_def
(interface_declaration
  name: (identifier) @name) @interface_def
"""

CS_DEF_QUERY = r"""
(method_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @method_def
(class_declaration
  name: (identifier) @name) @class_def
(interface_declaration
  name: (identifier) @name) @interface_def
(local_function_statement
  name: (identifier) @name
  parameters: (parameter_list) @params) @func_def
"""

# RUST_DEF_QUERY 现在通过 load_rust_def_queries() 动态加载

RUBY_DEF_QUERY = r"""
(method
  name: (identifier) @name
  parameters: (method_parameters) @params) @method_def
(class
  name: (constant) @name) @class_def
(module
  name: (constant) @name) @module_def
"""

PHP_DEF_QUERY = r"""
(method_declaration
  name: (name) @name
  parameters: (formal_parameters) @params) @method_def
(class_declaration
  name: (name) @name) @class_def
(function_definition
  name: (name) @name
  parameters: (formal_parameters) @params) @func_def
(interface_declaration
  name: (name) @name) @interface_def
"""

# SWIFT_DEF_QUERY 现在通过 load_swift_defs_queries() 动态加载

# KOTLIN_DEF_QUERY 现在通过 load_kotlin_defs_queries() 动态加载

DEF_QUERY_BY_LANG = {
    "python": PY_DEF_QUERY,  # Python现在使用专门的定义查询文件
    "go": GO_DEF_QUERY,  # Go现在使用专门的定义查询文件
    "typescript": TS_DEF_QUERY,  # TypeScript现在使用专门的定义查询文件
    "java": JAVA_DEF_QUERY,  # Java现在使用专门的定义查询文件
    "c_sharp": CS_DEF_QUERY,
    "rust": RUST_DEF_QUERY,  # Rust现在使用专门的定义查询文件
    "ruby": RUBY_DEF_QUERY,
    "php": PHP_DEF_QUERY,
    "swift": SWIFT_DEF_QUERY,
    "kotlin": KOTLIN_DEF_QUERY,
}

for lang, qsrc in DEF_QUERY_BY_LANG.items():
    if lang in LANG_BY_ID:
        try:
            DEF_QUERIES[lang] = LANG_BY_ID[lang].query(qsrc)
        except Exception:
            pass

IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "build", ".idea", ".vscode","scripts", "tests", "out",
    "__pycache__", "env", ".venv", "venv", ".mypy_cache", ".pytest_cache", "dist", "target"
}


def load_gitignore(root: Path):
    p = root / ".gitignore"
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        return PathSpec.from_lines("gitwildmatch", f)


def iter_files(root: Path, suffixes: List[str], spec: PathSpec | None) -> Iterable[Path]:
    for dp, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            path = Path(dp) / fn
            rel = path.relative_to(root).as_posix()
            if spec and spec.match_file(rel):
                continue
            if any(fn.endswith(suf) for suf in suffixes):
                yield path


def slice_text(src: bytes, node) -> str:
    return src[node.start_byte: node.end_byte].decode("utf-8", errors="ignore")


def find_condition(node, src: bytes) -> str:
    """
    向上追溯 AST，找到条件/异常上下文，返回一个字符串
    支持 if / while / for / try/except 等
    """
    conds = []
    parent = node.parent
    while parent:
        t = parent.type

        if t in ["if_statement", "if_expression"]:
            cond = parent.child_by_field_name("condition")
            if cond:
                conds.append("if(" + slice_text(src, cond) + ")")

        elif t in ["while_statement", "while_expression"]:
            cond = parent.child_by_field_name("condition")
            if cond:
                conds.append("while(" + slice_text(src, cond) + ")")

        elif t in ["for_statement", "for_expression"]:
            # for 的条件有点复杂，这里先抽 target / iterator
            target = parent.child_by_field_name("left") or parent.child_by_field_name("init")
            iterator = parent.child_by_field_name("right") or parent.child_by_field_name("condition")
            if target and iterator:
                conds.append("for(" + slice_text(src, target) + " in " + slice_text(src, iterator) + ")")

        elif t in ["try_statement", "try_expression"]:
            conds.append("try")

        elif t in ["catch_clause", "except_clause", "catch_block"]:
            # 有的语言叫 catch_clause，有的叫 except_clause
            ex = parent.child_by_field_name("parameter") or parent.child_by_field_name("exception")
            if ex:
                conds.append("except(" + slice_text(src, ex) + ")")
            else:
                conds.append("except")

        parent = parent.parent

    if not conds:
        return "true"
    # 从内到外拼接，越内层的条件优先
    return " ∧ ".join(reversed(conds))


def node_to_json(src: bytes, node) -> Dict[str, Any]:
    obj: Dict[str, Any] = {
        "type": node.type,
        "start": {"line": node.start_point[0] + 1, "col": node.start_point[1] + 1},
        "end": {"line": node.end_point[0] + 1, "col": node.end_point[1] + 1},
    }
    if node.type in {"identifier", "string", "attribute", "field_identifier", "property_identifier"}:
        obj["text"] = slice_text(src, node)
    if node.children:
        obj["children"] = [node_to_json(src, ch) for ch in node.children]
    return obj


def extract_definitions(lang: str, src: bytes, root_node) -> List[Dict[str, Any]]:
    """Extract function/class/method definitions"""
    q = DEF_QUERIES.get(lang)
    if not q:
        return []
    definitions = []
    order = 0
    
    # 语言特定的参数字段名映射
    param_field_mapping = {
        "python": ["parameters"],
        "go": ["parameter_list"],
        "java": ["formal_parameters"],
        "rust": ["parameters"],
        "typescript": ["formal_parameters"],
        "c_sharp": ["parameter_list"],
        "kotlin": ["function_value_parameters"],
        "php": ["formal_parameters"],
        "ruby": ["method_parameters"],
        "swift": ["parameter_list"]
    }
    
    param_fields = param_field_mapping.get(lang, ["parameters", "params"])
    
    for match_id, captures in q.matches(root_node):
        # 收集当前匹配的所有捕获组
        name_nodes = captures.get("name", [])
        params_nodes = captures.get("params", [])
        
        for cap_name, nodes in captures.items():
            for node in nodes:
                order += 1
                if cap_name in ["func_def", "method_def", "class_def", "type_def", "struct_def", "impl_def", "impl_func_def", "interface_def", "module_def", "trait_def", "object_def", "protocol_def", "anon_func_def"]:
                    # 使用捕获组而不是字段名
                    name_node = name_nodes[0] if name_nodes else None
                    params_node = params_nodes[0] if params_nodes else None
                    
                    definition = {
                        "kind": cap_name,
                        "name": slice_text(src, name_node) if name_node else None,
                        "params": slice_text(src, params_node) if params_node else None,
                        "cond": find_condition(node, src),
                        "order": order,
                        "line": node.start_point[0] + 1,
                        "col": node.start_point[1] + 1,
                    }
                    definitions.append(definition)
    return definitions


def extract_calls(lang: str, src: bytes, root_node) -> List[Dict[str, Any]]:
    """Extract function and method calls with improved logic."""
    q = QUERIES.get(lang)
    if not q:
        return []
    out = []
    order = 0
    
    for match_id, captures in q.matches(root_node):
        # 收集当前匹配的所有捕获组
        recv_nodes = captures.get("recv", [])
        method_nodes = captures.get("method", []) or captures.get("method_name", [])
        func_nodes = captures.get("func", []) or captures.get("func_name", [])
        mcall_nodes = captures.get("mcall", [])
        fcall_nodes = captures.get("fcall", [])
        
        # 处理方法调用
        for node in mcall_nodes:
            order += 1
            recv = recv_nodes[0] if recv_nodes else None
            name = method_nodes[0] if method_nodes else None
            
            out.append({
                "kind": "method_call",
                "recv": slice_text(src, recv) if recv else None,
                "name": slice_text(src, name) if name else None,
                "cond": find_condition(node, src),
                "order": order,
                "line": node.start_point[0] + 1,
                "col": node.start_point[1] + 1,
            })
        
        # 处理函数调用
        for node in fcall_nodes:
            order += 1
            name = func_nodes[0] if func_nodes else None
            
            out.append({
                "kind": "func_call",
                "name": slice_text(src, name) if name else None,
                "recv": "",
                "cond": find_condition(node, src),
                "order": order,
                "line": node.start_point[0] + 1,
                "col": node.start_point[1] + 1,
            })
    
    return out


def index_repo(root: Path, out_dir: Path, emit_ast: bool) -> None:
    spec = load_gitignore(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    ast_files: Dict[str, Any] = {}
    if emit_ast:
        for lang in LANG_CONFIG.keys():
            if lang in PARSERS:
                ast_files[lang] = (out_dir / f"ast_{lang}.jsonl").open("w", encoding="utf-8")
    for lang, (suffixes, _) in LANG_CONFIG.items():
        if lang not in PARSERS:
            continue
        parser = PARSERS[lang]
        calls_path = out_dir / f"calls_{lang}.jsonl"
        defs_path = out_dir / f"defs_{lang}.jsonl"
        with calls_path.open("w", encoding="utf-8") as calls_out, defs_path.open("w", encoding="utf-8") as defs_out:
            files = list(iter_files(root, suffixes, spec))
            for path in tqdm(files, desc=f"{lang}"):
                try:
                    src = path.read_bytes()
                except Exception:
                    continue
                tree = parser.parse(src)
                root_node = tree.root_node
                
                # Extract calls and definitions
                calls = extract_calls(lang, src, root_node)
                definitions = extract_definitions(lang, src, root_node)
                
                # Add statistics for debugging
                total_m = sum(1 for ev in calls if ev["kind"] == "method_call")
                resolved = sum(1 for ev in calls if ev["kind"] == "method_call" and ev["name"])
                if total_m > 0:
                    ratio = resolved / total_m
                    if ratio < 0.5:  # Only print if ratio is low (indicating potential issues)
                        print(f"[{lang}] {path.name}: method_call total={total_m}, with_name={resolved}, ratio={ratio:.2%}")
                
                # Write calls
                calls_rec = {"file": str(path), "calls": calls}
                calls_out.write(json.dumps(calls_rec, ensure_ascii=False) + "\n")
                
                # Write definitions
                defs_rec = {"file": str(path), "definitions": definitions}
                defs_out.write(json.dumps(defs_rec, ensure_ascii=False) + "\n")
                
                if emit_ast:
                    ast_json = node_to_json(src, root_node)
                    ast_rec = {"file": str(path), "ast": ast_json}
                    ast_files[lang].write(json.dumps(ast_rec, ensure_ascii=False) + "\n")
    for f in ast_files.values():
        f.close()


def main() -> None:
    emit_ast = False
    args = [a for a in sys.argv[1:] if a != "--emit-ast"]
    if len(sys.argv) > 1 and "--emit-ast" in sys.argv[1:]:
        emit_ast = True
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parent.parent
    out_dir = Path(__file__).resolve().parent.parent / "out"
    index_repo(root, out_dir, emit_ast)
    print(f"OK -> {out_dir}")


if __name__ == "__main__":
    main()

