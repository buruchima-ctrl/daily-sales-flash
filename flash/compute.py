# -*- coding: utf-8 -*-
"""The computed flash object — one per day, four surfaces (BR-5).

This module builds a plain, JSON-serializable dict. It computes nothing itself:
every figure comes from `catalog` (the formula home) and every display string
from `fmt` (the formatting home). Renderers read this object and print it. If a
renderer ever needs a number that is not in here, the fix is to add it here —
not to compute it in the renderer, which is how two surfaces start disagreeing.

The one piece of real judgement in this file is the **holiday override** (BR-1).
The catalog computes comps against whatever LY date it is handed. The calendar
knows two candidate LY dates for a holiday: the week/day-aligned one and the
same-holiday-last-year one. Deciding which leads is a business rule, so it
lives here, once, and the object carries both figures with the adjusted one in
the lead slot — never one without the other.

Determinism (NFR-2): `as_of` comes from the caller (the send morning, derived
from the flash date), never `now()`. Dict construction is stable and the
archive serializes with sort_keys.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from flash import fmt, narrative
from flash.calendar import ly_holiday_aligned_date
from flash.focus import build_focus

D = dt.date

SCHEMA_VERSION = 1
COMPANY = "Lumière Beauty Co."
CHANNELS = ("STORE", "ECOM")
REGIONS = ("Northeast", "Southeast", "Midwest", "Southwest", "West")


def send_morning(day: D) -> D:
    """The flash for `day` is sent the following morning. Derived from the
    data's own date — the reason nothing here calls now() (NFR-2)."""
    return day + dt.timedelta(days=1)


def build_flash(da, day: D, as_of: Optional[D] = None,
                version: int = 1, reason: Optional[str] = None) -> Dict[str, object]:
    """Build the computed flash object for one day."""
    as_of = as_of or send_morning(day)
    cal = da.cal
    fy, period_no, week, dow = cal.coordinates(day)
    per = cal.period_for_date(day)
    week_aligned_ly, restated = cal.ly_aligned_date(day)
    holiday = _holiday_of(da, day)
    settled_basis = (da.ecom_basis == "settled")

    obj: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "company": COMPANY,
        "date": day.isoformat(),
        "as_of": as_of.isoformat(),
        "version": version,
        "reason": reason,
        "basis": da.ecom_basis,
        "calendar": {
            "fiscal_year": fy,
            "period": period_no,
            "period_label": per.label,
            "quarter": per.quarter,
            "week": week,
            "day_of_week": dow,
            "weekday": fmt.WEEKDAYS[day.weekday()],
            "holiday_code": holiday,
            "restated_53_week": bool(restated),
            "week_start": da.window_start(day, "WTD").isoformat(),
            "period_start": per.start.isoformat(),
            "period_end": per.end.isoformat(),
            "year_start": cal.fy_start_date(fy).isoformat(),
        },
    }

    obj["comp"] = _comp_block(da, day, week_aligned_ly, holiday, restated)
    lead_ly = D.fromisoformat(obj["comp"]["ly_date"])
    ly_override = lead_ly if obj["comp"]["override_in_effect"] else None

    obj["headline"] = _headline(da, day, obj["comp"])
    obj["windows"] = {w: _window(da, day, w) for w in ("WTD", "MTD", "YTD")}
    obj["slices"] = {
        "channel": _slices(da, day, "channel", ly_override),
        "region": _slices(da, day, "region", ly_override),
    }
    obj["ecom"] = _ecom(da, day, as_of, settled_basis)
    obj["completeness"] = _completeness(da, day)
    obj["focus"] = build_focus(da, day, ly_override=ly_override)
    obj["recap"] = _recap(da, day, dow)
    obj["disclosures"] = _disclosures(da, day, obj)
    obj["method"] = _method(obj)
    obj["narrative"] = narrative.compose(obj)
    obj["display"] = _display(obj)
    obj["subject"] = _subject(obj)
    _assert_invariants(obj, day)
    return obj


# -- comp, and the holiday override (BR-1) ---------------------------------

def _holiday_of(da, day: D) -> Optional[str]:
    row = da.conn.execute("SELECT holiday_code FROM calendar WHERE date=?",
                          (day.isoformat(),)).fetchone()
    return row[0] if row else None


def _comp_block(da, day: D, week_aligned_ly: D, holiday: Optional[str],
                restated: bool) -> Dict[str, object]:
    """#2 with the BR-1 lead/raw discipline made explicit.

    Three comparisons exist for any day. Only the first is allowed to lead:

      holiday-aligned   same holiday code last year        (holidays only)
      week-aligned      same fiscal week + same weekday     (the default)
      calendar-date     the same calendar date last year    (never leads)

    The calendar-date figure is carried because BR-1 says the raw comparison
    "never appears without the aligned figure leading" — the honest way to
    honour that is to show what the spreadsheet flash would have printed, next
    to the number that is actually right.
    """
    week_pair = da.comp_pair(day)
    week_pct = da.comp_pct(day)

    holiday_ly = ly_holiday_aligned_date(day) if holiday else None
    override = bool(holiday_ly and holiday_ly != week_aligned_ly)

    block: Dict[str, object] = {
        "holiday_code": holiday,
        "override_in_effect": override,
        "restated_53_week": bool(restated),
        "week_aligned": _side(week_pair, week_pct, "week-aligned",
                              week_aligned_ly),
    }

    if override:
        pair = da.comp_pair(day, ly_override=holiday_ly)
        pct = da.comp_pct(day, ly_override=holiday_ly)
        block["holiday_aligned"] = _side(pair, pct, "holiday-aligned", holiday_ly)
        lead = block["holiday_aligned"]
    else:
        block["holiday_aligned"] = None
        lead = block["week_aligned"]

    # the calendar-date comparison — computed, carried, never allowed to lead
    cal_date_ly = _same_calendar_date_ly(day)
    cal_pair = cal_pct = None
    try:
        cal_pair = da.comp_pair(day, ly_override=cal_date_ly)
        cal_pct = da.comp_pct(day, ly_override=cal_date_ly)
    except ValueError:
        pass
    block["calendar_date"] = (_side(cal_pair, cal_pct, "calendar-date", cal_date_ly)
                              if cal_pair else None)

    block.update({
        "basis": lead["basis"],
        "ly_date": lead["ly_date"],
        "pct": lead["pct"],
        "ty": lead["ty"],
        "ly": lead["ly"],
        "gap": lead["gap"],
        "members": lead["members"],
    })
    return block


def _side(pair, pct, basis, ly_date) -> Dict[str, object]:
    return {
        "basis": basis,
        "ly_date": ly_date.isoformat() if hasattr(ly_date, "isoformat") else ly_date,
        "pct": pct,
        "ty": pair["ty"],
        "ly": pair["ly"],
        "gap": pair["gap"],
        "members": len(pair["members"]),
    }


def _same_calendar_date_ly(day: D) -> D:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:              # Feb 29
        return day.replace(year=day.year - 1, day=28)


# -- headline, windows, slices ---------------------------------------------

def _headline(da, day: D, comp: Dict[str, object]) -> Dict[str, object]:
    basket = da.basket(day)
    plan = da.plan_pair(day)
    txn = da.comp_transactions(
        day, ly_override=(D.fromisoformat(comp["ly_date"])
                          if comp["override_in_effect"] else None))
    return {
        "net_sales": basket["net_sales"],
        "comp_pct": comp["pct"],
        "comp_basis": comp["basis"],
        "plan": plan["plan"],
        "plan_attainment": (plan["actual"] / plan["plan"]) if plan["plan"] else None,
        "plan_gap": round(plan["actual"] - plan["plan"], 2),
        "transactions": basket["transactions"],
        "units": basket["units"],
        "aov": basket["aov"],
        "upt": basket["upt"],
        "aur": basket["aur"],
        "comp_transactions": txn,
    }


def _window(da, day: D, window: str) -> Dict[str, object]:
    m = da.window_metrics(day, window)
    m["label"] = {"WTD": "Week to date", "MTD": "Period to date",
                  "YTD": "Year to date"}[window]
    return m


def _slices(da, day: D, dimension: str, ly_override) -> List[Dict[str, object]]:
    """Channel and region cuts of the same day. Each slice carries its own comp
    set size so a reader can see why a region's comp base is smaller than its
    store count (remodel/new-store exclusions, BR-2)."""
    out = []
    keys = CHANNELS if dimension == "channel" else REGIONS + ("ECOM",)
    for key in keys:
        kw = {"channel": key} if dimension == "channel" else {"region": key}
        pair = da.comp_pair(day, ly_override=ly_override, **kw)
        plan = da.plan_pair(day, **kw)
        scope = da._scope_entities(**{k: v for k, v in kw.items()})
        open_ids = [e["entity_id"] for e in scope if da.is_open_on(e, day)]
        reported = [eid for eid in open_ids if da.sales_row(eid, day) is not None]
        out.append({
            "key": key,
            "label": _slice_label(key),
            "net_sales": da.net_sales(day, **kw),
            "comp_pct": (pair["ty"] / pair["ly"] - 1.0) if pair["ly"] else None,
            "comp_ty": pair["ty"],
            "comp_ly": pair["ly"],
            "comp_gap": pair["gap"],
            "comp_members": len(pair["members"]),
            "open_entities": len(open_ids),
            "reported_entities": len(reported),
            "plan": plan["plan"],
            "plan_attainment": (plan["actual"] / plan["plan"]) if plan["plan"] else None,
        })
    return out


def _slice_label(key: str) -> str:
    return {"STORE": "Stores", "ECOM": "E-commerce"}.get(key, key)


# -- e-commerce (BR-4) ------------------------------------------------------

def _ecom(da, day: D, as_of: D, settled_basis: bool) -> Dict[str, object]:
    e = da.ecom_day(day, as_of) or {}
    e["basis_in_headline"] = "shipped (settled)" if settled_basis else "demand (ordered)"
    e["settled_return_rate"] = da.ecom_settled_return_rate(as_of)
    lag = e.get("settle_lag_days", catalog_lag())
    e["return_rate_window_end"] = (as_of - dt.timedelta(days=lag)).isoformat()
    e["return_rate_window_days"] = 28
    return e


def catalog_lag() -> int:
    from flash.catalog import ECOM_SETTLE_LAG_DAYS
    return ECOM_SETTLE_LAG_DAYS


def _completeness(da, day: D) -> Dict[str, object]:
    c = da.completeness(day)
    c["late_posters"] = da.late_posters(day)
    c["escalating"] = [lp for lp in c["late_posters"] if lp["escalate"]]
    return c


# -- Monday trade recap (BRD §4.6, #14) ------------------------------------

def _recap(da, day: D, dow: int) -> Optional[Dict[str, object]]:
    """The recap rides the flash that is sent on a Monday morning.

    NRF weeks run Sunday..Saturday, so the week closes on Saturday and the
    first flash of the new week reports Sunday and is sent Monday. That flash —
    dow == 1 — carries the closed week and the gap-to-go for the new one.
    """
    if dow != 1:
        return None
    closed_end = day - dt.timedelta(days=1)          # the Saturday just gone
    closed = da.window_metrics(closed_end, "WTD")
    return {
        "edition": "Monday trade recap",
        "closed_week_start": closed["start"],
        "closed_week_end": closed["end"],
        "closed_week": closed,
        "gap_to_go": da.gap_to_go(day),
    }


# -- disclosures (every BR that touched this day, said out loud) -----------

def _disclosures(da, day: D, obj) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    comp = obj["comp"]

    if comp["override_in_effect"]:
        out.append({
            "rule": "BR-1",
            "text": "Holiday alignment in effect (%s). The comp above compares "
                    "%s with %s, the same holiday last year. The week-aligned "
                    "comparison (%s) reads %s and is shown for reference only."
                    % (_holiday_name(comp["holiday_code"]),
                       fmt.day_short_year(day),
                       fmt.day_short_year(comp["holiday_aligned"]["ly_date"]),
                       fmt.day_short_year(comp["week_aligned"]["ly_date"]),
                       fmt.pct(comp["week_aligned"]["pct"])),
        })
        ty_wd = fmt.WEEKDAYS[day.weekday()]
        ly_wd = fmt.WEEKDAYS[D.fromisoformat(
            comp["holiday_aligned"]["ly_date"]).weekday()]
        if ty_wd != ly_wd:
            out.append({
                "rule": "BR-1",
                "text": "Holiday alignment buys the holiday and gives up the "
                        "weekday: %s falls on a %s this year and a %s last "
                        "year, so part of the movement above is the weekday, "
                        "not the trade. The week-aligned figure keeps the "
                        "weekday and gives up the holiday. Both are shown "
                        "because neither is complete on its own."
                        % (_holiday_name(comp["holiday_code"]), ty_wd, ly_wd),
            })
    if comp["restated_53_week"]:
        out.append({
            "rule": "BR-8",
            "text": "53-week restatement in effect: the prior fiscal year's "
                    "weeks are shifted to the NRF restated calendar before "
                    "alignment.",
        })

    excluded = _comp_exclusions(da, day)
    if excluded["remodel"]:
        out.append({
            "rule": "BR-2",
            "text": "Excluded from comp on both sides — closed for remodel: %s."
                    % _names(da, excluded["remodel"]),
        })
    if excluded["immature"]:
        out.append({
            "rule": "BR-2",
            "text": "In total sales but not in comp — fewer than 13 full fiscal "
                    "periods of trading: %s." % _names(da, excluded["immature"]),
        })

    comp_ = obj["completeness"]
    if comp_["missing"]:
        out.append({
            "rule": "BR-3",
            "text": "%d of %d stores had not posted at generation time and are "
                    "MISSING, not zero: %s. Totals are reported-store figures; "
                    "no imputation."
                    % (len(comp_["missing"]), comp_["expected"],
                       ", ".join(comp_["missing_names"])),
        })
    for lp in comp_["escalating"]:
        out.append({
            "rule": "BR-3",
            "text": "ESCALATION — %s (%s) has not posted for %d consecutive "
                    "days (since %s). Ops action required."
                    % (lp["name"], lp["region"], lp["consecutive_days"],
                       fmt.day_short_year(lp["since"])),
        })

    ec = obj["ecom"]
    if ec:
        if obj["basis"] == "settled":
            out.append({
                "rule": "BR-4",
                "text": "E-commerce is on the SETTLED (shipped) basis in this "
                        "version; both years read shipped. The day-of flash "
                        "used demand.",
            })
        else:
            out.append({
                "rule": "BR-4",
                "text": "E-commerce comp is demand-based day-of (orders placed, "
                        "not shipped). Demand %s vs shipped %s; the day matures "
                        "after %d days and the archive shows both without "
                        "rewriting this flash."
                        % (fmt.money_compact(ec.get("demand")),
                           fmt.money_compact(ec.get("shipped")),
                           ec.get("settle_lag_days", 3)),
            })
        if not ec.get("matured", True):
            out.append({
                "rule": "BR-4",
                "text": "Settled return rate is computed on matured days only; "
                        "%s is not yet matured and is excluded from it."
                        % fmt.day_short_year(day),
            })

    out.append({
        "rule": "BR-5",
        "text": "Every figure on this flash is computed once in the metric "
                "catalog and rendered to all four surfaces from one object. "
                "Email, Slack, print and the archive cannot disagree.",
    })
    if obj["version"] > 1:
        out.append({
            "rule": "BR-7",
            "text": "This is version %d — a restatement. Version 1 is preserved "
                    "unchanged in the archive." % obj["version"],
        })
    return out


def _comp_exclusions(da, day: D) -> Dict[str, List[str]]:
    """Which open stores are out of the comp set today, and why (BR-2)."""
    remodel, immature = [], []
    members = set(da.comp_set(day))
    for e in da.entities():
        if e["channel"] != "STORE":
            continue
        eid = e["entity_id"]
        if eid in members:
            continue
        if da._in_remodel(e, day):
            remodel.append(eid)
        elif da.is_open_on(e, day) and not da.comp_eligible(eid, day):
            immature.append(eid)
    return {"remodel": sorted(remodel), "immature": sorted(immature)}


def _names(da, ids) -> str:
    return ", ".join("%s (%s, opened %s)"
                     % (da.entity(i)["name"], i,
                        fmt.day_short_year(da.entity(i)["open_date"]))
                     for i in ids)


def _holiday_name(code: Optional[str]) -> str:
    if not code:
        return ""
    return code.replace("_", " ").title().replace("July 4", "July 4")


# -- method notes (the formula key the email/print footer carries) ---------

def _method(obj) -> List[Dict[str, str]]:
    return [
        {"metric": "Net sales", "formula": "Σ net_sales over REPORTED entities "
         "(stores + e-commerce). A store that has not posted is excluded, "
         "never zero-filled."},
        {"metric": "Comp %", "formula": "(Σ comp-store TY ÷ Σ comp-store "
         "LY-aligned) − 1. LY-aligned = same fiscal week, same weekday; "
         "holiday codes override the week alignment."},
        {"metric": "Plan attainment", "formula": "Σ reported actual ÷ Σ plan for "
         "the same entities."},
        {"metric": "Contribution to comp gap", "formula": "(entity TY − entity "
         "LY-aligned) ÷ total comp LY-aligned. The focus panel's unit; named "
         "contributions plus 'all other' equal the headline gap exactly."},
        {"metric": "Completeness", "formula": "reported stores ÷ expected open "
         "stores; posted sales ÷ trailing-4 same-weekday average."},
        {"metric": "AOV / UPT / AUR", "formula": "net ÷ transactions, units ÷ "
         "transactions, net ÷ units."},
    ]


# -- display strings (BR-5, second half) -----------------------------------

def _display(obj) -> Dict[str, object]:
    h = obj["headline"]
    c = obj["comp"]
    cm = obj["completeness"]
    d = {
        "date_long": fmt.day_long(obj["date"]),
        "date_short": fmt.day_short(obj["date"]),
        "as_of": fmt.day_long(obj["as_of"]),
        "period_label": obj["calendar"]["period_label"],
        "week_label": "FY%d W%02d" % (obj["calendar"]["fiscal_year"],
                                      obj["calendar"]["week"]),
        "net_sales": fmt.money_compact(h["net_sales"]),
        "net_sales_exact": fmt.money_exact(h["net_sales"]),
        "comp_pct": fmt.pct(h["comp_pct"]),
        "comp_ly_date": fmt.day_short_year(c["ly_date"]),
        "comp_ty": fmt.money_exact(c["ty"]),
        "comp_ly": fmt.money_exact(c["ly"]),
        "comp_gap": fmt.money_signed(c["gap"]),
        "comp_gap_exact": fmt.money_exact(c["gap"]),
        "plan_attainment": fmt.pct_plain(h["plan_attainment"]),
        "plan": fmt.money_compact(h["plan"]),
        "plan_gap": fmt.money_signed(h["plan_gap"]),
        "transactions": fmt.count(h["transactions"]),
        "units": fmt.count(h["units"]),
        "aov": fmt.money_plain(h["aov"]),
        "upt": fmt.ratio(h["upt"]),
        "aur": fmt.money_plain(h["aur"]),
        "txn_comp": fmt.pct(h["comp_transactions"]["pct"]),
        "completeness": "%d of %d stores reported" % (cm["reported"], cm["expected"]),
        "completeness_pct": fmt.pct_plain(cm["pct"]),
        "posted_pct": fmt.pct_plain(cm["posted_pct"]),
        "comp_members": "%d comp entities" % c["members"],
        "week_aligned_pct": fmt.pct(c["week_aligned"]["pct"]),
        "week_aligned_ly_date": fmt.day_short_year(c["week_aligned"]["ly_date"]),
        "holiday_aligned_pct": (fmt.pct(c["holiday_aligned"]["pct"])
                                if c["holiday_aligned"] else None),
        "holiday_aligned_ly_date": (fmt.day_short_year(c["holiday_aligned"]["ly_date"])
                                    if c["holiday_aligned"] else None),
        "calendar_date_pct": (fmt.pct(c["calendar_date"]["pct"])
                              if c["calendar_date"] else None),
        "calendar_date_ly_date": (fmt.day_short_year(c["calendar_date"]["ly_date"])
                                  if c["calendar_date"] else None),
    }
    d["windows"] = {}
    for key, w in obj["windows"].items():
        d["windows"][key] = {
            "label": w["label"],
            "range": "%s – %s" % (fmt.day_short(w["start"]), fmt.day_short(w["end"])),
            "net_sales": fmt.money_compact(w["net_sales"]),
            "comp_pct": fmt.pct(w["comp_pct"]),
            "plan_attainment": fmt.pct_plain(w["plan_attainment"]),
            "days": str(w["days"]),
        }
    d["slices"] = {}
    for dim, rows in obj["slices"].items():
        d["slices"][dim] = [{
            "key": r["key"],
            "label": r["label"],
            "net_sales": fmt.money_compact(r["net_sales"]),
            "comp_pct": fmt.pct(r["comp_pct"]),
            "plan_attainment": fmt.pct_plain(r["plan_attainment"]),
            "comp_gap": fmt.money_signed(r["comp_gap"]),
            "coverage": "%d/%d" % (r["reported_entities"], r["open_entities"]),
        } for r in rows]
    d["focus"] = {
        "headline_gap": fmt.money_signed(obj["focus"]["headline_gap"]),
        "remainder": fmt.money_signed(obj["focus"]["remainder"]),
        "remainder_label": "All other (%d entities)" % obj["focus"]["remainder_count"],
        "entries": [_display_entry(e) for e in obj["focus"]["entries"]],
        "escalations": [
            "%s — no post for %d consecutive days (since %s)"
            % (e["label"], e["consecutive_days"], fmt.day_short_year(e["since"]))
            for e in obj["focus"]["escalations"] if e["escalate"]],
        "late": [
            "%s — not posted" % e["label"]
            for e in obj["focus"]["escalations"] if not e["escalate"]],
        "wtd_regions": [_display_region(r) for r in obj["focus"]["wtd_regions"]],
        "trailing_regions": [_display_region(r)
                             for r in obj["focus"]["trailing_regions"]],
        "trailing_label": "Trailing %d days (%s – %s)" % (
            obj["focus"]["trailing_days"],
            fmt.day_short(obj["focus"]["trailing_regions"][0]["start"]),
            fmt.day_short(obj["focus"]["trailing_regions"][0]["end"]))
        if obj["focus"]["trailing_regions"] else "",
    }
    ec = obj["ecom"]
    if ec:
        d["ecom"] = {
            "demand": fmt.money_compact(ec.get("demand")),
            "shipped": fmt.money_compact(ec.get("shipped")),
            "returns": fmt.money_compact(ec.get("returns")),
            "demand_comp": fmt.pct(ec.get("demand_comp_pct")),
            "shipped_comp": fmt.pct(ec.get("shipped_comp_pct")),
            "return_rate": fmt.pct_plain(ec.get("settled_return_rate")),
            "matured": "matured" if ec.get("matured") else "not yet matured",
            "basis": ec.get("basis_in_headline"),
        }
    if obj["recap"]:
        g = obj["recap"]["gap_to_go"]
        cw = obj["recap"]["closed_week"]
        d["recap"] = {
            "range": "%s – %s" % (fmt.day_short(cw["start"]), fmt.day_short(cw["end"])),
            "net_sales": fmt.money_compact(cw["net_sales"]),
            "comp_pct": fmt.pct(cw["comp_pct"]),
            "plan_attainment": fmt.pct_plain(cw["plan_attainment"]),
            "remaining_plan": fmt.money_compact(g["remaining_plan"]),
            "remaining_days": str(g["remaining_days"]),
            "run_rate": fmt.money_compact(g["required_run_rate"]),
            "period_label": g["period_label"],
        }
    return d


def _display_region(r) -> Dict[str, object]:
    return {
        "label": r["label"],
        "ty": fmt.money_compact(r["ty"]),
        "ly": fmt.money_compact(r["ly"]),
        "delta": fmt.money_signed(r["delta"]),
        "pct": fmt.pct(r["pct"]),
        "entities": str(r["entities"]),
        "adverse": r["delta"] < 0,
    }


def _display_entry(e) -> Dict[str, object]:
    return {
        "kind": e["kind"],
        "label": e["label"],
        "region": e["region"],
        "delta": fmt.money_signed(e["delta"]),
        "delta_exact": fmt.money_exact(e["delta"]),
        "pct": fmt.pct(e["pct"]),
        "share": fmt.pct(e["contribution"]),   # #15, in comp-% points
        "adverse": e["adverse"],
        "receipts": ["%s %s (%s)" % (r["name"], fmt.money_signed(r["delta"]),
                                     fmt.pct(r["pct"])) for r in e["receipts"]],
        "line": _entry_line(e),
    }


def _entry_line(e) -> str:
    """§6.4: one plain-English line with receipts."""
    head = "%s %s vs LY (%s)" % (e["label"], fmt.money_signed(e["delta"]),
                                 fmt.pct(e["pct"]))
    if e["kind"] == "region":
        head = "%s region %s vs LY (%s)" % (
            e["label"], fmt.money_signed(e["delta"]), fmt.pct(e["pct"]))
    if e["receipts"]:
        share = sum(abs(r["delta"]) for r in e["receipts"])
        total = abs(e["delta"]) or 1.0
        names = " and ".join(r["name"] for r in e["receipts"])
        head += " — %s drove %s of it" % (names, fmt.pct_plain(share / total, 0))
    elif e["region"] and e["kind"] == "store":
        head += " — %s" % e["region"]
    return head + "."


def _subject(obj) -> str:
    """PRD §8 subject-line convention, built from the same display strings the
    body prints — so the subject can never disagree with the flash."""
    d = obj["display"]
    return "Flash — %s · %s · comp %s · plan %s" % (
        d["date_short"], d["net_sales"], d["comp_pct"], d["plan_attainment"])


# -- invariants (NFR-4) -----------------------------------------------------

def _assert_invariants(obj, day) -> None:
    f = obj["focus"]
    check = round(sum(e["delta"] for e in f["entries"]) + f["remainder"], 2)
    if abs(check - f["headline_gap"]) > 0.005:
        raise AssertionError(
            "BR-6 broken on %s after object assembly: entries + remainder = %s "
            "but headline gap = %s. Fix in flash/focus.py — an entry's `covers` "
            "set overlaps another's." % (day, check, f["headline_gap"]))

    c = obj["comp"]
    if c["override_in_effect"]:
        if c["holiday_aligned"] is None:
            raise AssertionError(
                "BR-1 broken on %s: a holiday override is in effect but the "
                "holiday-aligned figure is missing. The adjusted comp must lead "
                "and the raw week-aligned comp must also be stated." % day)
        if c["pct"] != c["holiday_aligned"]["pct"]:
            raise AssertionError(
                "BR-1 broken on %s: the leading comp (%r) is not the "
                "holiday-aligned figure (%r). The adjusted number leads."
                % (day, c["pct"], c["holiday_aligned"]["pct"]))
    if c["week_aligned"] is None:
        raise AssertionError(
            "BR-1 broken on %s: the week-aligned comp is missing. A raw "
            "comparison may never appear without the aligned figure." % day)

    if obj["completeness"]["reported"] > obj["completeness"]["expected"]:
        raise AssertionError(
            "BR-3 broken on %s: %d reported stores exceeds %d expected."
            % (day, obj["completeness"]["reported"], obj["completeness"]["expected"]))

    sentences = [s for s in obj["narrative"].split(". ") if s.strip()]
    if len(sentences) > 3:
        raise AssertionError(
            "Narrative on %s runs to %d sentences; the owner default is at most "
            "3 (PRD §11). Trim flash/narrative.py." % (day, len(sentences)))
