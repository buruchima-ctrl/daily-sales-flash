# -*- coding: utf-8 -*-
"""Print surface — the trade-meeting handout, one page (PRD §8).

One page is the whole design constraint. A two-page handout gets stapled and
the second page never gets read, so everything that does not survive the cut is
dropped rather than shrunk: no formula key (it is on the email and the archive),
no trailing-region table, no window ranges. What stays is the headline, the
focus panel with its reconciliation, the region cut, and the disclosures —
because a handout that hides its caveats is the thing this product exists to
replace.

`@media print` sets Letter portrait with 0.5in margins and turns off the screen
chrome. On screen it renders as a preview of the printed page.

Same computed object, same display strings (BR-5).
"""

from __future__ import annotations

from html import escape as esc

CSS = """
:root{
  --paper:#FFFFFF; --ink:#1E2B38; --soft:#55636F; --rule:#C9C3B6;
  --gold:#8A6416; --blue:#2C5F8A; --calc:#2E7D5B; --bad:#A33A2A;
  --display:'Avenir Next',Avenir,'Segoe UI',Helvetica,sans-serif;
  --body:Charter,'Iowan Old Style',Georgia,serif;
  --data:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}
/* Every size below is set against a budget, not a taste: Letter portrait at
   0.5in margins leaves a 7.5 x 10in box, and 10in is 960px at 96dpi. The
   fullest day in the archive — 2026-07-23, which carries an incompleteness
   band, an escalation band and seven disclosures — has to fit inside that.
   Loosen any of these and check `.sheet` height at width:7.5in before
   shipping; a handout that silently spills onto a second page loses its
   disclosures, which are the half nobody would print on purpose. */
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#EEEBE4;color:var(--ink);
  font-family:var(--body);line-height:1.32;}
.sheet{width:8.5in;min-height:11in;margin:16px auto;padding:0.5in;
  background:var(--paper);box-shadow:0 1px 4px rgba(0,0,0,.18);}
h1{font-family:var(--display);font-size:17pt;font-weight:600;margin:0;line-height:1.15;}
.eyebrow{font-family:var(--display);font-size:7.5pt;letter-spacing:.13em;
  text-transform:uppercase;color:var(--soft);}
.meta{font-family:var(--data);font-size:7.5pt;color:var(--soft);margin-top:2px;}
hr{border:0;border-top:1.5pt solid var(--ink);margin:6px 0 8px;}
.tiles{display:table;width:100%;margin-bottom:8px;}
.tile{display:table-cell;width:33.33%;padding-right:12px;vertical-align:top;}
.tile .v{font-family:var(--data);font-size:18pt;font-weight:600;
  font-variant-numeric:tabular-nums;line-height:1.1;}
.tile .s{font-family:var(--data);font-size:7pt;color:var(--soft);}
.bad{color:var(--bad)} .good{color:var(--calc)}
.basket{font-family:var(--data);font-size:7.5pt;color:var(--soft);
  border-top:.5pt solid var(--rule);border-bottom:.5pt solid var(--rule);
  padding:3px 0;margin:0 0 7px;}
.basket b{font-family:var(--data);color:var(--ink);font-weight:600;
  font-variant-numeric:tabular-nums;}
.narr{font-size:9pt;line-height:1.38;margin:0 0 8px;}
.band{border-left:2.5pt solid var(--gold);background:#FAF4E6;padding:5px 7px;
  margin:0 0 6px;font-size:8pt;}
.band.alert{border-left-color:var(--bad);background:#FBEDEA;}
.band .t{font-family:var(--display);font-size:7pt;letter-spacing:.1em;
  text-transform:uppercase;font-weight:700;}
h2{font-family:var(--display);font-size:8pt;letter-spacing:.13em;
  text-transform:uppercase;color:var(--soft);font-weight:600;
  border-top:.75pt solid var(--rule);padding-top:4px;margin:7px 0 4px;}
table{width:100%;border-collapse:collapse;font-size:8pt;}
th{font-family:var(--display);font-size:7pt;letter-spacing:.07em;
  text-transform:uppercase;color:var(--soft);text-align:right;font-weight:600;
  padding:0 0 2px;border-bottom:.75pt solid var(--rule);}
th:first-child{text-align:left}
td{font-family:var(--data);font-variant-numeric:tabular-nums;text-align:right;
  padding:2px 0;border-bottom:.5pt solid var(--rule);}
td:first-child{font-family:var(--body);text-align:left}
ul.focus{list-style:none;margin:0;padding:0;font-size:8.5pt;}
ul.focus li{padding:2px 0;border-bottom:.5pt solid var(--rule);}
ul.focus .mk{font-weight:700;}
ul.focus .rc{font-family:var(--data);font-size:7pt;color:var(--soft);
  padding-left:12px;display:block;}
.recon{font-family:var(--data);font-size:7.5pt;color:var(--calc);padding-top:3px;}
.disc{font-size:7.5pt;line-height:1.3;color:var(--ink);margin:0 0 2px;}
.disc b{font-family:var(--data);color:var(--gold);font-weight:600;}
.foot{font-family:var(--data);font-size:7pt;color:var(--soft);
  border-top:.75pt solid var(--rule);margin-top:8px;padding-top:4px;}
.cols{display:table;width:100%;} .col{display:table-cell;width:50%;vertical-align:top;}
.col:first-child{padding-right:14px;}
@media print{
  @page{size:letter portrait;margin:0.5in;}
  html,body{background:#fff;}
  .sheet{width:auto;min-height:0;margin:0;padding:0;box-shadow:none;}
  .noprint{display:none}
}
"""


def render(obj) -> str:
    d = obj["display"]
    o = []
    a = o.append
    a('<!doctype html><html lang="en"><head><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<title>Flash one-pager — %s</title>' % esc(d["date_long"]))
    a('<style>%s</style></head><body><div class="sheet">' % CSS)

    a('<div class="eyebrow">%s · Daily Sales Flash · trade meeting handout</div>'
      % esc(obj["company"]))
    a('<h1>%s</h1>' % esc(d["date_long"]))
    a('<div class="meta">%s · fiscal %s · generated for the morning of %s%s</div>'
      % (esc(d["week_label"]), esc(d["period_label"]), esc(d["as_of"]),
         " · VERSION %d (restatement)" % obj["version"] if obj["version"] > 1 else ""))
    a('<hr>')

    comp_cls = "good" if (obj["headline"]["comp_pct"] or 0) >= 0 else "bad"
    plan_cls = "good" if (obj["headline"]["plan_attainment"] or 0) >= 1 else "bad"
    a('<div class="tiles">')
    a(_tile("Net sales", d["net_sales"], "", d["net_sales_exact"]))
    a(_tile("Comp %s" % obj["comp"]["basis"], d["comp_pct"], comp_cls,
            "vs %s · gap %s" % (d["comp_ly_date"], d["comp_gap"])))
    a(_tile("Plan attainment", d["plan_attainment"], plan_cls,
            "%s vs plan %s" % (d["plan_gap"], d["plan"])))
    a('</div>')

    if obj["comp"]["override_in_effect"]:
        a('<div class="band"><span class="t">Holiday alignment in effect</span><br>'
          'Leading comp %s is measured against %s, the same holiday last year. '
          'Raw week-aligned (%s) reads %s. The adjusted figure leads; both are '
          'stated.</div>'
          % (esc(d["comp_pct"]), esc(d["holiday_aligned_ly_date"]),
             esc(d["week_aligned_ly_date"]), esc(d["week_aligned_pct"])))
    if obj["completeness"]["missing"]:
        a('<div class="band alert"><span class="t">Incomplete — %s</span><br>'
          '%s had not posted. Excluded from totals and comp, never zeroed. '
          'Posted sales %s of the trailing-4 same-weekday average.</div>'
          % (esc(d["completeness"]),
             esc(", ".join(obj["completeness"]["missing_names"])),
             esc(d["posted_pct"])))
    for line in d["focus"]["escalations"]:
        a('<div class="band alert"><span class="t">Escalation to store operations'
          '</span><br>%s</div>' % esc(line))
    if obj["version"] > 1 and obj["reason"]:
        a('<div class="band"><span class="t">Restatement — version %d</span><br>%s</div>'
          % (obj["version"], esc(obj["reason"])))

    # Catalog metrics #7-#10 as one strip. A handout has one page, so the
    # basket travels as a line rather than a table — the numbers still have to
    # be here, because the trade meeting asks "was it traffic or was it spend?"
    a('<div class="basket">Transactions <b>%s</b> (comp %s) · units <b>%s</b> · '
      'AOV <b>%s</b> · UPT <b>%s</b> · AUR <b>%s</b></div>'
      % (esc(d["transactions"]), esc(d["txn_comp"]), esc(d["units"]),
         esc(d["aov"]), esc(d["upt"]), esc(d["aur"])))

    a('<p class="narr">%s</p>' % esc(obj["narrative"]))

    a('<h2>Focus — what moved it</h2><ul class="focus">')
    for e in d["focus"]["entries"]:
        cls = "bad" if e["adverse"] else "good"
        a('<li><span class="mk %s">%s</span> %s%s</li>'
          % (cls, "▼" if e["adverse"] else "▲", esc(e["line"]),
             "".join('<span class="rc">%s</span>' % esc(r) for r in e["receipts"])))
    a('<li>%s %s</li>' % (esc(d["focus"]["remainder_label"]),
                          esc(d["focus"]["remainder"])))
    a('</ul>')
    a('<div class="recon">Named contributions + all other = %s, the headline '
      'comp gap, to the cent (BR-6).</div>' % esc(d["focus"]["headline_gap"]))

    a('<div class="cols"><div class="col">')
    a('<h2>Week, period, year to date</h2>')
    a(_table(["", "Net sales", "Comp", "Plan"],
             [(d["windows"][k]["label"], d["windows"][k]["net_sales"],
               d["windows"][k]["comp_pct"], d["windows"][k]["plan_attainment"])
              for k in ("WTD", "MTD", "YTD")]))
    a('<h2>By channel</h2>')
    a(_table(["Channel", "Net sales", "Comp", "Posted"],
             [(r["label"], r["net_sales"], r["comp_pct"], r["coverage"])
              for r in d["slices"]["channel"]]))
    a('</div><div class="col">')
    a('<h2>By region</h2>')
    a(_table(["Region", "Net sales", "Comp", "Plan"],
             [(r["label"], r["net_sales"], r["comp_pct"], r["plan_attainment"])
              for r in d["slices"]["region"]]))
    a('</div></div>')

    if "recap" in d:
        r = d["recap"]
        a('<h2>Monday trade recap — week %s</h2>' % esc(r["range"]))
        a(_table(["Closed week", "Net sales", "Comp", "Plan"],
                 [("Week %s" % r["range"], r["net_sales"], r["comp_pct"],
                   r["plan_attainment"])]))
        a('<div class="recon">%s has %s of plan left across %s selling days — '
          '%s a day to make it.</div>'
          % (esc(r["period_label"]), esc(r["remaining_plan"]),
             esc(r["remaining_days"]), esc(r["run_rate"])))

    a('<h2>Disclosures</h2>')
    for item in obj["disclosures"]:
        a('<p class="disc"><b>%s</b> %s</p>' % (esc(item["rule"]), esc(item["text"])))

    a('<div class="foot">Every figure computed once in the metric catalog and '
      'rendered to email, Slack, print and the archive from one object (BR-5). '
      'Generated from seeded data for the morning of %s. Demo build.</div>'
      % esc(d["as_of"]))
    a('</div></body></html>')
    return "\n".join(o) + "\n"


def _tile(label, value, cls, sub) -> str:
    return ('<div class="tile"><div class="eyebrow">%s</div>'
            '<div class="v %s">%s</div><div class="s">%s</div></div>'
            % (esc(label), cls, esc(value), esc(sub)))


def _table(headers, rows) -> str:
    o = ["<table><tr>"]
    o += ["<th>%s</th>" % esc(h) for h in headers]
    o.append("</tr>")
    for row in rows:
        o.append("<tr>" + "".join(
            '<td class="%s">%s</td>'
            % ("bad" if isinstance(c, str) and c.startswith("−") else "", esc(str(c)))
            for c in row) + "</tr>")
    o.append("</table>")
    return "".join(o)
