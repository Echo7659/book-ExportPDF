#!/usr/bin/env python3
"""Capture bSmart (books.bsmart.it) Nutrient/PSPDFKit tokens.

Usage:
    python3 bsmart_capture.py "<viewer_url>" [ego_space_id_or_name]

Example:
    python3 bsmart_capture.py "https://books.bsmart.it/books/20315?page=0" 0

Prereq: ego-browser profile is logged into bSmart and the book tab is open.
Writes output/<bookId>/session.json with base/ver/docTok/textTok/imgTok.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"


def book_id_from(url: str) -> str:
    m = re.search(r"/books/(\d+)", url)
    if not m:
        raise SystemExit(f"cannot find book id in url: {url}")
    return m.group(1)


JS_TEMPLATE = r"""
const fs = await import("node:fs");
const sid = "%(space)s";
const task = /^\d+$/.test(sid) ? await taskSpace(Number(sid)) : await taskSpace(sid);

let page = null;
for (const t of await task.tabs()) {
  if ((t.url || "").includes("books.bsmart.it")) {
    page = t.label ? task.page(t.label) : await task.adopt(t.page);
    break;
  }
}
if (!page) page = task.page("p1");

await page.cdp("Network.enable", { maxTotalBufferSize: 300000000, maxResourceBufferSize: 50000000 });
await page.cdp("Network.setCacheDisabled", { cacheDisabled: true });
await page.goto("%(viewer)s");
await page.waitForTimeout(6000);

const sess = {};
const done = () => sess.base && sess.docTok && sess.textTok && sess.imgTok;
for (let i = 0; i < 10 && !done(); i++) {
  for (const e of await page.events()) {
    if (e.method !== "Network.requestWillBeSent") continue;
    const u = e.params?.request?.url || "";
    if (u.indexOf("pspdfkit.bsmart.it") < 0) continue;
    const h = e.params.request.headers || {};
    sess.ver = sess.ver || h["PSPDFKit-Version"];
    const m = u.indexOf("/h/");
    if (m > 0 && !sess.base) sess.base = u.slice(0, u.indexOf("/", m + 3));
    if (u.includes("document.json") && h["X-PSPDFKit-Token"]) sess.docTok = h["X-PSPDFKit-Token"];
    if (u.includes("text-content") && h["X-PSPDFKit-Token"]) sess.textTok = h["X-PSPDFKit-Token"];
    if (u.includes("-dimensions-") && h["X-PSPDFKit-Image-Token"]) sess.imgTok = h["X-PSPDFKit-Image-Token"];
  }
  if (!done()) await page.waitForTimeout(4000);
}
sess.finalUrl = await page.url();
fs.writeFileSync("%(outfile)s", JSON.stringify(sess));
console.log("WROTE_BSMART_SESSION");
"""


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    viewer = sys.argv[1]
    space = sys.argv[2] if len(sys.argv) > 2 else "0"
    book = book_id_from(viewer)
    d = OUT / book
    d.mkdir(parents=True, exist_ok=True)
    outfile = d / "session.json"
    if outfile.exists():
        outfile.unlink()
    js = JS_TEMPLATE % {"space": space, "viewer": viewer, "outfile": str(outfile), "book": book}
    r = subprocess.run(["ego-browser", "nodejs", "-e", js], capture_output=True, text=True)
    if not outfile.exists():
        print(r.stdout[-1500:])
        print(r.stderr[-1500:], file=sys.stderr)
        raise SystemExit("failed to capture bSmart session")
    sess = json.loads(outfile.read_text())
    missing = [k for k in ("base", "ver", "docTok", "textTok", "imgTok") if not sess.get(k)]
    if missing:
        raise SystemExit(f"missing {missing}; current url {sess.get('finalUrl')}\n"
                         "=> open the book in a bSmart tab and log in.")
    print(f"saved {outfile}")
    print(f"  base: {sess['base']}")


if __name__ == "__main__":
    main()
