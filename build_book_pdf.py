#!/usr/bin/env python3
"""Build a selectable-text PDF from downloaded tiles + text layers.

Usage:
    python3 build_book_pdf.py <bookId> [--quality 86] [--out NAME.pdf]

Reads  output/<bookId>/document.json, tiles/, text/
Writes output/<bookId>.pdf
"""
import argparse
import io
import json
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
FONT = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
pdfmetrics.registerFont(TTFont("Body", FONT))


def load_page_sizes(bdir, doc):
    pages = doc["data"]["pages"]
    return [(float(p["width"]), float(p["height"])) for p in pages]


def tile_files(d):
    return sorted(d.glob("tile_*.img"))


def stitch(d, W, H):
    cv = Image.new("RGB", (W, H), "white")
    for fp in tile_files(d):
        # name: tile_<x>_<y>_<w>_<h>.img
        _, x, y, w, h = fp.stem.split("_")
        im = Image.open(fp).convert("RGB")
        if im.size != (int(w), int(h)):
            im = im.resize((int(w), int(h)))
        cv.paste(im, (int(x), int(y)))
    return cv


def extract_text(obj, out):
    el = obj.get("element")
    if isinstance(el, dict) and el.get("type") == "text":
        t = el.get("text")
        if t and t.strip():
            out.append((obj.get("bbox"), t))
    for k in ("children", "nodes"):
        for c in obj.get(k, []) or []:
            extract_text(c, out)


def draw_text_layer(c, tf, PT_W, PT_H):
    if not tf.exists():
        return
    items = []
    for r in json.loads(tf.read_text()):
        extract_text(r, items)
    for bbox, text in items:
        if not bbox or len(bbox) < 4:
            continue
        text = text.replace("\n", " ").strip()
        if not text:
            continue
        x, top, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
        if w <= 0.3 or h <= 0.3:
            continue
        try:
            natural = pdfmetrics.stringWidth(text, "Body", h)
        except Exception:
            continue
        if natural <= 0:
            continue
        scale = min(max(100.0 * w / natural, 15.0), 500.0)
        baseline = PT_H - top - h * 0.80
        t = c.beginText()
        t.setTextRenderMode(3)
        t.setFont("Body", h)
        t.setTextOrigin(x, baseline)
        t.setHorizScale(scale)
        try:
            t.textOut(text)
            c.drawText(t)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book")
    ap.add_argument("--quality", type=int, default=86)
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0, help="only first N pages")
    a = ap.parse_args()

    bdir = OUT / a.book
    doc = json.loads((bdir / "document.json").read_text())
    sizes = load_page_sizes(bdir, doc)
    if a.limit:
        sizes = sizes[:a.limit]
    title = doc["data"].get("title") or f"Book {a.book}"
    pdf_path = Path(a.out) if a.out else (OUT / f"{a.book}.pdf")

    if not FONT:
        raise SystemExit("no usable Unicode font found")

    c = canvas.Canvas(str(pdf_path), pagesize=(sizes[0][0], sizes[0][1]))
    c.setTitle(title)
    n = len(sizes)
    for i, (w, h) in enumerate(sizes):
        d = bdir / "tiles" / f"p{i+1:04d}"
        W = max(1, round(w * 2))
        H = max(1, round(h * 2))
        # derive pixel size from tiles so scale is exact
        tiles = tile_files(d)
        if not tiles:
            c.showPage()
            continue
        max_x = max(int(fp.stem.split("_")[1]) + int(fp.stem.split("_")[3]) for fp in tiles)
        max_y = max(int(fp.stem.split("_")[2]) + int(fp.stem.split("_")[4]) for fp in tiles)
        img = stitch(d, max_x, max_y)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=a.quality, optimize=True)
        buf.seek(0)
        c.setPageSize((w, h))
        c.drawImage(ImageReader(buf), 0, 0, w, h, preserveAspectRatio=False)
        draw_text_layer(c, bdir / "text" / f"p{i+1:04d}.json", w, h)
        c.showPage()
        if (i + 1) % 25 == 0 or i + 1 == n:
            print(f"  {i+1}/{n} pages built", flush=True)
    c.save()
    print("PDF:", pdf_path, pdf_path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
