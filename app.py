# -*- coding: utf-8 -*-
"""Archive server — stdlib `http.server`, nothing installed (NFR-1).

Two jobs:

  1. **Serve the generated archive** in `render/site/`. Static files, no
     framework, no build step. The day pages link sideways to the email, print
     and Slack artifacts with `../../email/…`; a browser clamps those leading
     `..` segments at the document root, so the server aliases `/email/`,
     `/print/` and `/slack/` onto the sibling folders under `render/`. The same
     files then work identically opened straight off the disk with `file://`.

  2. **Generate on demand.** `/today` computes the flash live from `flash.db`
     and renders it without touching the archive — the page you would receive
     tomorrow morning, built from the data as it stands now.

"Today" is **2026-07-24** and the latest complete day is **2026-07-23**, both
fixed constants (`flash/archive.py`). Nothing in this server calls `now()`:
NFR-2 is not only about rebuild diffs, it is what lets a reviewer open this
demo in a year and see the same numbers the README describes.

Run:  python3 app.py            # http://127.0.0.1:8765/
      python3 app.py --port 9000 --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import posixpath
import sqlite3
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from flash import archive, catalog, compute                      # noqa: E402
from flash import render_email, render_print, render_site, render_slack  # noqa: E402
from flash.calendar import NRFCalendar                           # noqa: E402

RENDER_DIR = os.path.join(HERE, "render")
SITE_DIR = os.path.join(RENDER_DIR, "site")
DB_PATH = os.path.join(HERE, "flash.db")

# Sibling render surfaces, reachable from the site's relative links.
ALIASES = {"/email/": os.path.join(RENDER_DIR, "email"),
           "/print/": os.path.join(RENDER_DIR, "print"),
           "/slack/": os.path.join(RENDER_DIR, "slack")}

TODAY = archive.TODAY                      # 2026-07-24, fixed (NFR-2)
LATEST_COMPLETE = archive.LATEST_COMPLETE   # 2026-07-23


def build_today(surface: str = "site"):
    """Generate the latest complete day's flash on demand.

    Deliberately does NOT write to `flash_archive`: BR-7 says a sent flash is
    immutable, and a browser refresh is not a send. This endpoint is a preview
    of the object; `run_flash.py --all` is the thing that publishes it.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        da = catalog.DataAccess(conn, NRFCalendar())
        obj = compute.build_flash(da, LATEST_COMPLETE)
    finally:
        conn.close()

    if surface == "email":
        return "text/html; charset=utf-8", render_email.render(obj)
    if surface == "print":
        return "text/html; charset=utf-8", render_print.render(obj)
    if surface == "slack":
        return "text/plain; charset=utf-8", render_slack.render(obj)
    if surface == "json":
        return "application/json; charset=utf-8", archive.serialize(obj)
    prev = dt.date.fromisoformat(obj["date"]) - dt.timedelta(days=1)
    nav = {
        "stem": obj["date"],
        # Links are written for a document at the server root: `day/…` reaches
        # the archived pages, `../index.html` clamps to `/index.html`.
        "index_href": "index.html",
        "prev_href": "day/%s.html" % prev.isoformat(),
        "prev_label": "the day before",
        "next_href": "day/%s.html" % obj["date"],
        "next_label": "this day in the archive",
        "live_note": (
            "Generated on demand just now, live from flash.db — not read from "
            "the archive. This is the flash that would be sent on the morning "
            "of %s for the latest complete day, %s. It is not written to "
            "flash_archive: a refresh is not a send (BR-7)."
            % (TODAY.isoformat(), obj["date"])),
    }
    return "text/html; charset=utf-8", render_site.render_day(obj, nav)


# -- the server -------------------------------------------------------------

GENERATED = {
    "/today": "site",
    "/today.html": "site",
    "/today.email.html": "email",
    "/today.print.html": "print",
    "/today.txt": "slack",
    "/today.json": "json",
}


class FlashHandler(SimpleHTTPRequestHandler):
    """Static archive + the generate-on-demand routes."""

    server_version = "DailySalesFlash/1.0"

    def do_GET(self):                                   # noqa: N802
        path = urlparse(self.path).path
        if path in GENERATED:
            return self._generated(GENERATED[path])
        # "/" falls through: translate_path maps it to render/site, and the
        # base handler serves index.html for a directory.
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_HEAD(self):                                  # noqa: N802
        if urlparse(self.path).path in GENERATED:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return None
        return SimpleHTTPRequestHandler.do_HEAD(self)

    def _generated(self, surface):
        try:
            ctype, body = build_today(surface)
        except Exception as exc:                        # noqa: BLE001
            self._error(500, "Could not generate today's flash", exc)
            return None
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)
        return None

    def _error(self, code, title, exc):
        body = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<title>%s</title></head><body><h1>%s</h1><pre>%s: %s</pre>"
                "<p>Has the archive been generated? Run "
                "<code>python3 seed.py &amp;&amp; python3 run_flash.py --all</code>"
                ".</p></body></html>" % (title, title, type(exc).__name__, exc))
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def translate_path(self, path):
        """Map URLs to files: the site is the root, the sibling surfaces are
        aliased so the archive's `../../email/…` links resolve after a browser
        clamps them to `/email/…`."""
        clean = posixpath.normpath(unquote(urlparse(path).path))
        for prefix, target in ALIASES.items():
            if clean.startswith(prefix):
                rel = clean[len(prefix):]
                safe = [p for p in rel.split("/") if p not in ("", ".", "..")]
                return os.path.join(target, *safe)
        safe = [p for p in clean.split("/") if p not in ("", ".", "..")]
        return os.path.join(SITE_DIR, *safe)

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s %s\n" % (self.address_string(), fmt % args))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Serve the Daily Sales Flash archive")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)

    if not os.path.isfile(os.path.join(SITE_DIR, "index.html")):
        print("No archive found at %s.\n"
              "Generate it first:  python3 seed.py && python3 run_flash.py --all"
              % SITE_DIR)
        return 2
    if not os.path.isfile(DB_PATH):
        print("No flash.db found. Run: python3 seed.py")
        return 2

    httpd = ThreadingHTTPServer((args.host, args.port), FlashHandler)
    base = "http://%s:%d" % (args.host, args.port)
    print("Daily Sales Flash archive — %s" % base)
    print("  %s/                    archive index (fiscal-week navigation)" % base)
    print("  %s/today               generate the latest complete day on demand" % base)
    print("  %s/today.email.html    the same day as the email surface" % base)
    print("  %s/today.print.html    the print one-pager" % base)
    print("  %s/today.txt           the Slack block" % base)
    print("  %s/today.json          the computed object itself" % base)
    print("Demo clock is fixed: today = %s, latest complete day = %s."
          % (TODAY.isoformat(), LATEST_COMPLETE.isoformat()))
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
