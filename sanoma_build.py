#!/usr/bin/env python3
"""Render Sanoma page HTML to PDF via the ego browser (batched + merged).

Usage:
    python3 sanoma_build.py <product_id> [ego_space_name] [--batch 40]

Reads  output/sanoma/<product_id>/pNNNN.html + sizes.json + session.json
Writes output/sanoma/<product_id>.pdf

A large book is split into batches; each batch is written into one browser
page (via document.write) and printed to PDF, then all batch PDFs are merged.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "sanoma"

BATCH_TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@page {{ size: {w}px {h}px; margin: 0; }}
html,body {{ margin:0; padding:0; }}
.pagewrap {{ width:{w}px; height:{h}px; position:relative; overflow:hidden;
              page-break-after: always; break-after: page; }}
.t {{ color: transparent !important; }}
</style></head><body>
{pages}
</body></html>"""

JS_TEMPLATE = r"""
const fs = await import("node:fs");
const manifest = JSON.parse(fs.readFileSync("%(manifest)s", "utf8"));
const sid = "%(space)s";
const task = /^\d+$/.test(sid) ? await taskSpace(Number(sid)) : await taskSpace(sid);
const pg = await task.newPage();
await pg.goto("%(container)s");
await pg.waitForTimeout(2500);
for (const item of manifest) {
  const html = fs.readFileSync(item.html, "utf8");
  let ok = false;
  for (let attempt = 0; attempt < 2 && !ok; attempt++) {
    try {
      await pg.evaluate((h) => { document.open(); document.write(h); document.close(); }, html);
      await pg.waitForTimeout(%(wait)s);
      const res = await pg.cdp("Page.printToPDF", { printBackground: true, preferCSSPageSize: true });
      fs.writeFileSync(item.out, Buffer.from(res.data, "base64"));
      console.log("BATCH " + item.out + " " + Buffer.from(res.data, "base64").length);
      ok = true;
    } catch (e) {
      console.log("RETRY " + item.out + " : " + e.message.slice(0, 80));
      try { await pg.reload(); await pg.waitForTimeout(2500); } catch (e2) {}
    }
  }
  if (!ok) console.log("FAILED " + item.out);
}
try { await pg.close(); } catch (e) {}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("space", nargs="?", default="sanoma-download")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--wait", type=int, default=10000, help="ms to wait per batch")
    ap.add_argument("--keep", action="store_true", help="keep batch files")
    a = ap.parse_args()

    d = OUT / a.product
    sess = json.loads((d / "session.json").read_text())
    sizes = json.loads((d / "sizes.json").read_text())
    w, h = sizes[0]
    container = "https://npmitaly-pro-apidistribucion.sanoma.it/viewers/lm60/online/index.html"

    pages = sorted(d.glob("p[0-9][0-9][0-9][0-9].html"))
    if not pages:
        raise SystemExit("no page html found; run sanoma_fetch.py first")

    manifest = []
    for i in range(0, len(pages), a.batch):
        batch = pages[i:i + a.batch]
        parts = [f'<div class="pagewrap">{p.read_text()}</div>' for p in batch]
        bhtml = d / f"_batch_{i // a.batch:03d}.html"
        bhtml.write_text(BATCH_TEMPLATE.format(w=w, h=h, pages="\n".join(parts)))
        bpdf = d / f"_batch_{i // a.batch:03d}.pdf"
        if bpdf.exists():
            bpdf.unlink()
        manifest.append({"html": str(bhtml), "out": str(bpdf)})

    nbatch = len(manifest)
    print(f"{len(pages)} pages -> {nbatch} batches", flush=True)
    manifest_file = d / "_manifest.json"
    manifest_file.write_text(json.dumps(manifest))

    js = JS_TEMPLATE % {"manifest": str(manifest_file), "space": a.space,
                        "wait": a.wait, "container": container}
    r = subprocess.run(["ego-browser", "nodejs", "-e", js], capture_output=True, text=True)
    if r.stdout:
        for ln in r.stdout.splitlines():
            if ln.startswith(("BATCH", "RETRY", "FAILED")):
                print("  " + ln, flush=True)
    missing = [m["out"] for m in manifest if not Path(m["out"]).exists()
               or Path(m["out"]).stat().st_size < 1000]
    if missing:
        print(r.stderr[-1500:], file=sys.stderr)
        raise SystemExit(f"missing/failed batches: {len(missing)}")

    writer = PdfWriter()
    for m in manifest:
        for pg in PdfReader(m["out"]).pages:
            writer.add_page(pg)
    out = OUT / f"{a.product}.pdf"
    with open(out, "wb") as fh:
        writer.write(fh)
    print(f"PDF: {out} ({out.stat().st_size // 1024} KB, {len(writer.pages)} pages)")

    if not a.keep:
        for m in manifest:
            Path(m["html"]).unlink(missing_ok=True)
            Path(m["out"]).unlink(missing_ok=True)
        manifest_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
