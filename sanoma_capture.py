#!/usr/bin/env python3
"""Capture Sanoma / LibroMedia 6.0 session (CloudFront cookies + asset base).

Usage:
    python3 sanoma_capture.py "<viewer_url>" [space_id_or_name]

Prereq: ego-browser profile is logged into the Sanoma/My Place book, and the
book is open in a tab of that space (the viewer URL contains
ebook.sanoma.it/open-book).

Writes output/sanoma/<product>/session.json:
    { "base": ".../assets/book/pages", "product": "1118992", "cookies": [...] }
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "sanoma"

JS_TEMPLATE = r"""
const fs = await import("node:fs");
const sid = "%(space)s";

async function findSanomaPage() {
  // 1) scan every task space for an open Sanoma tab
  for (const sp of await listTaskSpaces()) {
    try {
      const t = await takeOverTaskSpace(sp.id);
      for (const tab of await t.tabs()) {
        if ((tab.url || "").includes("sanoma.it")) {
          return { task: t, page: tab.label ? t.page(tab.label) : await t.adopt(tab.page) };
        }
      }
    } catch (e) { /* space busy / user-owned */ }
  }
  // 2) fall back to the requested space, navigate to the viewer
  const t = /^\d+$/.test(sid) ? await taskSpace(Number(sid)) : await taskSpace(sid);
  return { task: t, page: null };
}

let { task, page } = await findSanomaPage();
if (!page) page = task.page("p1");
try { await page.bringToFront(); } catch (e) {}

await page.cdp("Network.enable", { maxTotalBufferSize: 300000000, maxResourceBufferSize: 50000000 });
await page.cdp("Network.setCacheDisabled", { cacheDisabled: true });

async function scan() {
  let base = null, product = null;
  for (const e of await page.events()) {
    if (e.method !== "Network.requestWillBeSent") continue;
    const u = e.params?.request?.url || "";
    const m = u.match(/^(https?:\/\/[^/]+)\/product\/(\d+)\/[^/]+\/assets\/book\/pages/);
    if (m) { base = m[0]; product = m[2]; break; }
  }
  return { base, product };
}

let found = await scan();
if (!found.base && !(await page.url()).includes("sanoma.it")) {
  await page.goto("%(viewer)s");
  await page.waitForTimeout(15000);
  found = await scan();
}
if (!found.base) {
  await page.reload();
  await page.waitForTimeout(15000);
  found = await scan();
}
const ck = await page.cdp("Network.getAllCookies", {});
const out = { base: found.base, product: found.product,
              cookies: (ck.cookies || []).filter(c => /sanoma\.it/.test(c.domain)) };
fs.writeFileSync("%(outfile)s", JSON.stringify(out));
console.log("WROTE_SANOMA_SESSION");
"""


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    viewer = sys.argv[1]
    space = sys.argv[2] if len(sys.argv) > 2 else "sanoma-download"
    tmp = ROOT / "output" / "_sanoma_session.tmp.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if tmp.exists():
        tmp.unlink()
    js = JS_TEMPLATE % {"space": space, "viewer": viewer, "outfile": str(tmp)}
    r = subprocess.run(["ego-browser", "nodejs", "-e", js], capture_output=True, text=True)
    if not tmp.exists():
        print(r.stdout[-1500:])
        print(r.stderr[-1500:], file=sys.stderr)
        raise SystemExit("failed to capture Sanoma session")
    data = json.loads(tmp.read_text())
    tmp.unlink()
    if not data.get("base") or not data.get("product"):
        raise SystemExit(
            "could not find a book asset request.\n"
            "=> open a book in the Sanoma viewer (tab url contains "
            "ebook.sanoma.it/open-book) and make sure you are logged in.")
    d = OUT / data["product"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "session.json").write_text(json.dumps(data, indent=1))
    print(f"saved {d / 'session.json'}")
    print(f"  product: {data['product']}")
    print(f"  base: {data['base']}")
    print(f"  cookies: {len(data['cookies'])}")


if __name__ == "__main__":
    main()
