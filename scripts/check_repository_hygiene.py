#!/usr/bin/env python3
"""Fail if restricted validation assets or obvious private paths enter the tree."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


FORBIDDEN_SUFFIXES = {".off", ".frc", ".car", ".mdf", ".xsd"}
NATIVE_EXPORT_MARKERS = (
    "native_bendbend",
    "pcff_native",
    "bendbend_export",
)
NATIVE_EXPORT_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xls"}
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".toml", ".yml", ".yaml", ".json", ".cff", ".sh"
}
PRIVATE_PATH_PATTERNS = (
    re.compile(r"(?i)[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s]+"),
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
)


def find_problems(root: Path) -> list[str]:
    problems: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue

        lower_name = path.name.lower()
        suffix = path.suffix.lower()

        if suffix in FORBIDDEN_SUFFIXES:
            problems.append(f"restricted Materials Studio/parameter asset: {rel}")

        if suffix in NATIVE_EXPORT_SUFFIXES and any(
            marker in lower_name for marker in NATIVE_EXPORT_MARKERS
        ):
            problems.append(f"native parameter export must remain local: {rel}")

        if suffix in TEXT_SUFFIXES and path.stat().st_size <= 2_000_000:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in PRIVATE_PATH_PATTERNS:
                match = pattern.search(text)
                if match:
                    problems.append(
                        f"possible personal absolute path in {rel}: {match.group(0)!r}"
                    )
                    break

    return sorted(set(problems))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root to inspect",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    problems = find_problems(root)
    if problems:
        print("Repository hygiene check failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("Repository hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
