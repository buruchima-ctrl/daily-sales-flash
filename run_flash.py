# -*- coding: utf-8 -*-
"""CLI entry point for the Daily Sales Flash.

  --date YYYY-MM-DD    Render one day to all four surfaces. Defaults to the
                       latest complete day (2026-07-23 — from the data, never
                       now()). If the day is already in the archive it is
                       rendered FROM the archive (BR-7: the site shows what was
                       sent, not a fresh recompute).
  --all                Regenerate everything: the 60-day archive ending
                       2026-07-23, all four surfaces, and the flash_archive
                       rows including the planted restatement (NFR-3: < 30s).
  --check              Build the DB, assert every storyline, run the whole test
                       suite (calendar, catalog, compute, render) and verify a
                       deterministic rebuild. Zero manual steps.

Determinism (NFR-2): nothing here reads the wall clock. Dates come from
`flash/archive.py`'s fixed anchors and timestamps from the flash's own `as_of`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import shutil
import sqlite3
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import seed                                          # noqa: E402
from flash import archive, catalog, compute           # noqa: E402
from flash import render_email, render_print, render_site, render_slack  # noqa: E402
from flash.calendar import NRFCalendar                # noqa: E402

D = dt.date
RENDER_DIR = os.path.join(HERE, "render")
SITE_DIR = os.path.join(RENDER_DIR, "site")
DB_PATH = os.path.join(HERE, "flash.db")


# -- the storyline index (PRD §7; the README and the site share this list) ---

def storyline_index():
    """One list, two consumers: the archive's index page and README.md. If the
    two ever disagreed about where a storyline is visible, the README would be
    the thing that rots — so neither owns it."""
    return [
        {"n": 1, "rule": "BR-1", "title": "Holiday shift — July 4",
         "note": "Raw week-aligned comp and holiday-aligned comp differ "
                 "visibly; the adjusted figure leads and both are stated, "
                 "alongside the same-calendar-date comparison the old "
                 "spreadsheet printed.",
         "where": "day/2026-07-04.html — the gold banner and the disclosures",
         "href": "day/2026-07-04.html"},
        {"n": 2, "rule": "BR-6", "title": "Soft Southeast region",
         "note": "LB-009 and LB-010 have run at x0.78 since 2026-07-10. The "
                 "focus panel rolls the region up and names the two doors "
                 "inside it; the trailing-14-day table shows the run.",
         "where": "day/2026-07-23.html — focus panel and trailing-14-day table",
         "href": "day/2026-07-23.html"},
        {"n": 3, "rule": "BR-2", "title": "Remodel closure — LB-013",
         "note": "Lakeview Arcade went down for remodel on 2026-06-15 and has "
                 "posted nothing since. It is out of comp on both sides of the "
                 "comparison and the exclusion is disclosed by name.",
         "where": "day/2026-07-23.html — disclosures, the BR-2 remodel line",
         "href": "day/2026-07-23.html"},
        {"n": 4, "rule": "BR-3", "title": "Late posters, one escalating",
         "note": "LB-021 missed 07-22 and 07-23 and escalates; LB-005 missed "
                 "07-23 only. Neither is zero-filled: the totals are "
                 "reported-store figures and the banner says so.",
         "where": "day/2026-07-23.html — red completeness banner + escalation",
         "href": "day/2026-07-23.html"},
        {"n": 5, "rule": "BR-4", "title": "E-commerce maturation",
         "note": "Demand read -8.0% on the send morning; the shipped series "
                 "settled at +5.0%. The flash is unchanged and the settled "
                 "view sits beside it at its own URL.",
         "where": "ecom/2026-07-23-settled.html — settled vs flash, side by side",
         "href": "ecom/2026-07-23-settled.html"},
        {"n": 6, "rule": "BR-2", "title": "New store — LB-025",
         "note": "Opened 2025-08-01, fewer than 13 full fiscal periods of "
                 "trading. In total net sales, out of comp, disclosed.",
         "where": "day/2026-07-23.html — disclosures, the BR-2 immaturity line",
         "href": "day/2026-07-23.html"},
        {"n": 7, "rule": "PRD 6.2", "title": "Bright spot — LB-022",
         "note": "Pacific Heights Court (West) has run at x1.18 since "
                 "2026-07-17 and takes the panel's single favourable slot.",
         "where": "day/2026-07-23.html — the up-arrow line in the focus panel",
         "href": "day/2026-07-23.html"},
        {"n": 8, "rule": "BR-7", "title": "Restatement — version 2",
         "note": "2026-07-20 was re-issued on the settled basis with a reason "
                 "string. Version 1 is preserved byte-for-byte at its own URL; "
                 "the history page shows both.",
         "where": "day/2026-07-20-history.html — both versions and the reason",
         "href": "day/2026-07-20-history.html"},
    ]


# -- surfaces ---------------------------------------------------------------

def _db(rebuild_if_missing: bool = True):
    if not os.path.isfile(DB_PATH):
        if not rebuild_if_missing:
            raise SystemExit("flash.db is missing. Run: python3 seed.py")
        print("flash.db not found — building it from the seed first ...")
        conn, _ = seed.build(DB_PATH)
        return conn
    return sqlite3.connect(DB_PATH)


def _write_surfaces(obj, stem: str):
    """Email, Slack and print for one flash object. The web archive is built
    once at the end, from the archive table, so it renders what was sent."""
    out = [
        render_site.write(os.path.join(RENDER_DIR, "email", "%s.html" % stem),
                          render_email.render(obj)),
        render_site.write(os.path.join(RENDER_DIR, "slack", "%s.txt" % stem),
                          render_slack.render(obj)),
        render_site.write(os.path.join(RENDER_DIR, "print", "%s.html" % stem),
                          render_print.render(obj)),
    ]
    return out


def _reset_render():
    """A full regeneration starts from an empty tree. Rendering over the top of
    an old run leaves orphans behind, and an archive with a stale page in it is
    exactly the kind of quiet inconsistency this product exists to remove."""
    for name in ("email", "slack", "print", "site"):
        path = os.path.join(RENDER_DIR, name)
        if os.path.isdir(path):
            shutil.rmtree(path)


def _archive_days(conn, settled_views=None):
    """Read the archive back out as the site's input (BR-7)."""
    settled_views = settled_views or {}
    rows = conn.execute(
        "SELECT DISTINCT date FROM flash_archive ORDER BY date").fetchall()
    out = []
    for (iso,) in rows:
        day = D.fromisoformat(iso)
        out.append({"date": iso,
                    "versions": archive.versions(conn, day),
                    "settled": settled_views.get(iso)})
    return out


def _build_site(conn, settled_views=None):
    days = _archive_days(conn, settled_views)
    return render_site.build_site(SITE_DIR, days, storylines=storyline_index(),
                                  today=archive.TODAY.isoformat())


# -- --all ------------------------------------------------------------------

def cmd_all() -> int:
    t0 = time.time()
    conn = _db()
    cal = NRFCalendar()
    da = catalog.DataAccess(conn, cal)
    da_settled = catalog.DataAccess(conn, cal, ecom_basis="settled")

    dates = archive.archive_dates()
    print("[1/4] Regenerating %d days, %s .. %s"
          % (len(dates), dates[0], dates[-1]))
    _reset_render()
    archive.clear(conn)

    for day in dates:
        obj = compute.build_flash(da, day)
        archive.write_version(conn, obj)
        _write_surfaces(obj, day.isoformat())
    print("      %d flashes computed, archived and rendered to email/slack/print"
          % len(dates))

    print("[2/4] Issuing the planted restatement (BR-7, storyline 8) ...")
    rd = archive.RESTATE_DATE
    v1 = archive.versions(conn, rd)[0]["obj"]
    draft = compute.build_flash(da_settled, rd, version=2)
    reason = archive.restatement_reason(v1, draft)
    v2 = compute.build_flash(da_settled, rd, version=2, reason=reason)
    archive.restate(conn, v2, reason)
    _write_surfaces(v2, "%s-v2" % rd.isoformat())
    print("      %s version 2 written; version 1 untouched (%s -> %s)"
          % (rd, v1["display"]["net_sales"], v2["display"]["net_sales"]))

    print("[3/4] Computing the settled view for the maturation day (BR-4) ...")
    mday = seed.ECOM_MATURATION_DAY
    settled_views = {mday.isoformat(): compute.build_flash(da_settled, mday)}
    print("      %s: flash %s (demand) vs settled view %s (shipped)"
          % (mday,
             archive.versions(conn, mday)[0]["obj"]["display"]["comp_pct"],
             settled_views[mday.isoformat()]["display"]["comp_pct"]))

    conn.commit()
    print("[4/4] Rendering the web archive ...")
    paths = _build_site(conn, settled_views)
    conn.close()

    files = _count_files()
    print("      %d site files (index + day pages + history + settled view)"
          % len(paths))
    elapsed = time.time() - t0
    print("\nDone in %.2fs — %d files under render/ (NFR-3 budget: 30s)."
          % (elapsed, files))
    print("Browse it:  python3 app.py   then open http://127.0.0.1:8765/")
    if elapsed > 30:
        print("NFR-3 FAILED: full regeneration took %.1fs, budget is 30s." % elapsed)
        return 1
    return 0


def _count_files() -> int:
    n = 0
    for _root, _dirs, files in os.walk(RENDER_DIR):
        n += len(files)
    return n


# -- --date -----------------------------------------------------------------

def cmd_date(iso: str) -> int:
    day = archive.LATEST_COMPLETE if not iso else D.fromisoformat(iso)
    conn = _db()
    cal = NRFCalendar()
    da = catalog.DataAccess(conn, cal)

    existing = archive.versions(conn, day)
    if existing:
        print("%s is already in the archive (%d version%s) — rendering what was "
              "sent, not a recompute (BR-7)."
              % (day, len(existing), "" if len(existing) == 1 else "s"))
        objs = [(v["obj"], day.isoformat() if v["version"] == 1
                 else "%s-v%d" % (day.isoformat(), v["version"]))
                for v in existing]
    else:
        obj = compute.build_flash(da, day)
        archive.write_version(conn, obj)
        conn.commit()
        print("%s was not in the archive — computed and archived as version 1."
              % day)
        objs = [(obj, day.isoformat())]

    written = []
    for obj, stem in objs:
        written += _write_surfaces(obj, stem)
        print("  %s  net %s · comp %s · plan %s"
              % (obj["display"]["date_short"], obj["display"]["net_sales"],
                 obj["display"]["comp_pct"], obj["display"]["plan_attainment"]))
        print("  subject: %s" % obj["subject"])

    mday = seed.ECOM_MATURATION_DAY
    settled_views = {}
    if archive.versions(conn, mday):
        da_settled = catalog.DataAccess(conn, cal, ecom_basis="settled")
        settled_views[mday.isoformat()] = compute.build_flash(da_settled, mday)
    written += _build_site(conn, settled_views)
    conn.close()

    for p in written[:3]:
        print("  wrote %s" % os.path.relpath(p, HERE))
    print("  wrote render/site/day/%s.html (+ index and %d other site files)"
          % (day.isoformat(), len(written) - 4))
    return 0


# -- --check ----------------------------------------------------------------

def cmd_check() -> int:
    print("[1/4] Building flash.db from schema + seed ...")
    conn, entities = seed.build()
    cal = NRFCalendar()

    print("[2/4] Asserting planted storylines manifest in the data ...")
    seed.assert_storylines(conn, cal)
    conn.close()
    print("      ok — 7 data-level storyline assertions passed")

    print("[3/4] Running the test suite (calendar, catalog, compute, render) ...")
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(HERE, "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        print("CHECK FAILED: test suite did not pass")
        return 1

    print("[4/4] Verifying deterministic rebuild (NFR-2) ...")
    if not _deterministic():
        print("CHECK FAILED: rebuild was not byte-identical")
        return 1
    print("      ok — rebuild is byte-identical")
    print("\nALL CHECKS PASSED.")
    return 0


def _deterministic() -> bool:
    def content_hash(path):
        seed.build(path)
        c = sqlite3.connect(path)
        lines = []
        for t in ("stores", "calendar", "sales_day", "plan_day"):
            for row in c.execute("SELECT * FROM %s ORDER BY 1,2" % t):
                lines.append(repr(row))
        c.close()
        os.remove(path)
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    return content_hash(os.path.join(HERE, "_det1.db")) == \
        content_hash(os.path.join(HERE, "_det2.db"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Daily Sales Flash")
    ap.add_argument("--check", action="store_true",
                    help="build, assert storylines, run tests, verify determinism")
    ap.add_argument("--date", nargs="?", const="", default=None,
                    help="flash date YYYY-MM-DD (default: the latest complete day)")
    ap.add_argument("--all", action="store_true",
                    help="regenerate the 60-day archive and all four surfaces")
    args = ap.parse_args(argv)

    if args.check:
        return cmd_check()
    if args.all:
        return cmd_all()
    if args.date is not None:
        return cmd_date(args.date)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
