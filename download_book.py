#!/usr/bin/env python3
"""Download all page tiles + text layers for one HUB Scuola book.

Usage:
    python3 download_book.py <bookId> [--scale 2] [--tile 1024] [--workers 12]

Reads  output/<bookId>/session.json   (created by capture_session.py)
Writes output/<bookId>/tiles/pNNNN/tile_*.img
       output/<bookId>/text/pNNNN.json
       output/<bookId>/document.json   (page count + per-page sizes)

Safe to re-run: already-downloaded files are skipped (resume).
"""
import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")


class AuthError(Exception):
    pass


def fetch(url, headers, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError(f"HTTP {e.code}") from e
            last = e
            time.sleep(1.5 * (i + 1))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def base_headers(sess):
    return {"PSPDFKit-Platform": "web", "PSPDFKit-Version": sess["ver"],
            "Referer": "https://young.hubscuola.it/", "User-Agent": UA}


def tile_headers(sess):
    h = base_headers(sess)
    h["Accept"] = "image/webp,image/*,*/*"
    h["X-PSPDFKit-Image-Token"] = sess["imgTok"]
    return h


def text_headers(sess):
    h = base_headers(sess)
    h["Accept"] = "application/json,*/*"
    h["X-PSPDFKit-Token"] = sess["textTok"]
    return h


def tile_rects(W, H, tile):
    xs = list(range(0, W, tile))
    ys = list(range(0, H, tile))
    rects = []
    for x in xs:
        for y in ys:
            tw = min(tile, W - x)
            th = min(tile, H - y)
            rects.append((x, y, tw, th))
    return rects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book")
    ap.add_argument("--scale", type=float, default=2.0,
                    help="pixel scale vs PDF points (default 2 -> ~150 dpi)")
    ap.add_argument("--tile", type=int, default=1024,
                    help="tile size in px (max ~1150)")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="only first N pages (0 = all)")
    a = ap.parse_args()

    bdir = OUT / a.book
    sess = json.loads((bdir / "session.json").read_text())
    BASE = sess["base"]

    doc = json.loads(fetch(BASE + "/document.json", base_headers(sess) | {"X-PSPDFKit-Token": sess["docTok"]}))
    (bdir / "document.json").write_text(json.dumps(doc))
    data = doc["data"]
    pages = data["pages"]
    N = data["pageCount"]
    print(f"book {a.book}: {N} pages, title={data.get('title')!r}", flush=True)
    if a.limit:
        N = min(N, a.limit)

    (bdir / "tiles").mkdir(parents=True, exist_ok=True)
    (bdir / "text").mkdir(parents=True, exist_ok=True)

    def work(i):
        pg = pages[i]
        W = max(1, math.ceil(pg["width"] * a.scale))
        H = max(1, math.ceil(pg["height"] * a.scale))
        d = bdir / "tiles" / f"p{i+1:04d}"
        d.mkdir(parents=True, exist_ok=True)
        problems = []
        for x, y, tw, th in tile_rects(W, H, a.tile):
            fp = d / f"tile_{x}_{y}_{tw}_{th}.img"
            if fp.exists() and fp.stat().st_size > 100:
                continue
            url = f"{BASE}/page-{i}-dimensions-{W}-{H}-tile-{x}-{y}-{tw}-{th}"
            try:
                fp.write_bytes(fetch(url, tile_headers(sess)))
            except AuthError as e:
                raise SystemExit("token expired -> re-run capture_session.py") from e
            except Exception as e:
                problems.append(f"tile {x},{y}: {e}")
        tf = bdir / "text" / f"p{i+1:04d}.json"
        if not (tf.exists() and tf.stat().st_size > 2):
            for v in (1, 2, 3):
                try:
                    tf.write_bytes(fetch(f"{BASE}/page-{i}-text-content-v-{v}", text_headers(sess)))
                    break
                except Exception:
                    continue
            else:
                problems.append("text")
        return i + 1, problems

    fails = {}
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(work, i): i for i in range(N)}
        for f in as_completed(futs):
            page, problems = f.result()
            done += 1
            if problems:
                fails[page] = problems
            if done % 25 == 0 or done == N:
                print(f"  {done}/{N} done, failing: {len(fails)}", flush=True)

    if fails:
        (bdir / "failures.json").write_text(json.dumps(fails, indent=1))
        print("FAILURES:", sorted(fails)[:30])
    else:
        print("ALL OK")


if __name__ == "__main__":
    main()
