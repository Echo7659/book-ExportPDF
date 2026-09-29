#!/usr/bin/env python3
"""Capture myLIM / Loescher session: JWT token + book metadata + PDF URL.

Usage:
    python3 loescher_capture.py "<viewer_url_or_isbn>" [ego_space]

Prereq: the ego-browser profile is logged into myLIM
(https://mylim.loescher.it). The book itself does not need to be open:
any myLIM tab (or a fresh one) is enough, the token lives in localStorage.

Writes output/loescher/<isbn>/session.json:
    { "isbn": "...", "token": "<jwt>", "title": "...", "author": "...",
      "pages_hint": ..., "size": 40145920, "pdfUrl": "https://s3...?X-Amz-..." }
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "loescher"

API = "https://loeda.loescher.it/mialim2/api/v1/book/"

JS_TEMPLATE = r"""
const fs = await import("node:fs");
const sid = "%(space)s";
const isbn = "%(isbn)s";

async function findLimTab() {
  // 1) scan every task space for an open myLIM tab (reuse the user's login)
  for (const sp of await listTaskSpaces()) {
    try {
      const t = await takeOverTaskSpace(sp.id);
      for (const tab of await t.tabs()) {
        if ((tab.url || "").includes("mylim.loescher.it")) {
          return { task: t, page: tab.label ? t.page(tab.label) : await t.adopt(tab.page) };
        }
      }
    } catch (e) { /* space busy / user-owned */ }
  }
  // 2) otherwise open the reader in the requested space
  const t = /^\d+$/.test(sid) ? await taskSpace(Number(sid)) : await taskSpace(sid);
  return { task: t, page: null };
}

let { task, page } = await findLimTab();
if (!page) page = task.page("p1");
try { await page.bringToFront(); } catch (e) {}
if (!(await page.url()).includes("mylim.loescher.it")) {
  await page.goto("https://mylim.loescher.it/#!/reader/" + isbn);
  await page.waitForTimeout(8000);
}

const data = await page.evaluate(async (args) => {
  const { isbn, api } = args;
  const tok = localStorage.getItem("token");
  if (!tok) return { token: null };
  const h = { "Authorization": "JWT " + tok };
  const out = { token: tok, status: {} };
  const r1 = await fetch(api + "sommari/" + isbn + "/", { headers: h });
  out.status.sommari = r1.status;
  if (r1.ok) out.sommari = await r1.json();
  const r2 = await fetch(api + "pdf/" + isbn + "/", { headers: h });
  out.status.pdf = r2.status;
  if (r2.ok) out.pdfUrl = (await r2.json()).url;
  return out;
}, { isbn: isbn, api: "https://loeda.loescher.it/mialim2/api/v1/book/" });

fs.writeFileSync("%(outfile)s", JSON.stringify({
  isbn: isbn,
  token: data.token,
  pdfUrl: data.pdfUrl || null,
  status: data.status || {},
  opera: (data.sommari || {}).opera || null,
  sezioni: (data.sommari || {}).sezioni || null,
}));
console.log("WROTE_LIM_SESSION");
"""


def isbn_from(value: str) -> str:
    """Accept a myLIM reader url (…/#!/reader/9788858335604) or a bare ISBN."""
    v = value.replace("-", "").replace(" ", "")
    m = re.search(r"(?<!\d)97[89]\d{10}(?!\d)", v)             # ISBN-13
    if m:
        return m.group(0)
    m = re.search(r"(?<!\d)\d{9}[\dXx](?!\d)", v)              # ISBN-10
    if m:
        return m.group(0)
    raise SystemExit(f"cannot find an ISBN in: {value}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    isbn = isbn_from(sys.argv[1])
    space = sys.argv[2] if len(sys.argv) > 2 else "mylim-download"

    d = OUT / isbn
    d.mkdir(parents=True, exist_ok=True)
    outfile = d / "session.json"
    if outfile.exists():
        outfile.unlink()

    js = JS_TEMPLATE % {"space": space, "isbn": isbn, "outfile": str(outfile)}
    r = subprocess.run(["ego-browser", "nodejs", "-e", js],
                       capture_output=True, text=True)
    if not outfile.exists():
        print(r.stdout[-1500:])
        print(r.stderr[-1500:], file=sys.stderr)
        raise SystemExit("failed to capture myLIM session")

    sess = json.loads(outfile.read_text())
    if not sess.get("token"):
        raise SystemExit(
            "no token in localStorage\n"
            "=> you are probably NOT logged in. Open an ego-browser window, "
            "log into https://mylim.loescher.it, then retry.")
    if not sess.get("pdfUrl"):
        raise SystemExit(
            f"API refused the PDF url (status={sess.get('status')})\n"
            "=> token expired or the book is not in your library. "
            "Re-login on myLIM and retry.")
    if not sess.get("opera"):
        raise SystemExit(f"could not read book metadata (status={sess.get('status')})")

    op = sess["opera"]
    print(f"saved {outfile}")
    print(f"  title:  {op.get('nome')}")
    print(f"  author: {op.get('autore')}")
    print(f"  size:   {op.get('dimensione_pdf')} bytes")
    print(f"  pdf:    {sess['pdfUrl'].split('?')[0]}")


if __name__ == "__main__":
    main()