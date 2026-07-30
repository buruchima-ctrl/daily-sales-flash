# -*- coding: utf-8 -*-
"""Render-surface invariants — BR-5, NFR-2, NFR-5.

The rule these tests exist for is BR-5: *four surfaces, one compute, numbers
that cannot differ.* The only way to hold that is to check the rendered bytes,
because the failure mode is not a wrong number — it is a renderer that helpfully
re-formats one. So the sampled days below are checked string-by-string: every
display value the four surfaces share must appear verbatim in all four.

The rest guards the delivery constraints that break silently: email weight and
external assets (a remote image is a tracking pixel to a mail scanner, and a
stripped one is a hole in the layout), the charset declaration the lease review
caught missing, and link integrity across the generated archive.

Run: python3 -m unittest tests.test_render
"""

import datetime as dt
import html
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seed                                          # noqa: E402
from flash import archive, catalog, compute           # noqa: E402
from flash import render_email, render_print, render_site, render_slack  # noqa: E402
from flash.calendar import NRFCalendar                # noqa: E402

D = dt.date

# Three sampled days, chosen because they are the ones most likely to drift:
# the late-poster/maturation day, the restated day, and the holiday day.
SAMPLED = (D(2026, 7, 23), D(2026, 7, 20), D(2026, 7, 4))

EMAIL_MAX_BYTES = 100 * 1024
EXTERNAL_REF = re.compile(r'(?:src|href)\s*=\s*["\']?\s*(?:https?:)?//', re.I)
ANY_URL = re.compile(r'https?://', re.I)
LINK = re.compile(r'(?:href|src)="([^"]+)"')
CHARSET = '<meta charset="utf-8">'


def common_values(obj):
    """Every display string all four surfaces are obliged to print.

    Deliberately the intersection, not the union: the print one-pager drops the
    window date ranges and the e-commerce table to stay on one page (PRD §8),
    and asserting on a number a surface never claimed to show would be testing
    the test. What is left is the set a reader could hold side by side.
    """
    d = obj["display"]
    out = [("net sales", d["net_sales"]),
           ("comp %", d["comp_pct"]),
           ("comp LY date", d["comp_ly_date"]),
           ("plan attainment", d["plan_attainment"]),
           ("plan gap", d["plan_gap"]),
           ("focus headline gap", d["focus"]["headline_gap"]),
           ("focus remainder", d["focus"]["remainder"]),
           ("transactions", d["transactions"]),
           ("transactions comp", d["txn_comp"]),
           ("units", d["units"]),
           ("AOV", d["aov"]),
           ("UPT", d["upt"]),
           ("AUR", d["aur"])]
    for key in ("WTD", "MTD", "YTD"):
        w = d["windows"][key]
        out += [("%s net sales" % key, w["net_sales"]),
                ("%s comp" % key, w["comp_pct"]),
                ("%s plan" % key, w["plan_attainment"])]
    for r in d["slices"]["region"]:
        out += [("region %s net sales" % r["key"], r["net_sales"]),
                ("region %s comp" % r["key"], r["comp_pct"]),
                ("region %s plan" % r["key"], r["plan_attainment"])]
    for r in d["slices"]["channel"]:
        out += [("channel %s net sales" % r["key"], r["net_sales"]),
                ("channel %s comp" % r["key"], r["comp_pct"])]
    for i, e in enumerate(d["focus"]["entries"]):
        out.append(("focus entry %d line" % (i + 1), e["line"]))
        for j, r in enumerate(e["receipts"]):
            out.append(("focus entry %d receipt %d" % (i + 1, j + 1), r))
    return [(name, v) for name, v in out if v and v != "n/a"]


class RenderCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, cls.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        cls.conn, _ = seed.build(cls.path)
        cls.cal = NRFCalendar()
        cls.da = catalog.DataAccess(cls.conn, cls.cal)
        cls.da_settled = catalog.DataAccess(cls.conn, cls.cal, ecom_basis="settled")
        cls.objs = {d: compute.build_flash(cls.da, d) for d in SAMPLED}
        cls.surfaces = {d: cls.render_all(obj) for d, obj in cls.objs.items()}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        os.remove(cls.path)

    @staticmethod
    def render_all(obj):
        return {
            "email": render_email.render(obj),
            "slack": render_slack.render(obj),
            "print": render_print.render(obj),
            "site": render_site.render_day(obj, {"stem": obj["date"]}),
        }

    # -- BR-5: the four surfaces cannot disagree ---------------------------

    def test_all_four_surfaces_agree_on_every_shared_number(self):
        for day in SAMPLED:
            obj = self.objs[day]
            rendered = {k: html.unescape(v) for k, v in self.surfaces[day].items()}
            missing = []
            for name, value in common_values(obj):
                for surface, text in sorted(rendered.items()):
                    if value not in text:
                        missing.append((surface, name, value))
            self.assertFalse(
                missing,
                "BR-5 broken on %s: %d displayed value(s) do not appear "
                "verbatim on every surface. One compute, four faces — a "
                "renderer that re-formats a number has forked the flash.\n"
                "Offending (surface, field, expected string):\n  %s\n"
                "Fix: render obj['display'][...] instead of formatting in the "
                "renderer (flash/fmt.py is the only formatting home)."
                % (day, len(missing),
                   "\n  ".join(repr(m) for m in missing[:12])))

    def test_catalog_metrics_7_to_10_reach_every_surface(self):
        """PRD §5 #7-#10 — transactions vs LY, AOV, UPT, AUR.

        Named separately from the BR-5 sweep because these four were computed,
        carried on the object and documented in the formula key while appearing
        on no surface at all. A metric the catalog computes and no reader ever
        sees is a metric that is quietly wrong forever.
        """
        for day in SAMPLED:
            d = self.objs[day]["display"]
            wanted = [("transactions", d["transactions"]), ("units", d["units"]),
                      ("AOV", d["aov"]), ("UPT", d["upt"]), ("AUR", d["aur"]),
                      ("transactions comp", d["txn_comp"])]
            for surface, text in sorted(self.surfaces[day].items()):
                text = html.unescape(text)
                for label, value in wanted:
                    self.assertIn(
                        value, text,
                        "PRD §5 metric %s (%s) is missing from the %s surface "
                        "on %s. It is on obj['display'] and named in the "
                        "formula key, so the reader is promised a row that is "
                        "not there. Fix: render it in flash/render_%s.py — the "
                        "basket block."
                        % (label, value, surface, day,
                           "site" if surface == "site" else surface))

    def test_subject_line_is_carried_by_the_email(self):
        for day in SAMPLED:
            obj = self.objs[day]
            self.assertIn("<!-- Subject: %s" % html.escape(obj["subject"]),
                          self.surfaces[day]["email"],
                          "PRD §8: the email must carry its subject line.")
            self.assertEqual(render_email.subject_line(obj), obj["subject"])

    def test_disclosures_reach_every_html_surface(self):
        for day in SAMPLED:
            obj = self.objs[day]
            for rule in {x["rule"] for x in obj["disclosures"]}:
                for surface in ("email", "print", "site"):
                    self.assertIn(
                        rule, self.surfaces[day][surface],
                        "%s is disclosed in the computed object for %s but "
                        "never reaches the %s surface. A caveat that does not "
                        "render is a caveat that does not exist."
                        % (rule, day, surface))

    # -- NFR-5: email weight and external assets ---------------------------

    def test_email_is_under_100kb_with_no_external_assets(self):
        for day in SAMPLED:
            body = self.surfaces[day]["email"]
            size = len(body.encode("utf-8"))
            self.assertLessEqual(
                size, EMAIL_MAX_BYTES,
                "PRD §8: the email for %s is %.1fKB, over the 100KB budget. "
                "Gmail clips at ~102KB and the clipped part is usually the "
                "disclosures." % (day, size / 1024.0))
            hits = EXTERNAL_REF.findall(body) + ANY_URL.findall(body)
            self.assertFalse(
                hits, "NFR-5 broken: the email for %s references something "
                      "outside itself (%r). No remote images, no hosted CSS — "
                      "the flash must render with images off." % (day, hits[:5]))
            for forbidden, why in (("<style", "Gmail strips <style> on forward"),
                                   ("<script", "mail clients do not run JS"),
                                   ("<link", "no external stylesheets"),
                                   ("url(", "no remote or data assets in CSS")):
                self.assertNotIn(
                    forbidden, body.lower(),
                    "PRD §8: the email for %s contains %r — %s. Every "
                    "declaration must be a style attribute."
                    % (day, forbidden, why))

    def test_email_declares_inline_css_and_a_single_column(self):
        body = self.surfaces[SAMPLED[0]]["email"]
        self.assertIn('style="', body)
        self.assertIn("max-width:600px", body,
                      "PRD §8: the email card must cap its width so a 375px "
                      "phone viewport cannot scroll horizontally.")
        self.assertIn('name="viewport"', body)

    # -- NFR-5: charset everywhere -----------------------------------------

    def test_every_html_surface_declares_utf8(self):
        for day in SAMPLED:
            for surface in ("email", "print", "site"):
                self.assertIn(
                    CHARSET, self.surfaces[day][surface],
                    "NFR-5: the %s surface for %s does not declare "
                    "<meta charset=\"utf-8\">. The flash prints é, — and −; "
                    "without the declaration they arrive as mojibake."
                    % (surface, day))

    def test_non_ascii_content_survives_a_utf8_round_trip(self):
        body = self.surfaces[SAMPLED[0]]["print"]
        self.assertIn("Lumi", body)
        self.assertEqual(body, body.encode("utf-8").decode("utf-8"))

    # -- NFR-2: rendering is deterministic ---------------------------------

    def test_rendering_is_byte_identical_on_a_second_pass(self):
        for day in SAMPLED:
            again = self.render_all(compute.build_flash(self.da, day))
            for surface, text in again.items():
                self.assertEqual(
                    text, self.surfaces[day][surface],
                    "NFR-2: the %s surface for %s changed between two renders "
                    "of the same day. Something in the path is reading the "
                    "clock, iterating a set, or depending on dict insertion "
                    "order." % (surface, day))


class SiteCase(unittest.TestCase):
    """The archive as a built tree: navigation, versions, and the BR-4 view."""

    @classmethod
    def setUpClass(cls):
        fd, cls.dbpath = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        cls.conn, _ = seed.build(cls.dbpath)
        cal = NRFCalendar()
        cls.da = catalog.DataAccess(cls.conn, cal)
        cls.da_settled = catalog.DataAccess(cls.conn, cal, ecom_basis="settled")
        cls.root = tempfile.mkdtemp(prefix="flash-site-")
        cls.site = os.path.join(cls.root, "site")
        cls.days = cls._build()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        os.remove(cls.dbpath)
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def _build(cls):
        """A miniature of what `run_flash.py --all` does: a short archive with
        the restated day and the maturation day inside it."""
        window = [D(2026, 7, 18) + dt.timedelta(days=i) for i in range(6)]
        archive.clear(cls.conn)
        for day in window:
            obj = compute.build_flash(cls.da, day)
            archive.write_version(cls.conn, obj)
            for name, ext, text in (
                    ("email", "html", render_email.render(obj)),
                    ("print", "html", render_print.render(obj)),
                    ("slack", "txt", render_slack.render(obj))):
                render_site.write(os.path.join(cls.root, name,
                                               "%s.%s" % (day.isoformat(), ext)), text)
        rd = seed.RESTATE_DAY
        v1 = archive.versions(cls.conn, rd)[0]["obj"]
        draft = compute.build_flash(cls.da_settled, rd, version=2)
        reason = archive.restatement_reason(v1, draft)
        v2 = compute.build_flash(cls.da_settled, rd, version=2, reason=reason)
        archive.restate(cls.conn, v2, reason)
        for name, ext, text in (("email", "html", render_email.render(v2)),
                                ("print", "html", render_print.render(v2)),
                                ("slack", "txt", render_slack.render(v2))):
            render_site.write(os.path.join(cls.root, name, "%s-v2.%s"
                                           % (rd.isoformat(), ext)), text)
        mday = seed.ECOM_MATURATION_DAY
        settled = {mday.isoformat(): compute.build_flash(cls.da_settled, mday)}
        days = [{"date": d.isoformat(),
                 "versions": archive.versions(cls.conn, d),
                 "settled": settled.get(d.isoformat())} for d in window]
        cls.storylines = [
            {"n": 5, "rule": "BR-4", "title": "E-commerce maturation",
             "note": "demand vs settled", "where": "the settled view",
             "href": "ecom/%s-settled.html" % mday.isoformat()}]
        render_site.build_site(cls.site, days, storylines=cls.storylines)
        return days

    def _html_files(self):
        for dirpath, _dirs, files in os.walk(self.site):
            for f in sorted(files):
                if f.endswith(".html"):
                    yield os.path.join(dirpath, f)

    def test_every_generated_html_file_declares_utf8(self):
        files = list(self._html_files())
        self.assertGreater(len(files), 5)
        for path in files:
            with open(path, encoding="utf-8") as fh:
                head = fh.read(400)
            self.assertIn(
                CHARSET, head,
                "NFR-5: %s does not declare <meta charset=\"utf-8\"> in its "
                "head. Every generated HTML file must (the lease review's "
                "deploy note — do not repeat that defect)."
                % os.path.relpath(path, self.site))

    def test_the_site_makes_no_external_requests(self):
        for path in list(self._html_files()) + [
                os.path.join(self.site, "assets", "site.css")]:
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            hits = ANY_URL.findall(body) + EXTERNAL_REF.findall(body)
            self.assertFalse(
                hits, "NFR-5: %s reaches outside the archive (%r). The site "
                      "must render offline from a copied folder."
                      % (os.path.relpath(path, self.site), hits[:5]))

    def test_every_internal_link_resolves_to_a_file(self):
        broken = []
        for path in self._html_files():
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            for href in LINK.findall(body):
                if href.startswith("#") or ":" in href:
                    continue
                if not href.endswith((".html", ".css", ".txt")):
                    continue           # e.g. /today, which only app.py serves
                target = os.path.normpath(
                    os.path.join(os.path.dirname(path), href))
                if not os.path.isfile(target):
                    broken.append((os.path.relpath(path, self.site), href))
        self.assertFalse(
            broken,
            "The archive has %d dead link(s) — a web archive whose navigation "
            "breaks is not an archive:\n  %s"
            % (len(broken), "\n  ".join(repr(b) for b in broken[:12])))

    def test_restated_day_publishes_both_versions_and_the_reason(self):
        rd = seed.RESTATE_DAY.isoformat()
        v1p = os.path.join(self.site, "day", "%s.html" % rd)
        v2p = os.path.join(self.site, "day", "%s-v2.html" % rd)
        hist = os.path.join(self.site, "day", "%s-history.html" % rd)
        for p in (v1p, v2p, hist):
            self.assertTrue(os.path.isfile(p),
                            "BR-7: %s is missing. A restated day must publish "
                            "version 1, version 2 and a history page."
                            % os.path.basename(p))
        versions = archive.versions(self.conn, seed.RESTATE_DAY)
        with open(v1p, encoding="utf-8") as fh:
            v1_body = fh.read()
        with open(hist, encoding="utf-8") as fh:
            hist_body = html.unescape(fh.read())
        self.assertIn(versions[0]["obj"]["display"]["net_sales"], v1_body)
        self.assertNotIn(
            versions[1]["obj"]["display"]["comp_pct"] + "<", v1_body,
            "BR-7: version 1's page is showing version 2's comp. Version 1 is "
            "immutable and must render exactly what was sent.")
        self.assertIn(versions[1]["reason"], hist_body,
                      "BR-7: the restatement reason must be rendered.")
        for v in versions:
            self.assertIn(v["obj"]["display"]["net_sales"], hist_body,
                          "BR-7: the history page must show every version.")

    def test_maturation_day_publishes_a_settled_view_beside_the_flash(self):
        mday = seed.ECOM_MATURATION_DAY.isoformat()
        page = os.path.join(self.site, "ecom", "%s-settled.html" % mday)
        self.assertTrue(os.path.isfile(page),
                        "BR-4: no settled view was published for %s." % mday)
        with open(page, encoding="utf-8") as fh:
            body = html.unescape(fh.read())
        flash = archive.versions(self.conn, seed.ECOM_MATURATION_DAY)[0]["obj"]
        settled = compute.build_flash(self.da_settled, seed.ECOM_MATURATION_DAY)
        self.assertIn(flash["display"]["comp_pct"], body)
        self.assertIn(settled["display"]["comp_pct"], body)
        self.assertNotEqual(flash["display"]["comp_pct"],
                            settled["display"]["comp_pct"])
        self.assertIn("version 1", body.lower(),
                      "BR-4: the settled view must say the sent flash is "
                      "unchanged, and which version that is.")
        with open(os.path.join(self.site, "day", "%s.html" % mday),
                  encoding="utf-8") as fh:
            day_body = fh.read()
        self.assertIn("%s-settled.html" % mday, day_body,
                      "BR-4: the day page must link to its settled view — both "
                      "must be visible, not one findable only by URL.")

    def test_index_navigates_by_fiscal_week_not_calendar_month(self):
        with open(os.path.join(self.site, "index.html"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("Fiscal week", body)
        self.assertRegex(body, r"FY20\d\d W\d\d",
                         "PRD §8: the index must navigate by fiscal week.")
        self.assertIn("period", body.lower())
        for entry in self.days:
            self.assertIn('href="day/%s.html"' % entry["date"], body,
                          "Every archived day must be reachable from the index.")
        for head in ("Sun", "Mon", "Sat"):
            self.assertIn(">%s</th>" % head, body)

    def test_site_build_is_byte_identical_on_a_second_pass(self):
        other = os.path.join(self.root, "site2")
        render_site.build_site(other, self.days, storylines=self.storylines)
        for path in self._html_files():
            rel = os.path.relpath(path, self.site)
            twin = os.path.join(other, rel)
            if not os.path.isfile(twin):
                continue
            with open(path, "rb") as a, open(twin, "rb") as b:
                self.assertEqual(a.read(), b.read(),
                                 "NFR-2: %s differs between two builds." % rel)


if __name__ == "__main__":
    unittest.main()
