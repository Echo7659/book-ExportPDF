"""Download all tiles + text layers for the 600-page book."""
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT = Path("/Users/lee/GolandProjects/pdf-export/output/full")
TILES = OUT / "tiles"
TEXT = OUT / "text"
TILES.mkdir(parents=True, exist_ok=True)
TEXT.mkdir(parents=True, exist_ok=True)

sess = json.loads(Path("/Users/lee/GolandProjects/pdf-export/output/session.json").read_text())
BASE = sess["base"]
VER = sess["ver"]
DOC_TOK = sess["docTok"]
TEXT_TOK = sess["textTok"]
IMG_TOK = sess["imgTok"]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")

COLS = [(0, 512), (507, 512), (1014, 177)]
ROWS = [(0, 512), (507, 512), (1014, 512), (1521, 124)]
N = 600


def fetch(url, headers, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def tile_headers():
    return {"PSPDFKit-Platform": "web", "PSPDFKit-Version": VER,
            "Referer": "https://young.hubscuola.it/", "User-Agent": UA,
            "Accept": "image/webp,*/*", "X-PSPDFKit-Image-Token": IMG_TOK}


def text_headers():
    return {"PSPDFKit-Platform": "web", "PSPDFKit-Version": VER,
            "Referer": "https://young.hubscuola.it/", "User-Agent": UA,
            "Accept": "application/json,*/*", "X-PSPDFKit-Token": TEXT_TOK}


def work(page):
    idx = page - 1
    d = TILES / f"p{page:04d}"
    d.mkdir(parents=True, exist_ok=True)
    problems = []
    for x, w in COLS:
        for y, h in ROWS:
            fp = d / f"tile_{x}_{y}_{w}_{h}.webp"
            if fp.exists() and fp.stat().st_size > 100:
                continue
            url = f"{BASE}/page-{idx}-dimensions-1191-1645-tile-{x}-{y}-{w}-{h}"
            try:
                fp.write_bytes(fetch(url, tile_headers()))
            except Exception as e:
                problems.append(f"tile {x},{y}: {e}")
    tf = TEXT / f"p{page:04d}.json"
    if not (tf.exists() and tf.stat().st_size > 2):
        ok = False
        for v in (1, 2, 3):
            try:
                body = fetch(f"{BASE}/page-{idx}-text-content-v-{v}", text_headers())
                tf.write_bytes(body)
                ok = True
                break
            except Exception:
                continue
        if not ok:
            problems.append("text")
    return page, problems


def main():
    pages = [p for p in range(1, N + 1)]
    done = 0
    fails = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(work, p): p for p in pages}
        for f in as_completed(futs):
            page, problems = f.result()
            done += 1
            if problems:
                fails[page] = problems
            if done % 25 == 0 or done == len(pages):
                print(f"{done}/{len(pages)} done, failing pages: {len(fails)}", flush=True)
    if fails:
        Path(OUT / "failures.json").write_text(json.dumps(fails, indent=1))
        print("FAILURES:", sorted(fails)[:20])
    else:
        print("ALL OK")


if __name__ == "__main__":
    main()
