# -*- coding: utf-8 -*-
"""Metric catalog — the ONE home for every formula (BR-5).

Every number the flash shows is computed here and nowhere else; the four render
surfaces consume the objects this module produces. Formulas map 1:1 to PRD §5
(the numbers in method docstrings are the catalog row #).

`DataAccess` wraps a sqlite3 connection + the NRF calendar and exposes the
metric functions. Comparisons are day-aligned by joining to the materialized
`calendar.ly_aligned_date` (BR-1); comp-store membership and remodel/closure
exclusion (BR-2) are enforced in one place: `comp_set()`.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from flash.calendar import NRFCalendar, PERIODS_PER_YEAR

D = dt.date
COMP_PERIODS = 13          # BR-2: 13 full fiscal periods before comp entry
REGIONS = ("Northeast", "Southeast", "Midwest", "Southwest", "West")

# BR-4: an e-commerce day is "matured" (settled figures trustworthy) only after
# the fulfillment file has had this many days to close. Day-of always uses
# demand, labeled; #12 is never computed on an immature day.
ECOM_SETTLE_LAG_DAYS = 3

WINDOWS = ("WTD", "MTD", "YTD")


class DataAccess(object):
    def __init__(self, conn, cal: Optional[NRFCalendar] = None,
                 ecom_basis: str = "demand"):
        if ecom_basis not in ("demand", "settled"):
            raise ValueError(
                "ecom_basis %r is not 'demand' or 'settled'. BR-4: the day-of "
                "flash reads demand (labeled); the settled view reads shipped. "
                "Mixing them silently is the rule this argument exists to stop."
                % (ecom_basis,))
        self.conn = conn
        self.cal = cal or NRFCalendar()
        self.ecom_basis = ecom_basis
        self._entities = None
        # Read-through caches. Semantics are unchanged — these exist so the
        # 60-day archive (which walks YTD windows) meets NFR-3 (< 30s).
        self._sales = None
        self._plan = None
        self._ly = None
        self._comp_set_cache = {}
        self._comp_elig_cache = {}

    # -- entity helpers ----------------------------------------------------

    def entities(self) -> List[dict]:
        if self._entities is None:
            cols = ["entity_id", "store_number", "name", "channel", "region",
                    "open_date", "close_date", "remodel_start", "remodel_end",
                    "rentable_sf", "target_sales_psf", "annual_volume"]
            rows = self.conn.execute("SELECT %s FROM stores" % ",".join(cols)).fetchall()
            self._entities = [dict(zip(cols, r)) for r in rows]
        return self._entities

    def entity(self, entity_id) -> dict:
        for e in self.entities():
            if e["entity_id"] == entity_id:
                return e
        raise KeyError(entity_id)

    def _in_remodel(self, e, day: D) -> bool:
        if not e["remodel_start"]:
            return False
        rs = D.fromisoformat(e["remodel_start"])
        re_ = D.fromisoformat(e["remodel_end"]) if e["remodel_end"] else None
        return day >= rs and (re_ is None or day <= re_)

    def is_open_on(self, e, day: D) -> bool:
        if D.fromisoformat(e["open_date"]) > day:
            return False
        if e["close_date"] and day > D.fromisoformat(e["close_date"]):
            return False
        return not self._in_remodel(e, day)

    # -- comp eligibility (BR-2) ------------------------------------------

    def _step_period(self, fy, pno, delta):
        """Move `delta` fiscal periods from (fy,pno), wrapping across years."""
        idx = (fy * PERIODS_PER_YEAR + (pno - 1)) + delta
        return idx // PERIODS_PER_YEAR, idx % PERIODS_PER_YEAR + 1

    def comp_eligible(self, entity_id, day: D) -> bool:
        """True if the entity is in the comp set on `day` (PRD §5 #2, BR-2).

        ECOM is always comp (owner decision: it carries 2 years of history).
        A store enters comp after COMP_PERIODS full fiscal periods of operation
        and is excluded on any remodel/closure day (both years handled by the
        caller excluding the day on each side)."""
        key = (entity_id, day)
        if key in self._comp_elig_cache:
            return self._comp_elig_cache[key]
        out = self._comp_eligible_uncached(entity_id, day)
        self._comp_elig_cache[key] = out
        return out

    def _comp_eligible_uncached(self, entity_id, day: D) -> bool:
        e = self.entity(entity_id)
        if e["channel"] == "ECOM":
            return True
        if self._in_remodel(e, day):
            return False
        per = self.cal.period_for_date(day)
        # start of the period COMP_PERIODS before the current one
        tfy, tpno = self._step_period(per.fiscal_year, per.period_no, -COMP_PERIODS)
        threshold = self.cal.period(tfy, tpno).start
        return D.fromisoformat(e["open_date"]) <= threshold

    # -- raw lookups -------------------------------------------------------

    SALES_COLS = ("net_sales", "transactions", "units", "demand_sales",
                  "shipped_sales", "returns_recorded", "posted_at")

    def _sales_index(self):
        if self._sales is None:
            self._sales = {}
            sql = ("SELECT date, entity_id, %s FROM sales_day"
                   % ",".join(self.SALES_COLS))
            for row in self.conn.execute(sql):
                self._sales[(row[0], row[1])] = dict(
                    zip(self.SALES_COLS, row[2:]))
        return self._sales

    def _plan_index(self):
        """iso-date -> {entity_id: plan_sales}."""
        if self._plan is None:
            self._plan = {}
            for d, eid, p in self.conn.execute(
                    "SELECT date, entity_id, plan_sales FROM plan_day"):
                self._plan.setdefault(d, {})[eid] = p
        return self._plan

    def plan_of(self, entity_id, day: D) -> Optional[float]:
        return self._plan_index().get(day.isoformat(), {}).get(entity_id)

    def sales_row(self, entity_id, day: D) -> Optional[dict]:
        return self._sales_index().get((day.isoformat(), entity_id))

    def ly_date(self, day: D) -> D:
        """Materialized day-aligned LY counterpart (BR-1) — a join, not a
        computation. Cached; the calendar table is the single source."""
        if self._ly is None:
            self._ly = dict(self.conn.execute(
                "SELECT date, ly_aligned_date FROM calendar"))
        iso = self._ly.get(day.isoformat())
        if not iso:
            raise ValueError(
                "no calendar row for %s — the seed materializes %s..%s; "
                "extend CAL_END in seed.py if a later date is needed"
                % (day, min(self._ly) if self._ly else "?",
                   max(self._ly) if self._ly else "?"))
        return D.fromisoformat(iso)

    def net_sales_of(self, entity_id, day: D) -> Optional[float]:
        """The entity's net sales for the day, or None if it has not posted.

        BR-4: for ECOM this is DEMAND on the day-of basis (what the morning
        flash can honestly know) and SHIPPED on the settled basis (what the
        restated/archive view shows once the fulfillment file closes). Both
        years read the same series, so a settled comp compares like with like."""
        row = self.sales_row(entity_id, day)
        if row is None:
            return None
        if (entity_id == "ECOM" and self.ecom_basis == "settled"
                and row["shipped_sales"] is not None):
            return row["shipped_sales"]
        return row["net_sales"]

    def _scope_entities(self, region=None, channel=None, entity_id=None) -> List[dict]:
        out = []
        for e in self.entities():
            if entity_id and e["entity_id"] != entity_id:
                continue
            if region and e["region"] != region:
                continue
            if channel and e["channel"] != channel:
                continue
            out.append(e)
        return out

    # -- headline metrics --------------------------------------------------

    def net_sales(self, day: D, region=None, channel=None, entity_id=None) -> float:
        """#1 Net Sales (day) = Σ net_sales over REPORTED entities in scope.

        ECOM contributes demand (stored as its net_sales), labeled (BR-4)."""
        scope = set(e["entity_id"] for e in
                    self._scope_entities(region, channel, entity_id))
        total = 0.0
        for eid in scope:
            v = self.net_sales_of(eid, day)
            if v is not None:
                total += v
        return round(total, 2)

    def comp_set(self, day: D, region=None, channel=None, entity_id=None,
                 ly_override: Optional[D] = None) -> List[str]:
        """Comp entities on `day`: eligible, open both TY and LY sides, and
        reported on both sides (missing => excluded from comp, disclosed in
        completeness, never zero-filled).

        `ly_override` swaps the LY side for a different date — the holiday
        override of BR-1 (`calendar.ly_holiday_aligned_date`). It never changes
        the formula, only which LY day the formula reads; that is why the
        holiday-adjusted comp still lives in exactly one place (BR-5)."""
        key = (day, region, channel, entity_id, ly_override)
        if key in self._comp_set_cache:
            return self._comp_set_cache[key]
        ly = ly_override or self.ly_date(day)
        out = []
        for e in self._scope_entities(region, channel, entity_id):
            eid = e["entity_id"]
            if not self.comp_eligible(eid, day):
                continue
            if self._in_remodel(e, ly):        # excluded on the LY side too (BR-2)
                continue
            if self.net_sales_of(eid, day) is None:
                continue
            if self.net_sales_of(eid, ly) is None:
                continue
            out.append(eid)
        out.sort()
        self._comp_set_cache[key] = out
        return out

    def comp_pct(self, day: D, region=None, channel=None, entity_id=None,
                 ly_override: Optional[D] = None) -> Optional[float]:
        """#2 Comp Sales % (day) = (Σ comp TY ÷ Σ comp LY-aligned) − 1."""
        pair = self.comp_pair(day, region, channel, entity_id, ly_override)
        if pair["ly"] == 0:
            return None
        return pair["ty"] / pair["ly"] - 1.0

    def comp_pair(self, day: D, region=None, channel=None, entity_id=None,
                  ly_override: Optional[D] = None) -> Dict[str, object]:
        """The two sides behind #2, so callers never re-sum them themselves."""
        ly_day = ly_override or self.ly_date(day)
        members = self.comp_set(day, region, channel, entity_id, ly_override)
        ty = round(sum(self.net_sales_of(m, day) for m in members), 2)
        lyv = round(sum(self.net_sales_of(m, ly_day) for m in members), 2)
        return {"ty": ty, "ly": lyv, "gap": round(ty - lyv, 2),
                "members": members, "ly_date": ly_day.isoformat()}

    def comp_transactions(self, day: D, region=None, channel=None,
                          entity_id=None, ly_override: Optional[D] = None) -> Dict[str, object]:
        """#7 Transactions (day, vs LY) — same comp basis as #2."""
        ly_day = ly_override or self.ly_date(day)
        members = self.comp_set(day, region, channel, entity_id, ly_override)
        ty = sum(self.sales_row(m, day)["transactions"] for m in members)
        lyv = sum(self.sales_row(m, ly_day)["transactions"] for m in members)
        return {"ty": ty, "ly": lyv,
                "pct": (ty / lyv - 1.0) if lyv else None}

    def plan_sales(self, day: D, region=None, channel=None, entity_id=None) -> float:
        scope = set(e["entity_id"] for e in
                    self._scope_entities(region, channel, entity_id))
        row = self._plan_index().get(day.isoformat(), {})
        return round(sum(p for eid, p in row.items() if eid in scope), 2)

    def plan_attainment(self, day: D, region=None, channel=None,
                        entity_id=None) -> Optional[float]:
        """#3 Plan Attainment % (day) = Σ reported actual ÷ Σ plan (same scope).

        Plan is measured against REPORTED actuals only (a missing store is not
        counted as a plan miss — it is disclosed in completeness instead)."""
        scope = set(e["entity_id"] for e in
                    self._scope_entities(region, channel, entity_id))
        pair = self.plan_pair(day, region, channel, entity_id)
        if pair["plan"] == 0:
            return None
        return pair["actual"] / pair["plan"]

    def plan_pair(self, day: D, region=None, channel=None,
                  entity_id=None) -> Dict[str, float]:
        """Reported actual and its matching plan — the two sides behind #3."""
        scope = set(e["entity_id"] for e in
                    self._scope_entities(region, channel, entity_id))
        plans = self._plan_index().get(day.isoformat(), {})
        actual, plan = 0.0, 0.0
        for eid in scope:
            v = self.net_sales_of(eid, day)
            if v is None:
                continue
            actual += v
            plan += plans.get(eid, 0.0)
        return {"actual": round(actual, 2), "plan": round(plan, 2)}

    # -- transactions / basket (#7-10) ------------------------------------

    def _sum(self, col, day, scope):
        total = 0
        for eid in scope:
            row = self.sales_row(eid, day)
            if row and row[col] is not None:
                total += row[col]
        return total

    def basket(self, day: D, region=None, channel=None, entity_id=None) -> Dict[str, float]:
        """#8 AOV, #9 UPT, #10 AUR over reported entities in scope."""
        scope = set(e["entity_id"] for e in
                    self._scope_entities(region, channel, entity_id))
        net = self.net_sales(day, region, channel, entity_id)
        txns = self._sum("transactions", day, scope)
        units = self._sum("units", day, scope)
        return {
            "net_sales": net,
            "transactions": txns,
            "units": units,
            "aov": (net / txns) if txns else None,
            "upt": (units / txns) if txns else None,
            "aur": (net / units) if units else None,
        }

    # -- focus-panel decomposition (#15, BR-6) ----------------------------

    def contribution_to_comp_gap(self, day: D, region=None, channel=None,
                                 ly_override: Optional[D] = None) -> List[dict]:
        """#15 Contribution to Comp Gap, per entity, within scope.

        entity contribution = (TY − LY-aligned) ÷ total LY-aligned. By
        construction Σ contributions = scope comp% (BR-6 reconciliation).
        Sorted most-adverse first."""
        ly = ly_override or self.ly_date(day)
        members = self.comp_set(day, region, channel, ly_override=ly_override)
        ly_total = sum(self.net_sales_of(m, ly) for m in members)
        out = []
        for m in members:
            ty = self.net_sales_of(m, day)
            lyv = self.net_sales_of(m, ly)
            out.append({
                "entity_id": m,
                "name": self.entity(m)["name"],
                "region": self.entity(m)["region"],
                "channel": self.entity(m)["channel"],
                "ty": ty, "ly": lyv, "delta": ty - lyv,
                "contribution": ((ty - lyv) / ly_total) if ly_total else 0.0,
            })
        out.sort(key=lambda c: (c["contribution"], c["entity_id"]))
        return out

    # -- windows: WTD / MTD(period) / YTD (#4, #5, #6) ---------------------

    def window_start(self, day: D, window: str) -> D:
        """First day of the named fiscal window containing `day`."""
        if window not in WINDOWS:
            raise ValueError("window %r is not one of %s — WTD/MTD/YTD are the "
                             "fiscal windows the flash reports" % (window, WINDOWS))
        if window == "WTD":
            fy = self.cal.fiscal_year_of(day)
            week = self.cal.week_of(day)
            return self.cal.fy_start_date(fy) + dt.timedelta(days=(week - 1) * 7)
        if window == "MTD":
            return self.cal.period_for_date(day).start
        return self.cal.fy_start_date(self.cal.fiscal_year_of(day))

    def window_dates(self, day: D, window: str) -> List[D]:
        start = self.window_start(day, window)
        n = (day - start).days
        return [start + dt.timedelta(days=i) for i in range(n + 1)]

    def window_metrics(self, day: D, window: str, region=None, channel=None,
                       entity_id=None) -> Dict[str, object]:
        """#4 net sales, #5 comp %, #6 plan attainment over a fiscal window.

        Built day by day from each day's own aligned LY date and each day's own
        comp set (PRD §5: "windows built from aligned days, not shifted
        totals"). Summing a window total and shifting it would silently mix
        weekdays across the year boundary."""
        net = plan = actual = comp_ty = comp_ly = 0.0
        days = self.window_dates(day, window)
        for d in days:
            net += self.net_sales(d, region, channel, entity_id)
            pp = self.plan_pair(d, region, channel, entity_id)
            actual += pp["actual"]
            plan += pp["plan"]
            cp = self.comp_pair(d, region, channel, entity_id)
            comp_ty += cp["ty"]
            comp_ly += cp["ly"]
        return {
            "window": window,
            "start": days[0].isoformat(),
            "end": day.isoformat(),
            "days": len(days),
            "net_sales": round(net, 2),
            "comp_ty": round(comp_ty, 2),
            "comp_ly": round(comp_ly, 2),
            "comp_gap": round(comp_ty - comp_ly, 2),
            "comp_pct": (comp_ty / comp_ly - 1.0) if comp_ly else None,
            "plan": round(plan, 2),
            "plan_attainment": (actual / plan) if plan else None,
        }

    # -- e-commerce demand vs settled (#11, #12, BR-4) ---------------------

    def ecom_matured(self, day: D, as_of: D) -> bool:
        return (as_of - day).days >= ECOM_SETTLE_LAG_DAYS

    def ecom_day(self, day: D, as_of: D) -> Optional[Dict[str, object]]:
        """#11 E-comm Demand vs Shipped, one day, with its maturation state.

        Demand leads day-of (BR-4); `shipped`/`returns` are carried but flagged
        immature until the fulfillment file has had ECOM_SETTLE_LAG_DAYS."""
        row = self.sales_row("ECOM", day)
        if row is None:
            return None
        matured = self.ecom_matured(day, as_of)
        ly_day = self.ly_date(day)
        ly_row = self.sales_row("ECOM", ly_day)
        out = {
            "date": day.isoformat(),
            "demand": round(row["demand_sales"], 2),
            "shipped": round(row["shipped_sales"], 2),
            "returns": round(row["returns_recorded"], 2),
            "matured": matured,
            "settle_lag_days": ECOM_SETTLE_LAG_DAYS,
            "ly_date": ly_day.isoformat(),
            "ly_demand": round(ly_row["demand_sales"], 2) if ly_row else None,
            "ly_shipped": round(ly_row["shipped_sales"], 2) if ly_row else None,
        }
        out["demand_comp_pct"] = (
            out["demand"] / out["ly_demand"] - 1.0) if out["ly_demand"] else None
        out["shipped_comp_pct"] = (
            out["shipped"] / out["ly_shipped"] - 1.0) if out["ly_shipped"] else None
        return out

    def ecom_settled_return_rate(self, as_of: D, lookback_days: int = 28) -> Optional[float]:
        """#12 E-comm Settled Return Rate = returns ÷ shipped, MATURED window
        only. Never computed on an immature day (that is the BR-4 trap)."""
        last = as_of - dt.timedelta(days=ECOM_SETTLE_LAG_DAYS)
        shipped = returns = 0.0
        for i in range(lookback_days):
            d = last - dt.timedelta(days=i)
            row = self.sales_row("ECOM", d)
            if row is None or row["shipped_sales"] is None:
                continue
            shipped += row["shipped_sales"]
            returns += row["returns_recorded"]
        if shipped == 0:
            return None
        return returns / shipped

    # -- gap-to-go (#14, Monday recap) ------------------------------------

    def gap_to_go(self, day: D) -> Dict[str, object]:
        """#14 Gap-to-Go Run Rate = plan remaining in the fiscal period ÷
        selling days remaining. Recap edition only."""
        per = self.cal.period_for_date(day)
        plan_total = sum(self.plan_sales(per.start + dt.timedelta(days=i))
                         for i in range((per.end - per.start).days + 1))
        actual = self.window_metrics(day, "MTD")["net_sales"]
        remaining_days = (per.end - day).days
        remaining_plan = round(plan_total - actual, 2)
        return {
            "period_label": per.label,
            "period_end": per.end.isoformat(),
            "period_plan": round(plan_total, 2),
            "actual_to_date": actual,
            "remaining_plan": remaining_plan,
            "remaining_days": remaining_days,
            "required_run_rate": (remaining_plan / remaining_days)
            if remaining_days > 0 else None,
        }

    # -- completeness (#13, BR-3) -----------------------------------------

    def completeness(self, day: D) -> Dict[str, object]:
        """#13 Completeness: reported stores ÷ expected; missing entities named.

        Second half of #13 — posted sales ÷ the trailing-4 same-weekday average
        — answers "how much of a normal day's dollars actually landed", which
        is the number that tells a reader whether a 24-of-25 day is fine or a
        big door is dark."""
        expected = [e for e in self.entities()
                    if e["channel"] == "STORE" and self.is_open_on(e, day)]
        missing = [e["entity_id"] for e in expected
                   if self.sales_row(e["entity_id"], day) is None]
        posted = self.net_sales(day, channel="STORE")
        baseline = self.trailing_same_weekday_avg(day, weeks=4, channel="STORE")
        return {
            "expected": len(expected),
            "reported": len(expected) - len(missing),
            "missing": sorted(missing),
            "missing_names": [self.entity(m)["name"] for m in sorted(missing)],
            "pct": (len(expected) - len(missing)) / len(expected) if expected else 1.0,
            "posted_sales": posted,
            "baseline_sales": baseline,
            "posted_pct": (posted / baseline) if baseline else None,
        }

    def trailing_same_weekday_avg(self, day: D, weeks: int = 4,
                                  region=None, channel=None,
                                  entity_id=None) -> Optional[float]:
        """Mean net sales of the `weeks` prior same-weekday days (#13 basis)."""
        vals = []
        for i in range(1, weeks + 1):
            d = day - dt.timedelta(days=7 * i)
            try:
                self.ly_date(d)          # inside the materialized calendar
            except ValueError:
                continue
            vals.append(self.net_sales(d, region, channel, entity_id))
        if not vals:
            return None
        return round(sum(vals) / len(vals), 2)

    def late_posters(self, day: D, lookback_days: int = 1) -> List[dict]:
        """BR-3 late-poster escalation: stores unposted on `day` and, when they
        were also unposted on the preceding day(s), flagged as escalating.

        A store that has not posted is MISSING, never zero — it stays out of
        the comp set and out of the totals, and it is named here so the flash
        can say so out loud."""
        out = []
        for eid in self.completeness(day)["missing"]:
            streak = 1
            probe = day - dt.timedelta(days=1)
            while streak <= lookback_days + 3:
                e = self.entity(eid)
                if not self.is_open_on(e, probe):
                    break
                if self.sales_row(eid, probe) is not None:
                    break
                streak += 1
                probe -= dt.timedelta(days=1)
            out.append({
                "entity_id": eid,
                "name": self.entity(eid)["name"],
                "region": self.entity(eid)["region"],
                "consecutive_days": streak,
                "escalate": streak >= 2,
                "since": (day - dt.timedelta(days=streak - 1)).isoformat(),
            })
        out.sort(key=lambda r: (-r["consecutive_days"], r["entity_id"]))
        return out
