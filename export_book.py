#!/usr/bin/env python3
"""One-command export: capture token (from logged-in browser) -> download -> PDF.

Usage:
    python3 export_book.py <viewer_url> [--limit N] [--scale 2] [--quality 86]
                           [--space NAME] [--workers 12]

Example:
    python3 export_book.py https://young.hubscuola.it/viewer/7358681?page=1

Prereq: the ego-browser profile is logged into HUB Scuola (log in once in an
ego-browser window).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def book_id_from(url: str) -> str:
    m = re.search(r"/(?:viewer|i/d)/(\d+)", url)
    if not m:
        raise SystemExit(f"cannot find book id in url: {url}")
    return m.group(1)


def run(args):
    print("\n$ " + " ".join(args), flush=True)
    r = subprocess.run(args, cwd=str(HERE))
    if r.returncode != 0:
        raise SystemExit(f"step failed: {' '.join(args)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--quality", type=int, default=86)
    ap.add_argument("--space", default="hub-download")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()

    book = book_id_from(a.url)
    py = sys.executable

    # 1) capture tokens from the logged-in browser
    run([py, "capture_session.py", a.url, a.space])

    # 2) download tiles + text
    dl = [py, "download_book.py", book, "--scale", str(a.scale), "--workers", str(a.workers)]
    if a.limit:
        dl += ["--limit", str(a.limit)]
    run(dl)

    # 3) build the PDF
    bd = [py, "build_book_pdf.py", book, "--quality", str(a.quality)]
    if a.limit:
        bd += ["--limit", str(a.limit)]
    run(bd)

    out = HERE / "output" / f"{book}.pdf"
    print(f"\nDONE -> {out}")


if __name__ == "__main__":
    main()
