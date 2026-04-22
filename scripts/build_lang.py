import platform
from pathlib import Path
from tree_sitter import Language

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
BUILD = ROOT / "build"

system = platform.system().lower()
if system == "windows":
    OUT = BUILD / "my-languages.dll"
elif system == "darwin":
    OUT = BUILD / "my-languages.dylib"
else:
    OUT = BUILD / "my-languages.so"

GRAMMAR_DIRS = [
    VENDOR / "tree-sitter-python",
    VENDOR / "tree-sitter-go",
    VENDOR / "tree-sitter-java",
    VENDOR / "tree-sitter-c-sharp",
    VENDOR / "tree-sitter-php",
    VENDOR / "tree-sitter-ruby",
    VENDOR / "tree-sitter-rust",
    VENDOR / "tree-sitter-swift",
    VENDOR / "tree-sitter-typescript" / "typescript",
    VENDOR / "tree-sitter-typescript" / "tsx",
]


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    dirs = [str(p) for p in GRAMMAR_DIRS if p.exists()]
    if not dirs:
        raise SystemExit("No grammar directories found. Run scripts/setup_grammars.py first.")
    Language.build_library(str(OUT), dirs)
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    main()

