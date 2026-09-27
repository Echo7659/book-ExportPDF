#!/usr/bin/env python3
"""One-command Sanoma export: capture -> fetch/decode -> PDF.

Usage:
    python3 sanoma_export.py "<viewer_url>" [--space NAME]

Prereq: ego-browser profile is logged into the Sanoma/My Place book.
Output: output/sanoma/<product>.pdf
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(args):
    print("\n$ " + " ".join(args), flush=True)
    if subprocess.run(args, cwd=str(HERE)).returncode != 0:
        raise SystemExit(f"step failed: {' '.join(args)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--space", default="sanoma-download")
    a = ap.parse_args()
    py = sys.executable

    run([py, "sanoma_capture.py", a.url, a.space])

    # product id was written to output/sanoma/<id>/session.json ; find newest
    base = HERE / "output" / "sanoma"
    cands = sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
    if not cands:
        raise SystemExit("no captured product found")
    product = cands[-1].name
    print(f"\nproduct = {product}")

    run([py, "sanoma_fetch.py", product])
    run([py, "sanoma_build.py", product, a.space])
    print(f"\nDONE -> {base / (product + '.pdf')}")


if __name__ == "__main__":
    main()
