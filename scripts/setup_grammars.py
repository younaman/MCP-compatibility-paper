import subprocess
import sys
from pathlib import Path
from typing import Dict

VENDOR = Path("vendor").resolve()

GRAMMARS: Dict[str, str] = {
    "https://github.com/tree-sitter/tree-sitter-python": "tree-sitter-python",
    "https://github.com/tree-sitter/tree-sitter-typescript": "tree-sitter-typescript",
    "https://github.com/tree-sitter/tree-sitter-go": "tree-sitter-go",
    "https://github.com/tree-sitter/tree-sitter-java": "tree-sitter-java",
    "https://github.com/tree-sitter/tree-sitter-c-sharp": "tree-sitter-c-sharp",
    "https://github.com/tree-sitter/kotlin-tree-sitter": "tree-sitter-kotlin",
    "https://github.com/tree-sitter/tree-sitter-php": "tree-sitter-php",
    "https://github.com/tree-sitter/tree-sitter-ruby": "tree-sitter-ruby",
    "https://github.com/tree-sitter/tree-sitter-rust": "tree-sitter-rust",
    "https://github.com/alex-pinkus/tree-sitter-swift": "tree-sitter-swift",
}


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def ensure_repo(url: str, subdir: str) -> None:
    dest = VENDOR / subdir
    if dest.exists():
        print(f"Exists: {dest}")
        return
    VENDOR.mkdir(parents=True, exist_ok=True)
    code = run(["git", "clone", "--depth", "1", url, str(dest)])
    if code != 0:
        print(f"ERROR cloning {url}")
        return


def main() -> None:
    for url, sub in GRAMMARS.items():
        ensure_repo(url, sub)
    print(f"OK -> {VENDOR}")


if __name__ == "__main__":
    main()

