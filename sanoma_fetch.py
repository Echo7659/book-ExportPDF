#!/usr/bin/env python3
"""Fetch + decode all Sanoma / LibroMedia 6.0 pages into one combined HTML.

Usage:
    python3 sanoma_fetch.py <product_id> [--start 1] [--end N]

Reads  output/sanoma/<product_id>/session.json   (from sanoma_capture.py)
Writes output/sanoma/<product_id>/pNNNN.html and combined.html

Decoding of ".data" = base64 -> JS-unescape(%XX and %uXXXX) -> subtract a
fixed key per position (Vigenere over char codes).
"""
import argparse
import base64
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "sanoma"

KEY = "1cff42dabb60beaf1e3b57988af787246c63613ef60435a05c9c79b98a9b41c8"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")
REFERER = "https://npmitaly-pro-apidistribucion.sanoma.it/viewers/lm60/online/index.html"


def js_unescape(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "%":
            if i + 5 < n and s[i + 1] == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", s[i + 2:i + 6]):
                out.append(chr(int(s[i + 2:i + 6], 16))); i += 6; continue
            if i + 2 < n and re.fullmatch(r"[0-9a-fA-F]{2}", s[i + 1:i + 3]):
                out.append(chr(int(s[i + 1:i + 3], 16))); i += 3; continue
        out.append(c); i += 1
    return "".join(out)


def decrypt(raw: str) -> str:
    e = re.sub(r"[^A-Za-z0-9+/=]", "", raw)
    s = js_unescape(base64.b64decode(e).decode("latin1"))
    return "".join(chr((ord(ch) - ord(KEY[i % len(KEY) - 1])) & 0xFFFF)
                   for i, ch in enumerate(s))


class Fetcher:
    def __init__(self, cookies):
        names = {"CloudFront-Policy", "CloudFront-Signature", "CloudFront-Key-Pair-Id"}
        self.jar = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c["name"] in names)
        if not self.jar:
            raise SystemExit("no CloudFront cookies in session")

    def get(self, url):
        req = urllib.request.Request(url, headers={
            "Cookie": self.jar, "Referer": REFERER, "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.read()


PAGE_TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@page {{ size: {w}px {h}px; margin: 0; }}
html,body {{ margin:0; padding:0; }}
.pagewrap {{ width:{w}px; height:{h}px; position:relative; overflow:hidden;
              page-break-after: always; break-after: page; }}
.t {{ color: transparent !important; }}
</style></head><body>
{pages}
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=0)
    a = ap.parse_args()

    d = OUT / a.product
    sess = json.loads((d / "session.json").read_text())
    base = sess["base"].rstrip("/") + "/"
    f = Fetcher(sess["cookies"])

    sizes = json.loads(decrypt(f.get(base + "sizes.data").decode("latin1")))
    (d / "sizes.json").write_text(json.dumps(sizes))
    N = len(sizes)
    end = a.end or N
    w, h = sizes[0]
    print(f"product {a.product}: {N} pages", flush=True)

    parts = []
    for p in range(a.start, end + 1):
        pf = d / f"p{p:04d}.html"
        if pf.exists() and pf.stat().st_size > 50:
            html = pf.read_text()
        else:
            html = decrypt(f.get(f"{base}{p}.data").decode("latin1"))
            html = html.replace("#PATH#", base).replace("#SCALE#", "1")
            pf.write_text(html)
        parts.append(f'<div class="pagewrap">{html}</div>')
        if p % 10 == 0 or p == end:
            print(f"  {p}/{end}", flush=True)

    combined = PAGE_TEMPLATE.format(w=w, h=h, pages="\n".join(parts))
    out = d / "combined.html"
    out.write_text(combined)
    print("combined html:", out, len(combined) // 1024, "KB")


if __name__ == "__main__":
    main()
