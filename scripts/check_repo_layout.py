#!/usr/bin/env python3
"""Lightweight repository/website link check; not an evidence-verifier."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/index.html",
    "docs/js/app.js",
    "docs/anchor/DiyarAnchor.json",
    "docs/data/ledger.json",
    "docs/reference-source.zip",
    "docs/whitepaper.pdf",
    "paper/DIYAR whitepaper v2.7.pdf",
    "project/README.md",
    "project/implementation-status.md",
    "project/verification-model.md",
    "project/ui-direction.md",
    "project/repository-map.md",
    "project/reproduce.md",
    "reference/README.md",
    "reference/diyar/replay.py",
    "reference/tests/test_replay.py",
    "reference/run_pipeline.py",
    "reference/results/v2_run/ledger.json",
    "reference/DIYAR_cost_model.xlsx",
    "reference/paper/DIYAR-whitepaper-v2.7.md",
)
errors: list[str] = []
for filename in REQUIRED:
    if not (ROOT / filename).is_file():
        errors.append(f"Missing required file: {filename}")

def check_local(url: str, base: Path, label: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or url.startswith(("#", "mailto:", "data:")):
        return
    path = unquote(parsed.path)
    if not path:
        return
    target = (base / path).resolve()
    if not target.is_relative_to(ROOT):
        errors.append(f"{label}: link escapes repository: {url}")
    elif not target.exists():
        errors.append(f"{label}: broken relative link: {url}")

# Readme and project navigation paths should be meaningful.
for markdown in [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "project").glob("*.md"))]:
    if not markdown.exists():
        continue
    source = markdown.read_text(encoding="utf-8")
    for url in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", source):
        check_local(url, markdown.parent, str(markdown.relative_to(ROOT)))

# GitHub Pages: check all local stylesheets, scripts and favicon paths.
page = ROOT / "docs/index.html"
if page.exists():
    source = page.read_text(encoding="utf-8")
    for url in re.findall(r'<(?:script|link)\b[^>]*\b(?:src|href)="([^"]+)"', source):
        check_local(url, page.parent, "docs/index.html")

# The canonical whitepaper and its website mirror must match byte for byte.
a, b = ROOT / "paper/DIYAR whitepaper v2.7.pdf", ROOT / "docs/whitepaper.pdf"
if a.exists() and b.exists():
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    if digest(a) != digest(b):
        errors.append("Whitepaper PDF and GitHub Pages PDF differ")

if errors:
    print("Repository checks FAILED:")
    print("\n".join(f"- {error}" for error in errors))
    sys.exit(1)
print(f"Repository layout OK; checked {len(REQUIRED)} required files and local navigation links.")
