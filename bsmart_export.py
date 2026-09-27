#!/usr/bin/env python3
"""One-command bSmart export: capture -> download -> PDF.

Usage:
    python3 bsmart_export.py "<viewer_url>" [--space 0] [--out NAME.pdf]
                             [--scale 2] [--quality 86] [--limit N]

Prereq: ego-browser profile is logged into bSmart and the book tab is open.
Output: output/<bookId>.pdf (or --out path)
"""
import argparse
import re
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
    ap.add_argument("--space", default="0")
    ap.add_argument("--out", default=None)
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--quality", type=int, default=86)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    py = sys.executable
    book = re.search(r"/books/(\d+)", a.url).group(1)
    out = a.out or f"output/{book}.pdf"

    run([py, "bsmart_capture.py", a.url, a.space])
    dl = [py, "download_book.py", book, "--scale", str(a.scale)]
    if a.limit:
        dl += ["--limit", str(a.limit)]
    run(dl)
    bd = [py, "build_book_pdf.py", book, "--quality", str(a.quality), "--out", out]
    if a.limit:
        bd += ["--limit", str(a.limit)]
    run(bd)
    print(f"\nDONE -> {HERE / out}")


if __name__ == "__main__":
    main()
