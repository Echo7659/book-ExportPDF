"""Stitch page tiles and overlay the viewer's text layer as invisible selectable text."""
import io
import json
import re
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

TILE_DIR = Path("/Users/lee/GolandProjects/pdf-export/output/pages-5-tiles")
TEXT_DIR = Path("/Users/lee/GolandProjects/pdf-export/output/text")
OUT_PDF = Path("/Users/lee/GolandProjects/pdf-export/output/preview-5pages-selectable.pdf")
PAGE_W, PAGE_H = 1191, 1645
PT_W, PT_H = 595.28, 822.05
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

pdfmetrics.registerFont(TTFont("Body", FONT))


def stitch(n: int) -> Image.Image:
    canvas_im = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    tiles = sorted(TILE_DIR.glob(f"p{n}_tile_*.webp"))
    if len(tiles) != 12:
        raise SystemExit(f"page {n}: expected 12 tiles, got {len(tiles)}")
    for t in tiles:
        m = re.search(r"tile_(\d+)_(\d+)_(\d+)_(\d+)\.webp$", t.name)
        x, y, w, h = map(int, m.groups())
        img = Image.open(t).convert("RGB")
        if img.size != (w, h):
            img = img.resize((w, h))
        canvas_im.paste(img, (x, y))
    return canvas_im


def draw_page(c: canvas.Canvas, n: int) -> None:
    image = stitch(n)
buf = io.BytesIO()
image.save(buf, format="PNG")
buf.seek(0)
c.drawImage(buf.getvalue(), 0, 0, PT_W, PT_H, preserveAspectRatio=False, mask="auto")

    data = json.loads((TEXT_DIR / f"p{n}.json").read_text())
    for item in data["items"]:
        text = item["t"].replace("\n", "").strip()
        if not text:
            continue
        x = item["x"] * PT_W
        y_top = item["y"] * PT_H
        w = max(item["w"] * PT_W, 0.5)
        h = max(item["h"] * PT_H, 0.5)
        font_size = h * 0.82
        natural = pdfmetrics.stringWidth(text, "Body", font_size)
        scale = 100.0 * w / natural if natural > 0 else 100.0
        scale = min(max(scale, 20.0), 400.0)
        baseline = PT_H - y_top - h * 0.82
        text_obj = c.beginText()
        text_obj.setTextRenderMode(3)
        text_obj.setFont("Body", font_size)
        text_obj.setTextOrigin(x, baseline)
        text_obj.setHorizScale(scale)
        text_obj.textOut(text)
        c.drawText(text_obj)
    c.showPage()


pdf = canvas.Canvas(str(OUT_PDF), pagesize=(PT_W, PT_H))
for n in range(1, 6):
    draw_page(pdf, n)
    print(f"page {n} written")
pdf.save()

reader = PdfReader(str(OUT_PDF))
print(f"pages={len(reader.pages)} bytes={OUT_PDF.stat().st_size}")
sample = reader.pages[1].extract_text() or ""
print(sample[:400])
