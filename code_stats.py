#!/usr/bin/env python3
"""代码统计分析工具 - 分析目录下的代码行数、文件类型分布、注释率"""

import os
import sys
from pathlib import Path
from collections import defaultdict

# 文件类型 → (注释单行前缀, 注释多行开始, 注释多行结束)
LANG_MAP = {
    ".py":   ("#", '"""', '"""'),
    ".js":   ("//", "/*", "*/"),
    ".ts":   ("//", "/*", "*/"),
    ".tsx":  ("//", "/*", "*/"),
    ".jsx":  ("//", "/*", "*/"),
    ".java": ("//", "/*", "*/"),
    ".c":    ("//", "/*", "*/"),
    ".cpp":  ("//", "/*", "*/"),
    ".h":    ("//", "/*", "*/"),
    ".go":   ("//", "/*", "*/"),
    ".rs":   ("//", "/*", "*/"),
    ".rb":   ("#", "=begin", "=end"),
    ".sh":   ("#", None, None),
    ".bash": ("#", None, None),
    ".yml":  ("#", None, None),
    ".yaml": ("#", None, None),
    ".toml": ("#", None, None),
    ".sql":  ("--", "/*", "*/"),
    ".html": (None, "<!--", "-->"),
    ".css":  (None, "/*", "*/"),
    ".vue":  ("//", "/*", "*/"),
    ".swift":("//", "/*", "*/"),
    ".kt":   ("//", "/*", "*/"),
    ".lua":  ("--", "--[[", "]]"),
    ".r":    ("#", None, None),
    ".php":  ("//", "/*", "*/"),
}

SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__",
    ".venv", "venv", "env", ".env", ".tox", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".eggs", "*.egg-info",
    "target", "vendor", ".next", ".nuxt", "coverage",
}


def should_skip(path: Path) -> bool:
    """判断是否跳过该目录"""
    return any(part in SKIP_DIRS for part in path.parts)


def analyze_file(filepath: Path) -> dict:
    """分析单个文件"""
    ext = filepath.suffix.lower()
    if ext not in LANG_MAP:
        return None

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except (OSError, PermissionError):
        return None

    line_comment, block_start, block_end = LANG_MAP[ext]
    total = len(lines)
    blank = 0
    comment = 0
    in_block = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank += 1
            continue
        if in_block:
            comment += 1
            if block_end and block_end in stripped:
                in_block = False
            continue
        if block_start and stripped.startswith(block_start):
            comment += 1
            if block_end and block_end not in stripped[len(block_start):]:
                in_block = True
            continue
        if line_comment and stripped.startswith(line_comment):
            comment += 1

    code = total - blank - comment
    return {
        "ext": ext,
        "total": total,
        "code": code,
        "comment": comment,
        "blank": blank,
    }


def format_bar(value: int, max_val: int, width: int = 30) -> str:
    """生成文本进度条"""
    if max_val == 0:
        return ""
    filled = int(width * value / max_val)
    return "█" * filled + "░" * (width - filled)


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if not target.is_dir():
        print(f"❌ 不是有效目录: {target}")
        sys.exit(1)

    # 收集文件
    stats_by_ext = defaultdict(lambda: {"files": 0, "total": 0, "code": 0, "comment": 0, "blank": 0})
    total_files = 0

    for filepath in target.rglob("*"):
        if not filepath.is_file() or should_skip(filepath):
            continue
        result = analyze_file(filepath)
        if result is None:
            continue
        total_files += 1
        ext = result["ext"]
        bucket = stats_by_ext[ext]
        bucket["files"] += 1
        for k in ("total", "code", "comment", "blank"):
            bucket[k] += result[k]

    if total_files == 0:
        print("未找到可分析的代码文件。")
        return

    # 汇总
    grand = {"files": 0, "total": 0, "code": 0, "comment": 0, "blank": 0}
    for bucket in stats_by_ext.values():
        for k in grand:
            grand[k] += bucket[k]

    # 输出
    print(f"\n📊 代码统计 — {target.resolve()}\n")
    print(f"{'类型':<8} {'文件数':>6} {'总行数':>8} {'代码行':>8} {'注释行':>8} {'空行':>8} {'注释率':>8}")
    print("─" * 62)

    # 按代码行数排序
    for ext, bucket in sorted(stats_by_ext.items(), key=lambda x: x[1]["code"], reverse=True):
        comment_rate = bucket["comment"] / max(bucket["code"] + bucket["comment"], 1) * 100
        print(f"{ext:<8} {bucket['files']:>6} {bucket['total']:>8} {bucket['code']:>8} "
              f"{bucket['comment']:>8} {bucket['blank']:>8} {comment_rate:>7.1f}%")

    print("─" * 62)
    comment_rate = grand["comment"] / max(grand["code"] + grand["comment"], 1) * 100
    print(f"{'合计':<8} {grand['files']:>6} {grand['total']:>8} {grand['code']:>8} "
          f"{grand['comment']:>8} {grand['blank']:>8} {comment_rate:>7.1f}%")

    # 文件类型分布图
    print(f"\n📁 文件类型分布（按代码行数）")
    max_code = max(b["code"] for b in stats_by_ext.values()) if stats_by_ext else 1
    for ext, bucket in sorted(stats_by_ext.items(), key=lambda x: x[1]["code"], reverse=True):
        bar = format_bar(bucket["code"], max_code)
        pct = bucket["code"] / max(grand["code"], 1) * 100
        print(f"  {ext:<8} {bar} {pct:5.1f}%")

    print(f"\n✅ 共 {grand['files']} 个文件, {grand['total']:,} 行 (代码 {grand['code']:,} / 注释 {grand['comment']:,} / 空行 {grand['blank']:,})")
    print(f"   代码占比 {grand['code']/max(grand['total'],1)*100:.1f}% | 注释率 {comment_rate:.1f}%\n")


if __name__ == "__main__":
    main()
