# -*- coding: utf-8 -*-
"""Catalog tests — formulas, comp-set rules, and BR-6 reconciliation.

Builds a fresh in-memory-ish DB via seed.build() into a temp file so the tests
are hermetic. Run: python3 -m unittest tests.test_catalog
"""
import datetime as dt
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seed
from flash.calendar import NRFCalendar
from flash import catalog

D = dt.date


class CatalogCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, cls.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        cls.conn, _ = seed.build(cls.path)
        cls.cal = NRFCalendar()
        cls.da = catalog.DataAccess(cls.conn, cls.cal)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        os.remove(cls.path)

    def test_comp_reconciliation_to_the_cent(self):
        # BR-6: Σ per-entity contributions == scope comp%, every day, every scope.
        for iso in ("2026-07-23", "2026-06-30", "2026-03-15", "2026-05-02"):
            day = D.fromisoformat(iso)
            for scope in ({}, {"region": "Southeast"}, {"region": "West"}):
                contribs = self.da.contribution_to_comp_gap(day, **scope)
                if not contribs:
                    continue
                total = sum(c["contribution"] for c in contribs)
                comp = self.da.comp_pct(day, **scope)
                self.assertAlmostEqual(total, comp, places=9,
                                       msg="%s %s reconciliation" % (iso, scope))

    def test_comp_eligibility_rules(self):
        day = D(2026, 7, 23)
        self.assertTrue(self.da.comp_eligible("ECOM", day))          # always comp
        self.assertTrue(self.da.comp_eligible("LB-001", day))        # est. 2017
        self.assertFalse(self.da.comp_eligible("LB-025", day))       # opened 2025-08
        self.assertFalse(self.da.comp_eligible("LB-013", day))       # in remodel

    def test_hand_comp_matches_direct_sql(self):
        # Acceptance §10 item 2: re-derive day comp for an ordinary day from raw
        # SQL and confirm the comp-store set + LY alignment agree with catalog.
        day = D(2026, 6, 17)                    # ordinary Wednesday, no storyline
        ly = self.da.ly_date(day)
        members = self.da.comp_set(day)
        # independent comp-store set: eligible stores+ECOM reported both sides,
        # not in remodel either day.
        indep = []
        for e in self.da.entities():
            eid = e["entity_id"]
            if not self.da.comp_eligible(eid, day):
                continue
            if self.da._in_remodel(e, ly):
                continue
            ty = self.conn.execute("SELECT net_sales FROM sales_day WHERE date=? AND entity_id=?",
                                   (day.isoformat(), eid)).fetchone()
            lyv = self.conn.execute("SELECT net_sales FROM sales_day WHERE date=? AND entity_id=?",
                                    (ly.isoformat(), eid)).fetchone()
            if ty and lyv:
                indep.append(eid)
        self.assertEqual(set(members), set(indep))
        ty_sum = self.conn.execute(
            "SELECT SUM(net_sales) FROM sales_day WHERE date=? AND entity_id IN (%s)"
            % ",".join("?" * len(indep)), [day.isoformat()] + indep).fetchone()[0]
        ly_sum = self.conn.execute(
            "SELECT SUM(net_sales) FROM sales_day WHERE date=? AND entity_id IN (%s)"
            % ",".join("?" * len(indep)), [ly.isoformat()] + indep).fetchone()[0]
        self.assertAlmostEqual(self.da.comp_pct(day), ty_sum / ly_sum - 1.0, places=9)

    def test_missing_stores_excluded_not_zeroed(self):
        # BR-3: a missing store lowers 'reported', never enters totals as zero.
        day = D(2026, 7, 23)
        comp = self.da.completeness(day)
        self.assertIn("LB-021", comp["missing"])
        self.assertIn("LB-005", comp["missing"])
        # net_sales for a missing store is None (absent), not 0.0
        self.assertIsNone(self.da.net_sales_of("LB-021", day))
        # total excludes them (no zero-fill): equals sum of reported only
        reported_sum = self.conn.execute(
            "SELECT SUM(net_sales) FROM sales_day WHERE date=?",
            (day.isoformat(),)).fetchone()[0]
        self.assertAlmostEqual(self.da.net_sales(day), round(reported_sum, 2), places=2)

    def test_basket_metrics_consistent(self):
        day = D(2026, 7, 23)
        b = self.da.basket(day)
        self.assertAlmostEqual(b["aov"], b["net_sales"] / b["transactions"], places=6)
        self.assertAlmostEqual(b["upt"], b["units"] / b["transactions"], places=6)
        self.assertAlmostEqual(b["aur"], b["net_sales"] / b["units"], places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
