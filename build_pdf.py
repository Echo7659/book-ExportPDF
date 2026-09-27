"""Build the full selectable-text PDF from downloaded tiles + text layers."""
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

OUT = Path("/Users/lee/GolandProjects/pdf-export/output")
TILES = OUT / "full" / "tiles"
TEXT = OUT / "full" / "text"
PDF_PATH = OUT / "full-600pages.pdf"
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

PAGE_W, PAGE_H = 1191, 1645
PT_W, PT_H = 595.2756, 822.0473

COLS = [(0, 512), (507, 512), (1014, 177)]
ROWS = [(0, 512), (507, 512), (1014, 512), (1521, 124)]

pdfmetrics.registerFont(TTFont("Body", FONT))


def stitch(page):
    d = TILES / f"p{page:04d}"
    cv = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    for x, w in COLS:
        for y, h in ROWS:
            fp = d / f"tile_{x}_{y}_{w}_{h}.webp"
            img = Image.open(fp).convert("RGB")
            if img.size != (w, h):
                img = img.resize((w, h))
            cv.paste(img, (x, y))
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


def draw_text_layer(c, page):
    fp = TEXT / f"p{page:04d}.json"
    if not fp.exists():
        return 0
    items = []
    for r in json.loads(fp.read_text()):
        extract_text(r, items)
    n = 0
    for bbox, text in items:
        if not bbox or len(bbox) < 4:
            continue
        text = text.replace("\n", " ").strip()
        if not text:
            continue
        x, top, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
        if w <= 0.3 or h <= 0.3:
            continue
        fs = h
        try:
            natural = pdfmetrics.stringWidth(text, "Body", fs)
        except Exception:
            continue
        if natural <= 0:
            continue
        scale = min(max(100.0 * w / natural, 15.0), 500.0)
        baseline = PT_H - top - h * 0.80
        t = c.beginText()
        t.setTextRenderMode(3)
        t.setFont("Body", fs)
        t.setTextOrigin(x, baseline)
        t.setHorizScale(scale)
        try:
            t.textOut(text)
            c.drawText(t)
            n += 1
        except Exception:
            pass
    return n


def build(pages):
    c = canvas.Canvas(str(PDF_PATH), pagesize=(PT_W, PT_H))
    c.setTitle("Libro digitale")
    for i, page in enumerate(pages, 1):
        img = stitch(page)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=86, optimize=True, progressive=False)
        buf.seek(0)
        c.drawImage(ImageReader(buf), 0, 0, PT_W, PT_H, preserveAspectRatio=False)
        draw_text_layer(c, page)
        c.showPage()
        if i % 25 == 0 or i == len(pages):
            print(f"{i}/{len(pages)} pages built", flush=True)
    c.save()
    print("PDF:", PDF_PATH, PDF_PATH.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        build(list(range(1, 6)))
    else:
        build(list(range(1, 601)))
