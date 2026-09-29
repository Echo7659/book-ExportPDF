#!/usr/bin/env python3
"""One-command myLIM (Loescher) export: capture -> download original PDF.

The myLIM reader is a plain pdf.js viewer over the *publisher's own PDF*:
the API hands out a short-lived presigned S3 link to the original file, so
the export is a straight download (text stays selectable, no image stitching).

Usage:
    python3 loescher_export.py "<viewer_url_or_isbn>" [--out NAME.pdf]
                               [--space NAME]

Examples:
    python3 loescher_export.py "https://mylim.loescher.it/#!/reader/9788858335604" \
            --out "output/loescher/Il tempo, l'uomo, il lavoro.pdf"
    python3 loescher_export.py 9788858335604

Prereq: ego-browser profile is logged into myLIM (log in once in an
ego-browser window).
Output: output/loescher/<isbn>.pdf  (or the name given with --out)
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from loescher_capture import API, OUT, isbn_from

ROOT = Path(__file__).resolve().parent

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")


def safe_name(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "-", title).strip()


def http_json(url: str, token: str):
    req = urllib.request.Request(url, headers={
        "Authorization": "JWT " + token,
        "Referer": "https://mylim.loescher.it/",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def download(url: str, dest: Path, ua: str = UA) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as fh:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            total += len(chunk)
            if total % (5 << 20) < (1 << 20):
                print(f"  {total // (1 << 20)} MB…", flush=True)
    tmp.replace(dest)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default=None, help="output pdf path (default: book title)")
    ap.add_argument("--space", default="mylim-download")
    a = ap.parse_args()

    isbn = isbn_from(a.url)
    py = sys.executable

    print("\n$ loescher_capture.py", a.url, a.space, flush=True)
    r = subprocess.run([py, str(ROOT / "loescher_capture.py"), a.url, a.space],
                       cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit("capture step failed")

    d = OUT / isbn
    sess = json.loads((d / "session.json").read_text())
    title = (sess.get("opera") or {}).get("nome") or isbn

    if a.out:
        out = Path(a.out)
        if not out.is_absolute():
            out = ROOT / out
    else:
        out = OUT / f"{safe_name(title)}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    expect = (sess.get("opera") or {}).get("dimensione_pdf") or 0
    for attempt in (1, 2):
        try:
            print(f"downloading {sess['pdfUrl'].split('?')[0]}", flush=True)
            n = download(sess["pdfUrl"], out)
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  attempt {attempt} failed: {e}", file=sys.stderr)
            if attempt == 2:
                raise SystemExit("download failed (presigned link expired?) — "
                                 "re-run loescher_capture.py and retry")
            # the presigned link lasts ~5 min; ask the API for a fresh one
            fresh = http_json(f"{API}pdf/{isbn}/", sess["token"])
            sess["pdfUrl"] = fresh["url"]
            (d / "session.json").write_text(json.dumps(sess, indent=1))

    print(f"\nDONE -> {out} ({n // 1024} KB, expected {expect // 1024} KB)")
    if expect and abs(n - expect) > 1024:
        print(f"warning: size differs from metadata ({n} vs {expect})", file=sys.stderr)
    if n < 100000 or open(out, "rb").read(5) != b"%PDF-":
        raise SystemExit("downloaded file is not a PDF")


if __name__ == "__main__":
    main()