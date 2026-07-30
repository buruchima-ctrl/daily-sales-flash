# -*- coding: utf-8 -*-
"""Slack surface — a plain-text block, paste-ready (PRD §8).

No markdown exotica. Slack's own renderer mangles tables, nested lists and
most of what looks clever in a preview, and the block gets pasted into threads
and forwarded into DMs where the formatting degrades again. So this is text
that reads correctly with zero rendering: fixed-width alignment, an em dash,
and nothing that changes meaning if the asterisks are stripped.

Same display strings as every other surface (BR-5).
"""

from __future__ import annotations

WIDTH = 62


def render(obj) -> str:
    d = obj["display"]
    L = []
    a = L.append

    a("%s — Daily Sales Flash" % obj["company"])
    a(d["date_long"] + ("  ·  VERSION %d (restatement)" % obj["version"]
                        if obj["version"] > 1 else ""))
    a("%s · fiscal %s · sent %s" % (d["week_label"], d["period_label"], d["as_of"]))
    a("")
    a(_rule())
    a("  Net sales     %s" % d["net_sales"])
    a("  Comp          %s   (%s, vs %s)"
      % (d["comp_pct"], obj["comp"]["basis"], d["comp_ly_date"]))
    a("  Plan          %s   (%s vs plan)" % (d["plan_attainment"], d["plan_gap"]))
    a("  Transactions  %s   (comp %s)" % (d["transactions"], d["txn_comp"]))
    a(_rule())
    a("")

    if obj["comp"]["override_in_effect"]:
        a("HOLIDAY ALIGNMENT — leading comp %s is against %s (same holiday last"
          % (d["comp_pct"], d["holiday_aligned_ly_date"]))
        a("year). Raw week-aligned (%s) reads %s. Adjusted leads; both stated."
          % (d["week_aligned_ly_date"], d["week_aligned_pct"]))
        a("")

    a(obj["narrative"])
    a("")

    a("FOCUS — what moved it")
    for e in d["focus"]["entries"]:
        a("  %s %s" % ("v" if e["adverse"] else "^", e["line"]))
        for r in e["receipts"]:
            a("      %s" % r)
    a("  · %s %s" % (d["focus"]["remainder_label"], d["focus"]["remainder"]))
    a("  Named + all other = %s, the headline comp gap, to the cent."
      % d["focus"]["headline_gap"])
    a("")

    for line in d["focus"]["escalations"]:
        a("ESCALATION — %s" % line)
    if d["focus"]["escalations"]:
        a("")

    a("COMPLETENESS")
    a("  %s (%s of expected). Posted sales %s of the trailing-4 same-weekday"
      % (d["completeness"], d["completeness_pct"], d["posted_pct"]))
    a("  average. Missing stores are excluded, never zeroed.")
    if obj["completeness"]["missing_names"]:
        a("  Not posted: %s" % ", ".join(obj["completeness"]["missing_names"]))
    a("")

    a("TO DATE")
    for key in ("WTD", "MTD", "YTD"):
        w = d["windows"][key]
        a("  %-4s %-19s %10s   comp %8s   plan %7s"
          % (key, w["range"], w["net_sales"], w["comp_pct"], w["plan_attainment"]))
    a("")

    a("BASKET")
    a("  Transactions  %-10s (comp %s)" % (d["transactions"], d["txn_comp"]))
    a("  Units         %-10s" % d["units"])
    a("  AOV           %-10s AUR %s · UPT %s" % (d["aov"], d["aur"], d["upt"]))
    a("")

    a("BY CHANNEL")
    for r in d["slices"]["channel"]:
        a("  %-14s %10s   comp %8s   plan %7s   posted %s"
          % (r["label"], r["net_sales"], r["comp_pct"], r["plan_attainment"],
             r["coverage"]))
    a("")

    a("BY REGION")
    for r in d["slices"]["region"]:
        a("  %-14s %10s   comp %8s   plan %7s   posted %s"
          % (r["label"], r["net_sales"], r["comp_pct"], r["plan_attainment"],
             r["coverage"]))
    a("")

    if "ecom" in d:
        e = d["ecom"]
        a("E-COMMERCE (BR-4)")
        a("  Demand %s (%s) · shipped %s (%s) · returns %s"
          % (e["demand"], e["demand_comp"], e["shipped"], e["shipped_comp"],
             e["returns"]))
        a("  Headline uses %s; this day is %s. Settled return rate %s."
          % (e["basis"], e["matured"], e["return_rate"]))
        a("")

    a(d["focus"]["trailing_label"].upper())
    for r in d["focus"]["trailing_regions"]:
        a("  %-14s LY %10s  TY %10s  %10s  %8s"
          % (r["label"], r["ly"], r["ty"], r["delta"], r["pct"]))
    a("")

    if "recap" in d:
        r = d["recap"]
        a("MONDAY TRADE RECAP — week %s" % r["range"])
        a("  Net %s · comp %s · plan %s"
          % (r["net_sales"], r["comp_pct"], r["plan_attainment"]))
        a("  %s: %s of plan left over %s selling days = %s a day."
          % (r["period_label"], r["remaining_plan"], r["remaining_days"],
             r["run_rate"]))
        a("")

    a("DISCLOSURES")
    for item in obj["disclosures"]:
        a(_wrap("  %s %s" % (item["rule"], item["text"])))
    a("")
    a("Generated from seeded data for the morning of %s. Demo build." % d["as_of"])
    return "\n".join(L) + "\n"


def _rule() -> str:
    return "  " + "-" * (WIDTH - 2)


def _wrap(text: str, width: int = WIDTH + 12, indent: str = "     ") -> str:
    """Hard-wrap without textwrap's paragraph reflow, so the output is stable
    across Python versions (NFR-2)."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = indent + w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        lines.append(cur)
    return "\n".join(lines)
