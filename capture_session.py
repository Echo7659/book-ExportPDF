#!/usr/bin/env python3
"""Capture HUB Scuola viewer auth tokens into output/<bookId>/session.json.

Usage:
    python3 capture_session.py <viewer_url> [ego_space_name]

Prereq: the ego-browser profile is already logged into HUB Scuola
(log in once in an ego-browser window).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"


def book_id_from(url: str) -> str:
    m = re.search(r"/(?:viewer|i/d)/(\d+)", url)
    if not m:
        raise SystemExit(f"cannot find book id in url: {url}")
    return m.group(1)


JS_TEMPLATE = r"""
const fs = await import("node:fs");
const task = await taskSpace("%(space)s");
const page = task.page("p1");
await page.cdp("Network.enable", { maxTotalBufferSize: 200000000, maxResourceBufferSize: 50000000 });
await page.cdp("Network.setCacheDisabled", { cacheDisabled: true });

async function capture() {
  const out = {};
  const events = await page.events();
  for (const e of events) {
    if (e.method !== "Network.requestWillBeSent") continue;
    const u = e.params?.request?.url || "";
    if (u.indexOf("ms-pdf") < 0) continue;
    const h = e.params.request.headers || {};
    if (!out.base) {
      const m = u.indexOf("/h/");
      if (m > 0) out.base = u.slice(0, u.indexOf("/", m + 3));
    }
    out.ver = out.ver || h["PSPDFKit-Version"];
    if (u.indexOf("-dimensions-") >= 0 && h["X-PSPDFKit-Image-Token"]) out.imgTok = h["X-PSPDFKit-Image-Token"];
    if (u.indexOf("text-content") >= 0 && h["X-PSPDFKit-Token"]) out.textTok = h["X-PSPDFKit-Token"];
    if (u.indexOf("document.json") >= 0 && h["X-PSPDFKit-Token"]) out.docTok = h["X-PSPDFKit-Token"];
  }
  return out;
}

await page.goto("%(viewer)s");
await page.waitForTimeout(12000);
let sess = await capture();
if (!sess.base || !sess.imgTok || !sess.textTok) {
  await page.reload();
  await page.waitForTimeout(12000);
  sess = await capture();
}
sess.finalUrl = await page.url();
fs.writeFileSync("%(outfile)s", JSON.stringify(sess));
console.log("WROTE_SESSION");
"""


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    viewer = sys.argv[1]
    space = sys.argv[2] if len(sys.argv) > 2 else "hub-download"
    book = book_id_from(viewer)
    d = OUT / book
    d.mkdir(parents=True, exist_ok=True)
    outfile = d / "session.json"
    if outfile.exists():
        outfile.unlink()
    js = JS_TEMPLATE % {"space": space, "viewer": viewer, "outfile": str(outfile)}
    r = subprocess.run(["ego-browser", "nodejs", "-e", js],
                       capture_output=True, text=True)
    if not outfile.exists():
        print(r.stdout[-1500:])
        print(r.stderr[-1500:], file=sys.stderr)
        raise SystemExit("failed to capture session")
    sess = json.loads(outfile.read_text())
    missing = [k for k in ("base", "ver", "docTok", "textTok", "imgTok") if not sess.get(k)]
    if missing:
        raise SystemExit(
            f"missing fields {missing}\n"
            f"current url: {sess.get('finalUrl')}\n"
            "=> you are probably NOT logged in. Open an ego-browser window and "
            "log into HUB Scuola, then retry.")
    print(f"saved {outfile}")
    print(f"  base: {sess['base']}")


if __name__ == "__main__":
    main()
