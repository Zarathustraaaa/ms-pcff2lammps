#!/usr/bin/env python3
"""Fail CI if likely proprietary force-field assets are committed."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {"pcff.off", "pcff.frc"}
FORBIDDEN_SUFFIXES = {".off", ".frc"}
ALLOW_SUFFIX_PATHS = set()

problems: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    rel = path.relative_to(ROOT)
    lower = path.name.lower()
    if lower in FORBIDDEN_NAMES:
        problems.append(f"forbidden parameter database name: {rel}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES and rel not in ALLOW_SUFFIX_PATHS:
        problems.append(f"forbidden parameter database extension: {rel}")
    if lower.startswith("pcff_native_bendbend") and path.suffix.lower() == ".csv":
        problems.append(f"native parameter export must remain local: {rel}")

if problems:
    print("Repository hygiene check failed:")
    for problem in problems:
        print(f"- {problem}")
    raise SystemExit(1)
print("Repository hygiene check passed")
