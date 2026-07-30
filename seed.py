# -*- coding: utf-8 -*-
"""Deterministic seed generator for the Daily Sales Flash.

Builds `flash.db` from `schema.sql`: entities (25 Lumière stores ported from
`Leases/src/roster.py` + one ECOM channel), the NRF 4-5-4 calendar with
materialized day-aligned LY dates, 2 full fiscal years + current-YTD of daily
facts, a plan, and the eight planted storylines the PRD (§7) calls the
acceptance material. Every storyline is asserted to manifest in the data
(assertions-not-hope, the Lease Toolkit standard).

Determinism (NFR-2): all randomness is a stable hash of (entity, date, tag) —
no `random` module, no `now()`. Same source -> byte-identical database and
CSV exports.

Run:  python3 seed.py          # builds ./flash.db and prints a storyline index
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import sqlite3
import sys

# Import the calendar (the moat) and the ported roster.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flash.calendar import (          # noqa: E402
    NRFCalendar, dow_1sun, holiday_code, holidays_for_calendar_year,
)

# The Lumière roster is vendored (vendor/roster.py) so the repo is
# self-contained; the Leases project remains the upstream source of truth.
try:
    from vendor.roster import ROSTER  # noqa: E402
except ImportError:
    ROSTER_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "Leases", "src")
    sys.path.insert(0, os.path.abspath(ROSTER_PATH))
    from roster import ROSTER         # noqa: E402

D = dt.date
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "flash.db")
SCHEMA_PATH = os.path.join(HERE, "schema.sql")

# --- demo anchors ---------------------------------------------------------
TODAY = D(2026, 7, 24)              # "today" is fixed by the data, never now()
LATEST_COMPLETE = D(2026, 7, 23)   # yesterday: the default flash date
SALES_START = D(2024, 2, 4)        # FY2024 start (2 full FYs + FY2026 YTD)
CAL_START = D(2023, 1, 29)         # FY2023 start, so FY2024's LY dates exist
SALES_END = LATEST_COMPLETE        # actuals stop at the last complete day
# The calendar and the PLAN run to the end of the fiscal period in flight. A
# plan legitimately exists ahead of actuals — without the forward rows the
# gap-to-go run rate (#14) has no remaining plan to divide, and "today"
# (2026-07-24) would have no calendar row to resolve its LY counterpart.
CAL_END = NRFCalendar().period_for_date(LATEST_COMPLETE).end

BASE_FY = 2024
STORE_GROWTH = 0.03                # YoY store trend
ECOM_GROWTH = 0.12                 # ECOM grows faster (Strategy: faster growth)
ECOM_SHARE = 0.22                  # ECOM ~22% of total revenue (base year)

# --- shape curves (normalized to mean 1.0 at load) ------------------------
_PERIOD_WEIGHTS = {                # beauty retailer; Q4 (P10/P11) heavy
    1: 1.05, 2: 0.92, 3: 0.95, 4: 1.10, 5: 1.00, 6: 1.02,
    7: 1.05, 8: 0.95, 9: 0.98, 10: 1.22, 11: 1.48, 12: 0.85,
}
_DOW_WEIGHTS = {                   # 1=Sun..7=Sat; Sat peak, Tue trough
    1: 1.05, 2: 0.85, 3: 0.80, 4: 0.88, 5: 0.95, 6: 1.20, 7: 1.45,
}
_HOLIDAY_MULT = {
    "NEW_YEARS_DAY": 0.60, "VALENTINES": 1.55, "EASTER": 0.70,
    "MOTHERS_DAY": 1.70, "MEMORIAL_DAY": 1.20, "JULY_4": 1.35,
    "LABOR_DAY": 1.20, "THANKSGIVING": 0.40, "BLACK_FRIDAY": 2.60,
    "CYBER_MONDAY": 1.90, "CHRISTMAS_EVE": 1.55, "CHRISTMAS_DAY": 0.10,
    "NEW_YEARS_EVE": 1.15,
}


def _normalized(weights):
    mean = sum(weights.values()) / len(weights)
    return {k: v / mean for k, v in weights.items()}


PERIOD_W = _normalized(_PERIOD_WEIGHTS)
DOW_W = _normalized(_DOW_WEIGHTS)

# --- planted-storyline parameters (indexed in README) ---------------------
SOFT_REGION = "Southeast"
SOFT_STORES = ("LB-009", "LB-010")            # Palmetto Landing, Sunset Terrace
SOFT_START = D(2026, 7, 10)                    # trailing ~2 weeks
SOFT_MULT = 0.78
BRIGHT_STORE = "LB-022"                        # Pacific Heights Court (West)
BRIGHT_START = D(2026, 7, 17)
BRIGHT_MULT = 1.18
REMODEL_STORE = "LB-013"                       # Lakeview Arcade ('Closing')
REMODEL_START = D(2026, 6, 15)                 # comp-excluded, no rows from here
NEW_STORE = "LB-025"                           # opened 2025-08-01, < 13 periods
LATE_BOTH = "LB-021"                           # missing 07-22 AND 07-23 (escalates)
LATE_ONE = "LB-005"                            # missing 07-23 only
LATE_DAY = D(2026, 7, 23)
LATE_DAY_PREV = D(2026, 7, 22)
ECOM_MATURATION_DAY = D(2026, 7, 23)           # demand -8% but settles +5%
RESTATE_DAY = D(2026, 7, 20)                   # flash re-issued as version 2


def u(*parts) -> float:
    """Deterministic uniform in [0,1) from a stable hash (platform-independent)."""
    s = "|".join(str(p) for p in parts)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:13], 16) / float(16 ** 13)


# --- entity construction --------------------------------------------------

def build_entities():
    """Return list of entity dicts for the `stores` table."""
    # Fallback PSF for stores the roster leaves at 0 (e.g. Opening-Soon).
    psfs = [r["target_sales_psf"] for r in ROSTER if r["target_sales_psf"]]
    median_psf = sorted(psfs)[len(psfs) // 2]

    entities = []
    store_annual_total = 0.0
    for r in ROSTER:
        psf = r["target_sales_psf"] or median_psf
        annual = psf * r["rentable_sf"]
        store_annual_total += annual
        remodel_start = REMODEL_START.isoformat() if r["lease_id"] == REMODEL_STORE else None
        entities.append(dict(
            entity_id=r["lease_id"],
            store_number=r["store_number"],
            name=r["store_name"],
            channel="STORE",
            region=r["region"],
            open_date=r["commencement_date"].isoformat(),
            close_date=None,
            remodel_start=remodel_start,
            remodel_end=None,
            rentable_sf=r["rentable_sf"],
            target_sales_psf=r["target_sales_psf"],
            annual_volume=round(annual, 2),
        ))
    # ECOM: sized so it is ~22% of total (base year); has full history.
    ecom_annual = store_annual_total * (ECOM_SHARE / (1.0 - ECOM_SHARE))
    entities.append(dict(
        entity_id="ECOM", store_number=None, name="E-commerce",
        channel="ECOM", region="ECOM",
        open_date=CAL_START.isoformat(), close_date=None,
        remodel_start=None, remodel_end=None, rentable_sf=None,
        target_sales_psf=None, annual_volume=round(ecom_annual, 2),
    ))
    return entities


def open_date_of(e):
    return dt.date.fromisoformat(e["open_date"])


def is_open_on(e, day):
    """Store is trading on `day` (open, not in remodel/closure window)."""
    if open_date_of(e) > day:
        return False
    if e["remodel_start"]:
        rs = dt.date.fromisoformat(e["remodel_start"])
        re_ = dt.date.fromisoformat(e["remodel_end"]) if e["remodel_end"] else None
        if day >= rs and (re_ is None or day <= re_):
            return False
    return True


def is_missing(entity_id, day):
    """Planted late-poster incident: these entity/day rows never post (BR-3)."""
    if day == LATE_DAY and entity_id in (LATE_BOTH, LATE_ONE):
        return True
    if day == LATE_DAY_PREV and entity_id == LATE_BOTH:
        return True
    return False


# --- daily figure model ---------------------------------------------------

def year_factor(channel, fiscal_year):
    yrs = fiscal_year - BASE_FY
    g = ECOM_GROWTH if channel == "ECOM" else STORE_GROWTH
    return (1.0 + g) ** yrs


def storyline_mult(entity_id, day):
    """Multiplicative storyline effects layered on the base model."""
    m = 1.0
    if entity_id in SOFT_STORES and SOFT_START <= day <= LATEST_COMPLETE:
        m *= SOFT_MULT
    if entity_id == BRIGHT_STORE and BRIGHT_START <= day <= LATEST_COMPLETE:
        m *= BRIGHT_MULT
    return m


def base_sales(entity, day, fiscal_year, period, dow):
    """Deterministic net sales for a trading entity/day (pre-missing check)."""
    daily_mean = entity["annual_volume"] * year_factor(entity["channel"], fiscal_year) / 364.0
    season = PERIOD_W[period] * DOW_W[dow]
    hol = _HOLIDAY_MULT.get(holiday_code(day), 1.0)
    noise = 0.90 + 0.20 * u(entity["entity_id"], day.isoformat(), "noise")   # ±10%
    val = daily_mean * season * hol * noise * storyline_mult(entity["entity_id"], day)
    return val


def txn_units(entity, net):
    aov = 45.0 + 45.0 * u(entity["entity_id"], "aov") if entity["channel"] == "STORE" \
        else 65.0 + 30.0 * u(entity["entity_id"], "aov")
    upt = 1.8 + 1.6 * u(entity["entity_id"], "upt")
    txns = max(1, int(round(net / aov)))
    units = max(txns, int(round(txns * upt)))
    return txns, units


def ecom_series(entity, day, net):
    """demand / shipped(settled) / returns for an ECOM day (BR-4).

    Normal days: shipped settles near demand. The planted maturation day
    (07-23) has demand -8% vs its LY but settles +5% — the burst-of-large-
    baskets case that looks soft day-of and settles positive.
    """
    demand = net
    if day == ECOM_MATURATION_DAY:
        # anchor to the LY-aligned figures so the divergence is exact & visible
        cal = NRFCalendar()
        ly, _ = cal.ly_aligned_date(day)
        ly_net = base_sales(entity, ly, cal.fiscal_year_of(ly),
                            cal.period_for_date(ly).period_no, dow_1sun(ly))
        demand = round(ly_net * 0.92, 2)          # looks -8% day-of
        shipped = round(ly_net * 1.05, 2)         # settles +5%
    else:
        shipped = round(demand * (0.985 + 0.03 * u(entity["entity_id"], day.isoformat(), "ship")), 2)
    returns = round(shipped * (0.06 + 0.03 * u(entity["entity_id"], day.isoformat(), "ret")), 2)
    return round(demand, 2), shipped, returns


def plan_sales(entity, day, fiscal_year, period, dow):
    """Plan tracks the deterministic mean (no noise, no storyline) so plan
    attainment reads as noise ± storyline around 100%."""
    daily_mean = entity["annual_volume"] * year_factor(entity["channel"], fiscal_year) / 364.0
    season = PERIOD_W[period] * DOW_W[dow]
    hol = _HOLIDAY_MULT.get(holiday_code(day), 1.0)
    return round(daily_mean * season * hol, 2)


# --- build ----------------------------------------------------------------

def build(db_path=DB_PATH):
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    cal = NRFCalendar()
    entities = build_entities()

    conn.executemany(
        "INSERT INTO stores VALUES (:entity_id,:store_number,:name,:channel,"
        ":region,:open_date,:close_date,:remodel_start,:remodel_end,"
        ":rentable_sf,:target_sales_psf,:annual_volume)", entities)

    # calendar rows
    cal_rows = []
    day = CAL_START
    while day <= CAL_END:
        fy, period, week, dow = cal.coordinates(day)
        ly, restated = cal.ly_aligned_date(day)
        cal_rows.append((day.isoformat(), fy, period, week, dow,
                        holiday_code(day), ly.isoformat(), 1 if restated else 0))
        day += dt.timedelta(days=1)
    conn.executemany(
        "INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?)", cal_rows)

    # facts + plan
    sales_rows, plan_rows = [], []
    day = SALES_START
    while day <= CAL_END:
        fy, period, week, dow = cal.coordinates(day)
        for e in entities:
            if not is_open_on(e, day):
                continue
            plan_rows.append((day.isoformat(), e["entity_id"],
                              plan_sales(e, day, fy, period, dow)))
            if day > SALES_END:          # forward plan only, no actuals yet
                continue
            posted = day.isoformat() + "T06:30:00-04:00"
            net = base_sales(e, day, fy, period, dow)
            if e["channel"] == "ECOM":
                demand, shipped, returns = ecom_series(e, day, net)
                net = demand   # headline uses ECOM demand, labeled (metric #1)
                txns, units = txn_units(e, net)
                if not is_missing(e["entity_id"], day):
                    sales_rows.append((day.isoformat(), e["entity_id"], round(net, 2),
                                    txns, units, demand, shipped, returns, posted))
            else:
                txns, units = txn_units(e, net)
                if not is_missing(e["entity_id"], day):
                    sales_rows.append((day.isoformat(), e["entity_id"], round(net, 2),
                                    txns, units, None, None, None, posted))
        day += dt.timedelta(days=1)

    conn.executemany(
        "INSERT INTO sales_day VALUES (?,?,?,?,?,?,?,?,?)", sales_rows)
    conn.executemany("INSERT INTO plan_day VALUES (?,?,?)", plan_rows)
    conn.commit()
    return conn, entities


# --- storyline assertions (NFR-4: name the storyline, rows, and the fix) ---

def _fail(storyline, detail):
    raise AssertionError("STORYLINE '%s' did not manifest: %s" % (storyline, detail))


def assert_storylines(conn, cal):
    cur = conn.cursor()

    def q(sql, args=()):
        return cur.execute(sql, args).fetchall()

    # 1. Holiday-shift week: raw (week/day-aligned) LY differs from holiday LY.
    from flash.calendar import ly_holiday_aligned_date
    j4 = D(2026, 7, 4)
    raw_ly, _ = cal.ly_aligned_date(j4)
    hol_ly = ly_holiday_aligned_date(j4)
    if raw_ly == hol_ly or hol_ly is None:
        _fail("1 holiday-shift", "July 4 raw-aligned %s == holiday-aligned %s"
              % (raw_ly, hol_ly))

    # 2. Soft Southeast region: negative day comp on 07-23, driven by 2 stores.
    from flash import catalog
    da = catalog.DataAccess(conn, cal)
    day = LATEST_COMPLETE
    region_comp = da.comp_pct(day, region=SOFT_REGION)
    if region_comp is None or region_comp >= 0:
        _fail("2 soft-region", "%s day comp is %r (want < 0)" % (SOFT_REGION, region_comp))
    contribs = da.contribution_to_comp_gap(day, region=SOFT_REGION)
    top2 = sum(c["contribution"] for c in contribs[:2])
    total_adverse = sum(c["contribution"] for c in contribs if c["contribution"] < 0)
    if not set(c["entity_id"] for c in contribs[:2]) == set(SOFT_STORES):
        _fail("2 soft-region", "top-2 movers %s != %s"
              % ([c["entity_id"] for c in contribs[:2]], list(SOFT_STORES)))

    # 3. Remodel closure: no rows for LB-013 in the window; excluded from comp.
    rows = q("SELECT COUNT(*) FROM sales_day WHERE entity_id=? AND date>=?",
            (REMODEL_STORE, REMODEL_START.isoformat()))
    if rows[0][0] != 0:
        _fail("3 remodel-closure", "%s has %d rows after remodel start"
              % (REMODEL_STORE, rows[0][0]))
    if da.comp_eligible(REMODEL_STORE, LATEST_COMPLETE):
        _fail("3 remodel-closure", "%s counted as comp during remodel" % REMODEL_STORE)

    # 4. Late posters: two missing on 07-23; one missing 07-22 too (escalation).
    present_2307 = set(r[0] for r in q(
        "SELECT entity_id FROM sales_day WHERE date=?", (LATE_DAY.isoformat(),)))
    if LATE_BOTH in present_2307 or LATE_ONE in present_2307:
        _fail("4 late-poster", "expected %s and %s missing on %s"
              % (LATE_BOTH, LATE_ONE, LATE_DAY))
    present_2207 = set(r[0] for r in q(
        "SELECT entity_id FROM sales_day WHERE date=?", (LATE_DAY_PREV.isoformat(),)))
    if LATE_BOTH in present_2207:
        _fail("4 late-poster", "%s should be missing on %s too (escalation)"
              % (LATE_BOTH, LATE_DAY_PREV))

    # 5. E-comm maturation: demand < LY but shipped > LY on the planted day.
    r = q("SELECT demand_sales, shipped_sales FROM sales_day WHERE date=? AND entity_id='ECOM'",
          (ECOM_MATURATION_DAY.isoformat(),))[0]
    ly, _ = cal.ly_aligned_date(ECOM_MATURATION_DAY)
    ly_row = q("SELECT demand_sales, shipped_sales FROM sales_day WHERE date=? AND entity_id='ECOM'",
               (ly.isoformat(),))
    if ly_row:
        ly_demand = ly_row[0][0]
        if not (r[0] < ly_demand < r[1]):
            _fail("5 ecom-maturation", "demand %.0f, LY %.0f, shipped %.0f "
                  "(want demand<LY<shipped)" % (r[0], ly_demand, r[1]))

    # 6. New store: included in total, excluded from comp on 07-23.
    if da.comp_eligible(NEW_STORE, LATEST_COMPLETE):
        _fail("6 new-store", "%s should be non-comp (<13 periods)" % NEW_STORE)
    in_total = q("SELECT COUNT(*) FROM sales_day WHERE entity_id=? AND date=?",
                (NEW_STORE, LATEST_COMPLETE.isoformat()))[0][0]
    if in_total == 0:
        _fail("6 new-store", "%s missing from total on %s" % (NEW_STORE, LATEST_COMPLETE))

    # 7. Plan-beat bright spot: BRIGHT_STORE beats plan on 07-23.
    att = da.plan_attainment(LATEST_COMPLETE, entity_id=BRIGHT_STORE)
    if att is None or att <= 1.05:
        _fail("7 bright-spot", "%s plan attainment %r (want > 1.05)"
              % (BRIGHT_STORE, att))

    # 8. Restatement is generated at flash time (compute phase) — data supports
    #    it via the flash_archive(version) PK; verified there, not in the seed.
    return True


def main():
    conn, entities = build()
    cal = NRFCalendar()
    assert_storylines(conn, cal)
    cur = conn.cursor()
    n_sales = cur.execute("SELECT COUNT(*) FROM sales_day").fetchone()[0]
    n_cal = cur.execute("SELECT COUNT(*) FROM calendar").fetchone()[0]
    print("Built %s" % DB_PATH)
    print("  entities: %d (%d stores + ECOM)" % (len(entities), len(entities) - 1))
    print("  calendar rows: %d (%s .. %s)" % (n_cal, CAL_START, CAL_END))
    print("  sales_day rows: %d" % n_sales)
    print("  all 7 data-level storyline assertions passed")
    conn.close()


if __name__ == "__main__":
    main()
