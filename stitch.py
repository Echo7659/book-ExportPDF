"""Stitch PSPDFKit 1191x1645 tiles into full pages and assemble a PDF."""
import re
from pathlib import Path
from PIL import Image

TILE_DIR = Path("/Users/lee/GolandProjects/pdf-export/output/pages-5-tiles")
OUT_PDF = Path("/Users/lee/GolandProjects/pdf-export/output/preview-5pages.pdf")
PAGE_W, PAGE_H = 1191, 1645
PAGES = range(1, 601)

full_pages = []
for n in PAGES:
    canvas = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    tiles = sorted(TILE_DIR.glob(f"p{n}_tile_*.webp"))
    assert len(tiles) == 12, f"page {n}: expected 12 tiles, got {len(tiles)}"
    for t in tiles:
        m = re.search(r"tile_(\d+)_(\d+)_(\d+)_(\d+)\.webp$", t.name)
        x, y, w, h = map(int, m.groups())
        img = Image.open(t).convert("RGB")
        if img.size != (w, h):
            img = img.resize((w, h))
        canvas.paste(img, (x, y))
    full_pages.append(canvas)
    print(f"page {n} stitched")

full_pages[0].save(
    OUT_PDF, save_all=True, append_images=full_pages[1:], resolution=150.0
)
print(f"PDF saved: {OUT_PDF} ({OUT_PDF.stat().st_size / 1024:.0f} KB)")
