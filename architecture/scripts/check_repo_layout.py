#!/usr/bin/env python3
"""Lightweight repository/website link check; not an evidence-verifier."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent.parent
REQUIRED = (
    "README.md",
    "docs/index.html",
    "docs/js/app.js",
    "docs/anchor/DiyarAnchor.json",
    "docs/data/ledger.json",
    "docs/reference-source.zip",
    "docs/whitepaper.pdf",
    "paper/DIYAR whitepaper v2.7.pdf",
    "architecture/README.md",
    "architecture/implementation-status.md",
    "architecture/verification-model.md",
    "architecture/ui-direction.md",
    "architecture/repository-map.md",
    "architecture/reproduce.md",
    "reference-and-tests/README.md",
    "reference-and-tests/diyar/replay.py",
    "reference-and-tests/tests/test_replay.py",
    "reference-and-tests/run_pipeline.py",
    "reference-and-tests/results/v2_run/ledger.json",
    "reference-and-tests/DIYAR_cost_model.xlsx",
    "reference-and-tests/paper/DIYAR-whitepaper-v2.7.md",
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
for markdown in [ROOT / "README.md", *sorted((ROOT / "architecture").glob("*.md"))]:
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

# Published highlights must remain byte-identical to their source snapshots.
MIRRORS = [("e1_summary.json","e1"),("e1_custody_volume.png","e1"),
 ("e2_summary.json","e2"),("e2_flag_rates_fox.png","e2"),
 ("e3a_quarterly.json","e3"),("e3a_extra.json","e3"),
 ("e3b_results.json","e3"),("e3_gates_fox.png","e3"),
 ("e4_results.json","e4")]
for name, group in MIRRORS:
    original = ROOT / "reference-and-tests" / "results" / name
    mirror = ROOT / "results" / group / name
    if not original.is_file() or not mirror.is_file():
        errors.append(f"Missing result mirror: {name}")
    elif hashlib.sha256(original.read_bytes()).digest() != hashlib.sha256(mirror.read_bytes()).digest():
        errors.append(f"Result mirror does not match reference: {name}")

if errors:
    print("Repository checks FAILED:")
    print("\n".join(f"- {error}" for error in errors))
    sys.exit(1)
print(f"Repository layout OK; checked {len(REQUIRED)} required files and local navigation links.")
