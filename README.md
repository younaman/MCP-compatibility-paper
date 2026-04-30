This repository contains tooling for **MCP SDK analysis** in three stages: building a unified intermediate representation (IR), running **LLM-assisted compliance** checks against MCP rules, and running an **exploitability-oriented threat pipeline** on specification text.

Python dependencies are listed in `requirements.txt` (tree-sitter, OpenAI client, etc.). Use a virtual environment and install with `pip install -r requirements.txt`.

---

## 1. IR generation

IR consists of per-language JSONL files under `out/`:

- `out/defs_<lang>.jsonl` — function/class (and related) **definitions** per source file  
- `out/calls_<lang>.jsonl` — **calls** (function and method calls) per source file  

Each line is one JSON object with a `file` key (absolute path at generation time) and `definitions` or `calls` arrays.

**Primary script:** `scripts/index_repo.py`

- Walks a source tree, parses files with tree-sitter AST pharser, and runs language-specific queries from `scripts/queries/*.scm` (with inline fallbacks).
- Supported language keys include: `python`, `typescript`, `go`, `java`, `c_sharp`, `kotlin`, `php`, `ruby`, `rust`, `swift`.

**Run (from repository root):**

```bash
python scripts/index_repo.py path/to/sdk-root
```

Output directory is fixed to `./out` relative to the repo root (see `main()` in `index_repo.py`). Optional flag `--emit-ast` also writes `ast_<lang>.jsonl`.

**Optional grammar setup** (only if you build languages from vendored grammars instead of prebuilt wheels):

```bash
python scripts/setup_grammars.py   # clone grammars under vendor/
python scripts/build_lang.py       # build shared library under build/
```

Languages are loaded via `tree_sitter_language_pack` or `tree_sitter_languages` when available.

---

## 2. Compliance analysis

**Script:** `scripts/auto_llm_compliance_checker.py`

This tool does **not** generate IR; it **consumes** IR plus rules and uploads material to the OpenAI Assistants API (vector store + file search) to judge each rule against an SDK.

**Inputs:**

| Argument | Role |
|----------|------|
| `--rules` | JSON file: list of rule objects (fields such as `id` / `rule_id`, `type`, `context` / `full_text`, etc.) |
| `--defs` | One `defs_*.jsonl` file (e.g. `out/defs_python.jsonl`) |
| `--calls` | Matching `calls_*.jsonl` file |
| `--source-root` | SDK root to scan; matching source files are uploaded (with a `FILE_PATH:` header) for deep inspection |

**Authentication:** set `OPENAI_API_KEY` or pass `--api-key`.

**Example:**

```bash
python scripts/auto_llm_compliance_checker.py \
  --rules path/to/rules.json \
  --defs out/defs_python.jsonl \
  --calls out/calls_python.jsonl \
  --source-root path/to/python-sdk-main/python-sdk-main \
  --output compliance_report.json
```
 **The rule file (`requirements_analysis.json`) contains the MCP clause specifications used in our analysis. It is preprocessed and normalized from the MCP specification, and is provided in the artifact for direct use.**
Use `--output-format jsonl` with `--start-rule` / `--end-rule` for chunked runs and resume via the same JSONL path. See `--help` for all flags.

**Privacy note for public or anonymous artifacts:** IR and uploaded sources embed absolute paths. Scrub or use relative paths before publishing if you must avoid machine-specific strings.

---

## 3. Exploitability analysis

**Entry point:** `scripts/exploitable_analyzer/pipeline.py`

End-to-end pipeline (three LLM-backed stages):

1. `semantic_analysis.py` — `analyze_semantics`  
2. `control_analysis.py` — `analyze_controls`  
3. `threat_derivation.py` — `derive_threats` (threats, scenarios, exploitability-style fields)

Shared client: `scripts/exploitable_analyzer/llm_client.py` (expects `OPENAI_API_KEY`).

**Run from the `exploitable_analyzer` directory** (imports are local):

```bash
cd scripts/exploitable_analyzer
python pipeline.py --requirements path/to/requirements_analysis.json --id 42 --noimplemented
```

Or feed a spec from a file or stdin:

```bash
python pipeline.py --spec path/to/spec_fragment.txt --implemented
# or
echo "..." | python pipeline.py --spec - --noimplemented
```

- `--implemented` — penetration-style scenario (implemented stack).  
- `--noimplemented` — architect-style “missing control” scenario (default if neither flag is set).

JSON result is printed to stdout (`semantic_analysis`, `control_analysis`, `threat_analysis`).

---

## Related scripts (short pointers)

| Path | Purpose |
|------|---------|
| `scripts/llm_rule_extractor.py` | LLM-based extraction from spec artifacts (rules JSON). |
| `scripts/rule_parser.py` / `scripts/rule_loader.py` | Rule parsing and loading helpers for other tooling. |
| `scripts/demo_llm_compliance.py` | Offline demo that reads `out/*.jsonl` without calling the API. |

For questions about a specific SDK subtree, refer to that SDK’s own README under `*-sdk-main/`.
