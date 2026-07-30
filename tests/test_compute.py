# -*- coding: utf-8 -*-
"""Compute-layer invariants — the business rules, asserted on real seeded days.

These are the tests that would catch a regression a reader would notice: a
focus panel that no longer adds up, a holiday comp that quietly reverts to the
calendar date, a late poster silently counted as zero, a restated flash that
overwrote the one that was actually sent.

Every failure message names the rule, the storyline and the offending figures
(NFR-4) — a test that only says "AssertionError: False is not true" costs more
time than the bug.

Run: python3 -m unittest tests.test_compute
"""

import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seed                                          # noqa: E402
from flash import archive, catalog, compute           # noqa: E402
from flash.calendar import NRFCalendar                # noqa: E402

D = dt.date

LATEST = seed.LATEST_COMPLETE          # 2026-07-23
JULY4 = D(2026, 7, 4)
SAMPLE_DAYS = (D(2026, 7, 23), D(2026, 7, 20), D(2026, 7, 4),
               D(2026, 6, 30), D(2026, 6, 6))


class _Fixture(unittest.TestCase):
    """One seeded database, shared by the cases below. Carries no tests itself
    so the subclasses do not re-run each other's."""

    @classmethod
    def setUpClass(cls):
        fd, cls.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        cls.conn, _ = seed.build(cls.path)
        cls.cal = NRFCalendar()
        cls.da = catalog.DataAccess(cls.conn, cls.cal)
        cls.da_settled = catalog.DataAccess(cls.conn, cls.cal, ecom_basis="settled")
        cls.objs = {d: compute.build_flash(cls.da, d) for d in SAMPLE_DAYS}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        os.remove(cls.path)


class ComputeCase(_Fixture):
    """BR-1 and BR-6 — the comparison and its decomposition."""

    # -- BR-6: the focus panel reconciles to the cent ----------------------

    def test_focus_reconciles_to_the_cent_every_archived_day(self):
        for day in archive.archive_dates():
            obj = self.objs.get(day) or compute.build_flash(self.da, day)
            f = obj["focus"]
            named = sum(e["delta"] for e in f["entries"])
            total = round(named + f["remainder"], 2)
            self.assertAlmostEqual(
                total, f["headline_gap"], places=2,
                msg="BR-6 broken on %s: named contributions %.2f + all other "
                    "%.2f = %.2f, but the headline comp gap is %.2f. The "
                    "entries are %r. Fix: an entry's `covers` set in "
                    "flash/focus.py overlaps another's, so an entity is "
                    "counted twice or not at all."
                    % (day, named, f["remainder"], total, f["headline_gap"],
                       [(e["kind"], e["key"], e["delta"]) for e in f["entries"]]))

    def test_headline_gap_is_the_comp_pair_difference(self):
        for day, obj in self.objs.items():
            f, c = obj["focus"], obj["comp"]
            self.assertAlmostEqual(
                f["headline_gap"], round(c["ty"] - c["ly"], 2), places=2,
                msg="BR-6/BR-5 broken on %s: the focus panel decomposes a gap "
                    "(%.2f) that is not the headline's TY %.2f − LY %.2f. The "
                    "panel must decompose the comparison the reader was shown."
                    % (day, f["headline_gap"], c["ty"], c["ly"]))

    def test_focus_covers_are_disjoint(self):
        for day, obj in self.objs.items():
            seen = set()
            for e in obj["focus"]["entries"]:
                overlap = seen & set(e["covers"])
                self.assertFalse(
                    overlap,
                    "BR-6 broken on %s: focus entry %r claims entities already "
                    "explained by an earlier entry: %s. Double-counted entities "
                    "make the panel add up only by accident."
                    % (day, e["key"], sorted(overlap)))
                seen |= set(e["covers"])

    # -- BR-1: holiday-adjusted comp leads, raw is still stated ------------

    def test_july4_holiday_alignment_leads_and_states_the_raw_figure(self):
        obj = self.objs[JULY4]
        c = obj["comp"]
        self.assertTrue(
            c["override_in_effect"],
            "STORYLINE 1 (BR-1) missing: %s carries holiday_code %r but no "
            "holiday override is in effect. The July 4 weekday shift is the "
            "planted storyline; check flash/calendar.ly_holiday_aligned_date."
            % (JULY4, c["holiday_code"]))
        self.assertIsNotNone(c["holiday_aligned"], "BR-1: no holiday-aligned figure")
        self.assertIsNotNone(c["week_aligned"], "BR-1: no week-aligned figure")
        self.assertEqual(
            c["pct"], c["holiday_aligned"]["pct"],
            "BR-1 broken on %s: the leading comp is %r but the holiday-adjusted "
            "figure is %r. The adjusted number must lead."
            % (JULY4, c["pct"], c["holiday_aligned"]["pct"]))
        self.assertNotEqual(
            round(c["holiday_aligned"]["pct"], 4),
            round(c["week_aligned"]["pct"], 4),
            "STORYLINE 1 is invisible on %s: the adjusted comp (%r) and the raw "
            "week-aligned comp (%r) are identical, so a reader cannot see the "
            "holiday shift. Check the seed's JULY_4 multiplier and the LY "
            "holiday date." % (JULY4, c["holiday_aligned"]["pct"],
                               c["week_aligned"]["pct"]))
        self.assertNotEqual(c["holiday_aligned"]["ly_date"],
                            c["week_aligned"]["ly_date"])
        texts = " ".join(x["text"] for x in obj["disclosures"] if x["rule"] == "BR-1")
        self.assertIn("Holiday alignment in effect", texts,
                      "BR-1: the holiday override is not disclosed on %s" % JULY4)
        self.assertIn(obj["display"]["week_aligned_pct"], texts,
                      "BR-1 broken on %s: the raw week-aligned comp %s is not "
                      "stated anywhere in the disclosures. A raw comparison may "
                      "be shown only alongside the aligned one — and the aligned "
                      "one may never be shown alone either."
                      % (JULY4, obj["display"]["week_aligned_pct"]))

    def test_calendar_date_comp_is_carried_but_never_leads(self):
        for day, obj in self.objs.items():
            c = obj["comp"]
            if not c["calendar_date"]:
                continue
            if c["calendar_date"]["ly_date"] == c["ly_date"]:
                continue
            self.assertNotEqual(
                c["basis"], "calendar-date",
                "BR-1 broken on %s: the flash is leading with the same-calendar-"
                "date comparison. That is the spreadsheet's defect, not ours."
                % day)

    def test_ordinary_day_leads_with_the_week_aligned_comp(self):
        obj = self.objs[D(2026, 6, 6)]
        c = obj["comp"]
        self.assertFalse(c["override_in_effect"])
        self.assertEqual(c["basis"], "week-aligned")
        ly, _restated = self.cal.ly_aligned_date(D(2026, 6, 6))
        self.assertEqual(c["ly_date"], ly.isoformat())
        self.assertEqual(D.fromisoformat(c["ly_date"]).weekday(),
                         D(2026, 6, 6).weekday(),
                         "BR-1: the LY counterpart must fall on the same "
                         "weekday as the day being reported.")


class DisclosureCase(_Fixture):
    """BR-2/BR-3/BR-4/BR-7 — the rules that are only real if they are said."""

    # -- BR-3: missing is not zero, and two days escalates -----------------

    def test_late_posters_are_disclosed_and_lb021_escalates(self):
        obj = self.objs[LATEST]
        cm = obj["completeness"]
        self.assertEqual(
            sorted(cm["missing"]), [seed.LATE_ONE, seed.LATE_BOTH],
            "STORYLINE 4 (BR-3) broken on %s: expected %s and %s to be missing, "
            "got %r. Check seed.is_missing."
            % (LATEST, seed.LATE_ONE, seed.LATE_BOTH, cm["missing"]))
        esc = {e["entity_id"]: e for e in cm["escalating"]}
        self.assertIn(
            seed.LATE_BOTH, esc,
            "STORYLINE 4 (BR-3) broken: %s missed %s and %s but is not "
            "escalating. Two consecutive missed days must escalate regardless "
            "of rank (PRD §6.6). Late posters seen: %r"
            % (seed.LATE_BOTH, seed.LATE_DAY_PREV, seed.LATE_DAY,
               [(l["entity_id"], l["consecutive_days"]) for l in cm["late_posters"]]))
        self.assertEqual(esc[seed.LATE_BOTH]["consecutive_days"], 2)
        self.assertNotIn(
            seed.LATE_ONE, esc,
            "BR-3: %s missed one day only and must NOT escalate — escalating "
            "everything is the same as escalating nothing." % seed.LATE_ONE)
        keys = {e["key"] for e in obj["focus"]["escalations"] if e["escalate"]}
        self.assertIn(seed.LATE_BOTH, keys,
                      "PRD §6.6: an escalating store must appear in the focus "
                      "panel regardless of rank.")
        texts = " ".join(x["text"] for x in obj["disclosures"] if x["rule"] == "BR-3")
        self.assertIn("MISSING, not zero", texts)
        self.assertIn("ESCALATION", texts)
        self.assertIn(self.da.entity(seed.LATE_BOTH)["name"], texts)

    def test_missing_stores_are_excluded_not_zero_filled(self):
        obj = self.objs[LATEST]
        cm = obj["completeness"]
        self.assertEqual(cm["expected"] - cm["reported"], len(cm["missing"]))
        rows = self.conn.execute(
            "SELECT COALESCE(SUM(net_sales),0) FROM sales_day WHERE date=?",
            (LATEST.isoformat(),)).fetchone()[0]
        self.assertAlmostEqual(
            obj["headline"]["net_sales"], round(rows, 2), places=2,
            msg="BR-3 broken on %s: the headline (%.2f) is not the sum of the "
                "rows that actually posted (%.2f). A missing store must be "
                "absent from the total, never added in as a zero."
                % (LATEST, obj["headline"]["net_sales"], rows))
        for eid in cm["missing"]:
            self.assertIsNone(
                self.da.sales_row(eid, LATEST),
                "BR-3: %s is reported missing but has a sales row." % eid)

    # -- BR-2: comp-set exclusions, disclosed by name ----------------------

    def test_remodel_store_excluded_from_comp_and_disclosed(self):
        obj = self.objs[LATEST]
        members = set(self.da.comp_set(LATEST))
        self.assertNotIn(
            seed.REMODEL_STORE, members,
            "STORYLINE 3 (BR-2) broken: %s is closed for remodel from %s and "
            "must be out of the comp set on both sides."
            % (seed.REMODEL_STORE, seed.REMODEL_START))
        self.assertIsNone(
            self.da.sales_row(seed.REMODEL_STORE, LATEST),
            "STORYLINE 3: %s is down for remodel and must post nothing."
            % seed.REMODEL_STORE)
        self.assertNotIn(
            seed.REMODEL_STORE, set(self.da.comp_pair(LATEST)["members"]),
            "BR-2: a remodel store must be on neither side of the headline "
            "comp pair.")
        # The LY side of the rule. LB-013's remodel runs forward from
        # 2026-06-15, so no day in the archive has it down LY and up TY. Point
        # the comparison the other way — a 2025 day measured against the
        # remodel window — and the same branch has to fire, because BR-2 says
        # the exclusion applies to BOTH years, not to the reporting year.
        reversed_pair = self.da.comp_set(D(2025, 7, 24),
                                         ly_override=D(2026, 7, 23))
        self.assertNotIn(
            seed.REMODEL_STORE, set(reversed_pair),
            "BR-2 broken: %s is excluded when it is in remodel on the TY side "
            "but not when the remodel falls on the LY side. A comp that drops "
            "a door from one year only is not like-for-like."
            % seed.REMODEL_STORE)
        texts = " ".join(x["text"] for x in obj["disclosures"] if x["rule"] == "BR-2")
        self.assertIn("closed for remodel", texts)
        self.assertIn(seed.REMODEL_STORE, texts,
                      "BR-2: every exclusion must be disclosed by name in the "
                      "footer. Disclosures seen: %r" % texts)

    def test_new_store_out_of_comp_but_inside_the_total(self):
        obj = self.objs[LATEST]
        self.assertNotIn(
            seed.NEW_STORE, set(self.da.comp_set(LATEST)),
            "STORYLINE 6 (BR-2) broken: %s opened %s — fewer than 13 full "
            "fiscal periods — and must not be in comp."
            % (seed.NEW_STORE, self.da.entity(seed.NEW_STORE)["open_date"]))
        row = self.da.sales_row(seed.NEW_STORE, LATEST)
        self.assertIsNotNone(row, "STORYLINE 6: the new store posted no sales, "
                                  "so it cannot demonstrate 'in total, out of comp'.")
        self.assertGreater(
            obj["headline"]["net_sales"], row["net_sales"],
            "BR-2: the new store's sales must be inside total net sales.")
        texts = " ".join(x["text"] for x in obj["disclosures"] if x["rule"] == "BR-2")
        self.assertIn("fewer than 13 full fiscal", texts)
        self.assertIn(seed.NEW_STORE, texts)

    # -- BR-4: demand and shipped are distinct series ----------------------

    def test_ecom_maturation_day_demand_negative_settles_positive(self):
        obj = self.objs[LATEST]
        e = obj["ecom"]
        self.assertLess(
            e["demand_comp_pct"], 0,
            "STORYLINE 5 (BR-4) broken: %s demand comp is %r, expected the "
            "planted −8%%." % (LATEST, e["demand_comp_pct"]))
        self.assertGreater(
            e["shipped_comp_pct"], 0,
            "STORYLINE 5 (BR-4) broken: %s shipped comp is %r, expected the "
            "planted +5%%. The point of the storyline is that the two series "
            "disagree in SIGN." % (LATEST, e["shipped_comp_pct"]))
        self.assertFalse(e["matured"],
                         "BR-4: %s is inside the settle lag and must not be "
                         "presented as matured." % LATEST)
        self.assertEqual(obj["basis"], "demand")
        self.assertIn("demand", obj["display"]["ecom"]["basis"])

    def test_settled_view_differs_and_leaves_the_flash_alone(self):
        flash = self.objs[LATEST]
        settled = compute.build_flash(self.da_settled, LATEST)
        self.assertEqual(settled["version"], flash["version"],
                         "BR-4/BR-7: the settled view is a VIEW, not a new "
                         "version of the sent flash.")
        self.assertNotEqual(
            round(flash["headline"]["comp_pct"], 4),
            round(settled["headline"]["comp_pct"], 4),
            "STORYLINE 5 (BR-4) is invisible: the settled basis produces the "
            "same comp as the demand basis (%r), so the archive's settled view "
            "shows nothing." % flash["headline"]["comp_pct"])
        self.assertEqual(
            flash["headline"]["net_sales"],
            compute.build_flash(self.da, LATEST)["headline"]["net_sales"],
            "BR-7: recomputing the flash after building a settled view changed "
            "the flash. Nothing may mutate shared state.")
        self.assertEqual(settled["basis"], "settled")
        texts = " ".join(x["text"] for x in settled["disclosures"] if x["rule"] == "BR-4")
        self.assertIn("SETTLED", texts)

    # -- BR-7: immutability and restatement --------------------------------

    def test_archive_refuses_to_overwrite_and_restates_as_a_new_version(self):
        day = seed.RESTATE_DAY
        obj = compute.build_flash(self.da, day)
        archive.clear(self.conn)
        archive.write_version(self.conn, obj)
        with self.assertRaises(archive.ImmutabilityError,
                               msg="BR-7: writing the same date+version twice "
                                   "must be refused, not upserted."):
            archive.write_version(self.conn, obj)

        draft = compute.build_flash(self.da_settled, day, version=2)
        reason = archive.restatement_reason(obj, draft)
        v2 = compute.build_flash(self.da_settled, day, version=2, reason=reason)
        archive.restate(self.conn, v2, reason)

        vs = archive.versions(self.conn, day)
        self.assertEqual([v["version"] for v in vs], [1, 2],
                         "BR-7: a restatement appends version 2 and leaves "
                         "version 1 in place.")
        self.assertEqual(
            archive.serialize(vs[0]["obj"]), archive.serialize(obj),
            "BR-7 VIOLATED: version 1 changed when version 2 was written. The "
            "sent flash is immutable; %s's version 1 must be byte-identical to "
            "what was archived." % day)
        self.assertNotEqual(vs[0]["obj"]["headline"]["net_sales"],
                            vs[1]["obj"]["headline"]["net_sales"],
                            "STORYLINE 8: the restatement restates nothing.")
        self.assertTrue(vs[1]["reason"], "BR-7: a restatement needs a reason string.")
        self.assertIn("settled", vs[1]["reason"])
        self.assertIn("E-commerce settled late", vs[1]["obj"]["reason"])
        texts = " ".join(x["text"] for x in vs[1]["obj"]["disclosures"])
        self.assertIn("restatement", texts)
        archive.clear(self.conn)

    def test_gaps_and_reuses_in_the_version_chain_are_refused(self):
        day = D(2026, 6, 6)
        obj = compute.build_flash(self.da, day)
        archive.clear(self.conn)
        archive.write_version(self.conn, obj)
        skipped = compute.build_flash(self.da, day, version=3)
        with self.assertRaises(archive.ImmutabilityError,
                               msg="BR-7: version 3 after version 1 leaves a "
                                   "hole in the audit trail."):
            archive.restate(self.conn, skipped, "skips a version")
        archive.clear(self.conn)

    # -- housekeeping ------------------------------------------------------

    def test_object_is_deterministic(self):
        for day in (LATEST, JULY4):
            a = archive.serialize(compute.build_flash(self.da, day))
            b = archive.serialize(compute.build_flash(self.da, day))
            self.assertEqual(a, b, "NFR-2: two builds of %s differ." % day)
            self.assertEqual(
                compute.build_flash(self.da, day)["as_of"],
                (day + dt.timedelta(days=1)).isoformat(),
                "NFR-2: as_of must be derived from the flash date, never now().")

    def test_narrative_is_at_most_three_sentences(self):
        for day, obj in self.objs.items():
            n = len([s for s in obj["narrative"].split(". ") if s.strip()])
            self.assertLessEqual(
                n, 3, "PRD §11: the narrative for %s runs to %d sentences.\n%s"
                      % (day, n, obj["narrative"]))

    def test_subject_line_convention(self):
        obj = self.objs[LATEST]
        d = obj["display"]
        self.assertEqual(
            obj["subject"],
            "Flash — %s · %s · comp %s · plan %s"
            % (d["date_short"], d["net_sales"], d["comp_pct"], d["plan_attainment"]),
            "PRD §8: the subject line must be built from the same display "
            "strings the body prints, so it cannot disagree with the flash.")


if __name__ == "__main__":
    unittest.main()
