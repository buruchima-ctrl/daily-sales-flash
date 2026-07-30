# -*- coding: utf-8 -*-
"""Web archive surface — the fourth face of the same computed object (PRD §8).

What the archive is for, and what that forces:

  * **It is the evidence.** Email and Slack are the send; the archive is what
    FP&A comes back to in November to ask what the flash actually said on the
    morning of July 21. So a day page renders the ARCHIVED object — the JSON
    that was written when the flash was sent — never a fresh recompute. A page
    that recomputes is a page that can quietly change its mind (BR-7).
  * **Versions are pages, not states.** A restated day gets a second page and a
    history page that shows both side by side with the reason. Version 1 stays
    reachable at its own URL forever.
  * **Maturation is a second view, not an edit.** The BR-4 settled view lives
    at its own URL and says, in words, that the flash it is compared against is
    unchanged. Both are visible; neither overwrites the other.
  * **Navigation is fiscal.** Calendar months are the wrong unit for a retailer
    — a "month" boundary falls mid-week and the comparison the reader wants is
    the fiscal week. The index is a 4-5-4 week grid: fiscal year, period, week,
    Sunday through Saturday.

Design tokens are the portfolio's (PRD §8): **gold = an input**, **blue = a
presentation figure**, **green = calculated**; Avenir display, Charter body,
monospace for data. One stylesheet, linked relatively — every request this site
makes is to a file inside `render/site/` (NFR-5). No JS, no fonts, no images.

Like every other renderer this file prints `obj["display"]` strings and never
formats a number itself (BR-5).
"""

from __future__ import annotations

import datetime as dt
import os
from html import escape as esc
from typing import Dict, List, Optional

D = dt.date

WEEKDAY_HEADS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

# Formula strings shown on hover (PRD §5). Keyed by the label they annotate;
# the text is the catalog's own definition, not a paraphrase.
FORMULA = {
    "Net sales": "Σ net_sales over REPORTED entities (stores + e-commerce). "
                 "An unposted store is excluded, never zero-filled.",
    "Comp": "(Σ comp-store TY ÷ Σ comp-store LY-aligned) − 1. LY-aligned = "
            "same fiscal week, same weekday; holiday codes override.",
    "Plan attainment": "Σ reported actual ÷ Σ plan for the same entities.",
    "Transactions": "Count of transactions over reported entities; comp basis "
                    "as for comp sales.",
    "AOV": "net_sales ÷ transactions.",
    "UPT": "units ÷ transactions.",
    "AUR": "net_sales ÷ units.",
    "Contribution": "(entity TY − entity LY-aligned) ÷ total comp LY-aligned. "
                    "Named contributions + all other = the headline gap.",
    "Completeness": "reported stores ÷ expected open stores; posted sales ÷ "
                    "trailing-4 same-weekday average.",
    "Demand": "Σ ECOM demand_sales — orders placed on the day (BR-4).",
    "Shipped": "Σ ECOM shipped_sales — settled, available after the "
               "fulfillment lag (BR-4).",
    "Return rate": "returns ÷ shipped over the matured window only.",
    "Gap to go": "(period plan remaining) ÷ selling days remaining.",
}


# -- stylesheet (one file, linked relatively; no external requests) ---------

CSS = """/* Daily Sales Flash — web archive.
   Design tokens (PRD §8, the portfolio's language):
     --gold  an INPUT        something the business asserted (a plan, a date)
     --blue  a PRESENTATION  a figure being shown, not derived here
     --calc  a CALCULATION   something this system worked out
   Avenir display / Charter body / monospace data. No webfonts: every stack
   falls back through faces that ship with the OS, so the page renders offline
   and identically on a reviewer's machine. */
:root{
  --paper:#F7F5F0; --panel:#FFFFFF; --ink:#1E2B38; --soft:#55636F;
  --rule:#DCD7CC; --rule-soft:#EDEAE3;
  --gold:#8A6416; --gold-bg:#FBF4E4;
  --blue:#2C5F8A; --blue-bg:#EAF1F7;
  --calc:#2E7D5B; --calc-bg:#E9F3EE;
  --bad:#A33A2A; --bad-bg:#FBEDEA; --good:#2E7D5B;
  --display:'Avenir Next',Avenir,'Segoe UI',Helvetica,Arial,sans-serif;
  --body:Charter,'Iowan Old Style',Georgia,'Times New Roman',serif;
  --data:ui-monospace,'SF Mono',Menlo,Consolas,'Courier New',monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);
  font-size:16px;line-height:1.55;}
a{color:var(--blue);text-decoration:none;border-bottom:1px solid rgba(44,95,138,.35);}
a:hover{border-bottom-color:var(--blue)}
.wrap{max-width:960px;margin:0 auto;padding:20px 16px 64px;}
.wrap.narrow{max-width:760px}

header.top{border-bottom:2px solid var(--ink);padding-bottom:12px;margin-bottom:18px;}
.eyebrow{font-family:var(--display);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--soft);}
h1{font-family:var(--display);font-size:30px;font-weight:600;margin:6px 0 0;
  line-height:1.15;letter-spacing:-.01em;}
.meta{font-family:var(--data);font-size:12px;color:var(--soft);margin-top:6px;}
.crumbs{font-family:var(--display);font-size:12px;color:var(--soft);margin-bottom:14px;}
.crumbs a{border-bottom:none}

h2{font-family:var(--display);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--soft);font-weight:600;
  border-top:1px solid var(--rule);padding-top:12px;margin:26px 0 10px;}

.tiles{display:flex;flex-wrap:wrap;gap:12px;margin:4px 0 18px;}
.tile{flex:1 1 190px;background:var(--panel);border:1px solid var(--rule);
  padding:12px 14px;}
.tile .v{font-family:var(--data);font-size:27px;font-weight:600;line-height:1.15;
  font-variant-numeric:tabular-nums;padding-top:2px;}
.tile .s{font-family:var(--data);font-size:11px;color:var(--soft);padding-top:3px;}
.bad{color:var(--bad)} .good{color:var(--good)} .calc{color:var(--calc)}
.gold{color:var(--gold)} .blue{color:var(--blue)}

.band{border-left:3px solid var(--gold);background:var(--gold-bg);
  padding:10px 12px;margin:0 0 10px;font-size:14px;}
.band.alert{border-left-color:var(--bad);background:var(--bad-bg)}
.band.note{border-left-color:var(--blue);background:var(--blue-bg)}
.band.calcband{border-left-color:var(--calc);background:var(--calc-bg)}
.band .t{font-family:var(--display);font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;font-weight:700;display:block;}
.band .t.g{color:var(--gold)} .band .t.r{color:var(--bad)}
.band .t.b{color:var(--blue)} .band .t.c{color:var(--calc)}

.narr{font-size:17px;line-height:1.6;margin:2px 0 14px;}

.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;}
table{width:100%;border-collapse:collapse;font-size:14px;background:var(--panel);}
th{font-family:var(--display);font-size:10px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--soft);font-weight:600;text-align:right;
  padding:6px 8px;border-bottom:1px solid var(--rule);white-space:nowrap;}
th:first-child{text-align:left}
td{font-family:var(--data);font-variant-numeric:tabular-nums;text-align:right;
  padding:6px 8px;border-bottom:1px solid var(--rule-soft);white-space:nowrap;}
td:first-child{font-family:var(--body);text-align:left;white-space:normal}
tr:last-child td{border-bottom:1px solid var(--rule)}
th[title],td[title],.hint{cursor:help;border-bottom-style:dashed}

ul.focus{list-style:none;margin:0;padding:0;}
ul.focus li{padding:8px 0;border-bottom:1px solid var(--rule-soft);font-size:15px;}
ul.focus .mk{font-weight:700;padding-right:4px;}
ul.focus .rc{display:block;font-family:var(--data);font-size:12px;
  color:var(--soft);padding-left:18px;}
.recon{font-family:var(--data);font-size:12px;color:var(--calc);padding-top:8px;}

/* fiscal-week grid — the index's navigation (PRD §8: weeks, not months) */
.periodhead{font-family:var(--display);font-size:12px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--gold);font-weight:700;margin:22px 0 6px;}
table.cal{table-layout:fixed;font-size:13px;}
table.cal th{text-align:center}
table.cal th.wk{text-align:left;width:120px}
table.cal td{text-align:left;vertical-align:top;padding:0;white-space:normal;
  border:1px solid var(--rule-soft);height:74px;}
table.cal td.wk{font-family:var(--data);font-size:11px;color:var(--soft);
  padding:6px 8px;border-left:none;vertical-align:middle;}
.cell{display:block;padding:6px 7px;height:100%;border-bottom:none;}
a.cell:hover{background:var(--blue-bg);border-bottom:none}
.cell .dnum{font-family:var(--data);font-size:11px;color:var(--soft);}
.cell .amt{font-family:var(--data);font-size:14px;font-weight:600;
  font-variant-numeric:tabular-nums;display:block;padding-top:2px;color:var(--ink);}
.cell .cmp{font-family:var(--data);font-size:11px;display:block;}
.cell.empty{background:repeating-linear-gradient(135deg,transparent,
  transparent 5px,var(--rule-soft) 5px,var(--rule-soft) 6px);}
.flag{display:inline-block;font-family:var(--display);font-size:9px;
  letter-spacing:.06em;text-transform:uppercase;padding:0 3px;margin-top:2px;
  border:1px solid var(--gold);color:var(--gold);}
.flag.r{border-color:var(--bad);color:var(--bad)}
.flag.b{border-color:var(--blue);color:var(--blue)}

.cards{display:flex;flex-wrap:wrap;gap:10px;}
.card{flex:1 1 260px;background:var(--panel);border:1px solid var(--rule);
  padding:11px 13px;font-size:13px;}
.card .n{font-family:var(--display);font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--soft);font-weight:600;}
.card .h{font-family:var(--display);font-size:15px;font-weight:600;margin:2px 0 4px;}

.disc{font-size:13px;line-height:1.5;margin:0 0 7px;}
.disc b{font-family:var(--data);color:var(--gold);font-weight:600;
  font-size:12px;padding-right:3px;}
.key{font-family:var(--data);font-size:12px;line-height:1.5;color:var(--soft);
  margin:0 0 5px;}
.key b{color:var(--ink);font-weight:600}
.legend{font-family:var(--data);font-size:11px;color:var(--soft);
  border-top:1px solid var(--rule);padding-top:8px;margin-top:8px;}
.legend i{font-style:normal;font-weight:700}
footer{font-family:var(--data);font-size:11px;color:var(--soft);
  border-top:1px solid var(--rule);margin-top:26px;padding-top:10px;}
.pager{display:flex;justify-content:space-between;font-family:var(--display);
  font-size:13px;margin:18px 0 0;gap:12px;}
.surfaces{font-family:var(--display);font-size:12px;color:var(--soft);margin-top:8px}

@media (max-width:620px){
  h1{font-size:24px}
  .tile .v{font-size:22px}
  table.cal{min-width:640px}
}
"""


# -- page shell -------------------------------------------------------------

def _page(title: str, body: str, depth: int = 0, wrap_class: str = "") -> str:
    """Every page declares utf-8 (NFR-5 — the defect the lease review caught).

    `depth` is how many directories down the page sits, which is the whole of
    the link strategy: relative hrefs only, so the site works identically from
    `file://`, from `app.py`, and from a copied folder.
    """
    up = "../" * depth
    o = []
    a = o.append
    a('<!doctype html>')
    a('<html lang="en">')
    a('<head>')
    a('<meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<title>%s</title>' % esc(title))
    a('<link rel="stylesheet" href="%sassets/site.css">' % up)
    a('</head>')
    a('<body>')
    a('<div class="wrap%s">' % ((" " + wrap_class) if wrap_class else ""))
    a(body)
    a('</div>')
    a('</body>')
    a('</html>')
    return "\n".join(o) + "\n"


def _footer(extra: str = "") -> str:
    return ('<footer>%sEvery figure on this site is computed once in the metric '
            'catalog and rendered to email, Slack, print and this archive from '
            'one object (BR-5). Generated from seeded data; no live systems '
            'were queried. Demo build.</footer>' % (extra + " " if extra else ""))


def _legend() -> str:
    return ('<div class="legend">Colour tokens: <i class="gold">gold</i> = an '
            'input the business asserted · <i class="blue">blue</i> = a figure '
            'presented as given · <i class="calc">green</i> = calculated here. '
            'Dotted underline = hover for the formula.</div>')


def _band(kind: str, title: str, body_html: str) -> str:
    cls = {"gold": ("band", "g"), "alert": ("band alert", "r"),
           "note": ("band note", "b"), "calc": ("band calcband", "c")}[kind]
    return ('<div class="%s"><span class="t %s">%s</span>%s</div>'
            % (cls[0], cls[1], esc(title), body_html))


def _tile(label: str, value: str, cls: str, sub: str,
          formula: Optional[str] = None) -> str:
    lab = ('<span class="eyebrow hint" title="%s">%s</span>' % (esc(formula), esc(label))
           if formula else '<span class="eyebrow">%s</span>' % esc(label))
    return ('<div class="tile">%s<div class="v %s">%s</div>'
            '<div class="s">%s</div></div>'
            % (lab, cls, esc(value), esc(sub)))


def _table(headers, rows, titles=None) -> str:
    """`titles` is a parallel list of hover formulas for the header cells."""
    o = ['<div class="scroll"><table><tr>']
    for i, h in enumerate(headers):
        t = (titles[i] if titles and i < len(titles) else None)
        o.append('<th%s>%s</th>' % (' title="%s"' % esc(t) if t else "", esc(h)))
    o.append("</tr>")
    for row in rows:
        cells = []
        for c in row:
            s = "" if c is None else str(c)
            cls = "bad" if s.startswith("−") else ""
            cells.append('<td class="%s">%s</td>' % (cls, esc(s)))
        o.append("<tr>" + "".join(cells) + "</tr>")
    o.append("</table></div>")
    return "".join(o)


def _num_class(v, positive_is_good: bool = True, pivot: float = 0.0) -> str:
    if v is None:
        return ""
    return "good" if (v >= pivot) == positive_is_good else "bad"


# -- the day page -----------------------------------------------------------

def render_day(obj, nav: Optional[Dict[str, object]] = None) -> str:
    """One archived flash, on the web. `nav` carries only links — never data,
    so the page cannot say anything the archived object does not."""
    nav = nav or {}
    d = obj["display"]
    o = []
    a = o.append
    stem = nav.get("stem") or obj["date"]
    is_restatement = obj["version"] > 1

    a('<div class="crumbs"><a href="%s">← Flash archive</a></div>'
      % esc(str(nav.get("index_href") or "../index.html")))
    a('<header class="top">')
    a('<div class="eyebrow">%s · Daily Sales Flash%s</div>'
      % (esc(obj["company"]),
         " · version %d (restatement)" % obj["version"] if is_restatement else ""))
    a('<h1>%s</h1>' % esc(d["date_long"]))
    a('<div class="meta">%s · fiscal %s · week %d · sent the morning of %s · '
      'archived version %d</div>'
      % (esc(d["week_label"]), esc(d["period_label"]), obj["calendar"]["week"],
         esc(d["as_of"]), obj["version"]))
    a('<div class="surfaces">Same numbers, other surfaces: '
      '<a href="../../email/%s.html">email</a> · '
      '<a href="../../print/%s.html">print one-pager</a> · '
      '<a href="../../slack/%s.txt">Slack block</a>%s%s</div>'
      % (esc(stem), esc(stem), esc(stem),
         ' · <a href="%s">version history</a>' % esc(str(nav["history"]))
         if nav.get("history") else "",
         ' · <a href="%s">settled (BR-4) view</a>' % esc(str(nav["settled"]))
         if nav.get("settled") else ""))
    a('</header>')

    if nav.get("live_note"):
        a(_band("calc", "Generated on demand", "<div>%s</div>"
                % esc(str(nav["live_note"]))))
    a(_day_versions_bar(obj, nav))
    a(_day_tiles(obj, d))
    a(_day_banners(obj, d, nav))
    a('<p class="narr">%s</p>' % esc(obj["narrative"]))
    a(_day_focus(obj, d))
    a(_day_windows(d))
    a(_day_basket(d))
    a(_day_slices(d))
    a(_day_ecom(obj, d, nav))
    a(_day_trailing(d))
    a(_day_recap(d))
    a(_day_disclosures(obj))
    a(_day_method(obj))
    a(_legend())
    a(_pager(nav))
    a(_footer())
    return _page("Flash — %s%s" % (d["date_long"],
                                  " (v%d)" % obj["version"] if is_restatement else ""),
                 "\n".join(o), depth=1)


def _day_versions_bar(obj, nav) -> str:
    vs = nav.get("versions") or []
    if len(vs) < 2:
        return ""
    bits = []
    for v in vs:
        label = "version %d%s" % (v["version"],
                                  " (as sent)" if v["version"] == 1 else " (restatement)")
        if v["version"] == obj["version"]:
            bits.append("<b>%s — you are here</b>" % esc(label))
        else:
            bits.append('<a href="%s">%s</a>' % (esc(str(v["href"])), esc(label)))
    return _band("note", "This day has been restated (BR-7)",
                 '<div>%s</div><div class="key" style="padding-top:4px;">'
                 'Every version keeps its own URL. Nothing was overwritten; '
                 '<a href="%s">the history page</a> shows both side by side.</div>'
                 % (" &nbsp;·&nbsp; ".join(bits), esc(str(nav.get("history", "")))))


def _day_tiles(obj, d) -> str:
    h = obj["headline"]
    return ('<div class="tiles">%s%s%s</div>' % (
        _tile("Net sales", d["net_sales"], "", d["net_sales_exact"],
              FORMULA["Net sales"]),
        _tile("Comp %s" % obj["comp"]["basis"], d["comp_pct"],
              _num_class(h["comp_pct"]), "vs %s · gap %s"
              % (d["comp_ly_date"], d["comp_gap"]), FORMULA["Comp"]),
        _tile("Plan attainment", d["plan_attainment"],
              _num_class(h["plan_attainment"], pivot=1.0),
              "%s vs plan %s" % (d["plan_gap"], d["plan"]),
              FORMULA["Plan attainment"])))


def _day_banners(obj, d, nav) -> str:
    o = []
    c = obj["comp"]
    if c["override_in_effect"]:
        o.append(_band(
            "gold", "Holiday alignment in effect (BR-1)",
            "<div>The leading comp %s is measured against %s — the same holiday "
            "last year. The raw week-aligned comparison (%s) reads %s, and the "
            "same-calendar-date comparison the old spreadsheet printed reads %s. "
            "The adjusted figure leads; all three are stated.</div>"
            % (esc(d["comp_pct"]), esc(str(d["holiday_aligned_ly_date"])),
               esc(str(d["week_aligned_ly_date"])), esc(str(d["week_aligned_pct"])),
               esc(str(d["calendar_date_pct"])))))
    if obj["completeness"]["missing"]:
        o.append(_band(
            "alert", "Incomplete — %s" % d["completeness"],
            "<div>%s had not posted at generation time. Missing stores are "
            "excluded from totals and from comp, never counted as zero (BR-3). "
            "Posted sales are %s of the trailing-4 same-weekday average.</div>"
            % (esc(", ".join(obj["completeness"]["missing_names"])),
               esc(d["posted_pct"]))))
    for line in d["focus"]["escalations"]:
        o.append(_band("alert", "Escalation to store operations (BR-3)",
                       "<div>%s</div>" % esc(line)))
    if obj["version"] > 1 and obj["reason"]:
        o.append(_band("note", "Restatement — version %d (BR-7)" % obj["version"],
                       "<div>%s</div>" % esc(obj["reason"])))
    if nav.get("settled"):
        o.append(_band(
            "calc", "E-commerce matured after this flash was sent (BR-4)",
            '<div>This page is the flash exactly as sent, on the day-of demand '
            'basis. The settled (shipped) figures arrived later and are shown '
            'in a <a href="%s">separate settled view</a> — this flash is not '
            'rewritten.</div>' % esc(str(nav["settled"]))))
    return "".join(o)


def _day_focus(obj, d) -> str:
    f = d["focus"]
    o = ['<h2>Focus — what moved it</h2>', '<ul class="focus">']
    for e in f["entries"]:
        cls = "bad" if e["adverse"] else "good"
        o.append('<li><span class="mk %s">%s</span>%s%s'
                 '<span class="rc">contribution to comp %s · %s vs LY</span></li>'
                 % (cls, "▼" if e["adverse"] else "▲", esc(e["line"]),
                    "".join('<span class="rc">%s</span>' % esc(r)
                            for r in e["receipts"]),
                    esc(e["share"]), esc(e["delta_exact"])))
    o.append('<li>%s <span class="mk">%s</span></li>'
             % (esc(f["remainder_label"]), esc(f["remainder"])))
    o.append('</ul>')
    o.append('<div class="recon hint" title="%s">Named contributions + all other '
             '= %s, the headline comp gap, to the cent (BR-6). TY %s − LY %s = '
             '%s.</div>'
             % (esc(FORMULA["Contribution"]), esc(f["headline_gap"]),
                esc(d["comp_ty"]), esc(d["comp_ly"]), esc(d["comp_gap_exact"])))
    return "".join(o)


def _day_windows(d) -> str:
    rows = [(d["windows"][k]["label"], d["windows"][k]["range"],
             d["windows"][k]["days"], d["windows"][k]["net_sales"],
             d["windows"][k]["comp_pct"], d["windows"][k]["plan_attainment"])
            for k in ("WTD", "MTD", "YTD")]
    return ('<h2>Week, period, year to date</h2>'
            + _table(["", "Range", "Days", "Net sales", "Comp", "Plan"], rows,
                     [None, None, None, FORMULA["Net sales"], FORMULA["Comp"],
                      FORMULA["Plan attainment"]]))


def _day_basket(d) -> str:
    """Catalog metrics #7-#10. The formula key on this page names AOV / UPT /
    AUR, so the page has to show them — a key that documents a row the reader
    cannot find is the same broken promise as a number with no formula."""
    rows = [
        ("Transactions", d["transactions"], d["txn_comp"]),
        ("Units", d["units"], ""),
        ("AOV — average order value", d["aov"], ""),
        ("UPT — units per transaction", d["upt"], ""),
        ("AUR — average unit retail", d["aur"], ""),
    ]
    return ('<h2>Basket — transactions, AOV, UPT, AUR</h2>'
            + _table(["", "Day", "vs LY"], rows,
                     [None, FORMULA["Transactions"], FORMULA["Comp"]]))


def _day_slices(d) -> str:
    o = ['<h2>By channel</h2>']
    o.append(_table(["Channel", "Posted", "Net sales", "Comp", "Comp gap", "Plan"],
                    [(r["label"], r["coverage"], r["net_sales"], r["comp_pct"],
                      r["comp_gap"], r["plan_attainment"])
                     for r in d["slices"]["channel"]],
                    [None, FORMULA["Completeness"], FORMULA["Net sales"],
                     FORMULA["Comp"], FORMULA["Contribution"],
                     FORMULA["Plan attainment"]]))
    o.append('<h2>By region</h2>')
    o.append(_table(["Region", "Posted", "Net sales", "Comp", "Comp gap", "Plan"],
                    [(r["label"], r["coverage"], r["net_sales"], r["comp_pct"],
                      r["comp_gap"], r["plan_attainment"])
                     for r in d["slices"]["region"]],
                    [None, FORMULA["Completeness"], FORMULA["Net sales"],
                     FORMULA["Comp"], FORMULA["Contribution"],
                     FORMULA["Plan attainment"]]))
    return "".join(o)


def _day_ecom(obj, d, nav) -> str:
    if "ecom" not in d:
        return ""
    e = d["ecom"]
    rows = [("Demand (ordered)", e["demand"], e["demand_comp"]),
            ("Shipped (settled)", e["shipped"], e["shipped_comp"]),
            ("Returns recorded", e["returns"], ""),
            ("Settled return rate (matured window)", e["return_rate"], "")]
    note = ('The headline uses %s. This day is %s — it settles after %d days. '
            'The archive shows both series without rewriting this flash (BR-4).'
            % (e["basis"], e["matured"], obj["ecom"].get("settle_lag_days", 3)))
    return ('<h2>E-commerce — demand vs shipped</h2>'
            + _table(["", "Amount", "vs LY"], rows,
                     [None, FORMULA["Demand"], FORMULA["Comp"]])
            + '<div class="key">%s</div>' % esc(note))


def _day_trailing(d) -> str:
    if not d["focus"]["trailing_regions"]:
        return ""
    return ('<h2>%s</h2>' % esc(d["focus"]["trailing_label"])
            + _table(["Region", "LY", "TY", "Δ", "%", "Doors"],
                     [(r["label"], r["ly"], r["ty"], r["delta"], r["pct"],
                       r["entities"]) for r in d["focus"]["trailing_regions"]],
                     [None, None, None, FORMULA["Contribution"], FORMULA["Comp"],
                      None]))


def _day_recap(d) -> str:
    if "recap" not in d:
        return ""
    r = d["recap"]
    return ('<h2>Monday trade recap — the week that closed</h2>'
            + _table(["Closed week", "Net sales", "Comp", "Plan"],
                     [("Week %s" % r["range"], r["net_sales"], r["comp_pct"],
                       r["plan_attainment"])],
                     [None, FORMULA["Net sales"], FORMULA["Comp"],
                      FORMULA["Plan attainment"]])
            + '<div class="recon hint" title="%s">%s has %s of plan left across '
              '%s selling days — %s a day to make it.</div>'
              % (esc(FORMULA["Gap to go"]), esc(r["period_label"]),
                 esc(r["remaining_plan"]), esc(r["remaining_days"]),
                 esc(r["run_rate"])))


def _day_disclosures(obj) -> str:
    o = ['<h2>Disclosures</h2>']
    for item in obj["disclosures"]:
        o.append('<p class="disc"><b>%s</b>%s</p>'
                 % (esc(item["rule"]), esc(item["text"])))
    return "".join(o)


def _day_method(obj) -> str:
    o = ['<h2>Formula key</h2>']
    for m in obj["method"]:
        o.append('<p class="key"><b>%s</b> — %s</p>'
                 % (esc(m["metric"]), esc(m["formula"])))
    return "".join(o)


def _pager(nav) -> str:
    prev = ('<a href="%s">← %s</a>' % (esc(str(nav["prev_href"])), esc(str(nav["prev_label"])))
            if nav.get("prev_href") else "<span></span>")
    nxt = ('<a href="%s">%s →</a>' % (esc(str(nav["next_href"])), esc(str(nav["next_label"])))
           if nav.get("next_href") else "<span></span>")
    return '<div class="pager">%s%s</div>' % (prev, nxt)


# -- the settled view (BR-4) ------------------------------------------------

def _rows_compare(left, right, left_label, right_label):
    """The comparison rows two versions/views of a day are judged on."""
    dl, dr = left["display"], right["display"]
    rows = [
        ("Net sales", dl["net_sales"], dr["net_sales"],
         _delta(left["headline"]["net_sales"], right["headline"]["net_sales"])),
        ("Comp %", dl["comp_pct"], dr["comp_pct"],
         _delta_pct(left["headline"]["comp_pct"], right["headline"]["comp_pct"])),
        ("Comp gap vs LY", dl["comp_gap"], dr["comp_gap"],
         _delta(left["comp"]["gap"], right["comp"]["gap"])),
        ("Plan attainment", dl["plan_attainment"], dr["plan_attainment"],
         _delta_pct(left["headline"]["plan_attainment"],
                    right["headline"]["plan_attainment"])),
        ("E-commerce in the headline",
         dl.get("ecom", {}).get("basis", "—"), dr.get("ecom", {}).get("basis", "—"), ""),
        ("E-commerce demand (ordered)",
         dl.get("ecom", {}).get("demand", "—"), dr.get("ecom", {}).get("demand", "—"), ""),
        ("E-commerce shipped (settled)",
         dl.get("ecom", {}).get("shipped", "—"), dr.get("ecom", {}).get("shipped", "—"), ""),
        ("E-commerce comp used",
         dl.get("ecom", {}).get("demand_comp", "—"),
         dr.get("ecom", {}).get("shipped_comp", "—"), ""),
        ("Stores in comp", dl["comp_members"], dr["comp_members"], ""),
    ]
    return ["", left_label, right_label, "Δ"], rows


def _delta(a_val, b_val) -> str:
    from flash import fmt
    if a_val is None or b_val is None:
        return ""
    return fmt.money_signed(round(b_val - a_val, 2))


def _delta_pct(a_val, b_val) -> str:
    from flash import fmt
    if a_val is None or b_val is None:
        return ""
    return "%s pts" % fmt.pct(round(b_val - a_val, 6))


def render_settled(flash_obj, settled_obj, nav: Optional[Dict[str, object]] = None) -> str:
    """The BR-4 maturation view: the sent flash and the settled restatement of
    the same day, side by side, with the sent flash explicitly unchanged."""
    nav = nav or {}
    d = flash_obj["display"]
    o = []
    a = o.append
    a('<div class="crumbs"><a href="../index.html">← Flash archive</a> · '
      '<a href="../day/%s.html">the flash as sent</a></div>' % esc(flash_obj["date"]))
    a('<header class="top">')
    a('<div class="eyebrow">%s · E-commerce maturation · BR-4</div>'
      % esc(flash_obj["company"]))
    a('<h1>%s — settled vs flash</h1>' % esc(d["date_long"]))
    a('<div class="meta">Flash sent %s on the demand basis · settled figures '
      'available after the %d-day fulfillment lag</div>'
      % (esc(d["as_of"]), flash_obj["ecom"].get("settle_lag_days", 3)))
    a('</header>')

    a(_band("note", "The flash is not rewritten",
            '<div>The flash for %s remains <b>version %d</b>, exactly as it was '
            'sent: net sales %s, comp %s, e-commerce on the day-of demand '
            'basis. This page is a <b>second view</b> of the same day computed '
            'on the settled (shipped) basis, published alongside it. Neither '
            'replaces the other, and the archived object behind the sent flash '
            'is byte-for-byte what it was on the send morning (BR-4, BR-7).'
            '</div>'
            % (esc(d["date_short"]), flash_obj["version"],
               esc(d["net_sales"]), esc(d["comp_pct"]))))

    a('<h2>The same day, two bases</h2>')
    heads, rows = _rows_compare(flash_obj, settled_obj,
                                "Flash as sent (demand)", "Settled (shipped)")
    a(_table(heads, rows, [None, FORMULA["Demand"], FORMULA["Shipped"], None]))

    ec = flash_obj["ecom"]
    se = settled_obj["ecom"]
    a('<div class="key">Demand read %s vs LY on the send morning; the shipped '
      'series for the same day settled at %s. Both series existed all along — '
      'BR-4 keeps them distinct rather than letting one silently become the '
      'other.</div>'
      % (esc(d["ecom"]["demand_comp"]),
         esc(settled_obj["display"]["ecom"]["shipped_comp"])))

    a('<h2>The e-commerce series in full</h2>')
    a(_table(["Series", "This year", "Last year", "vs LY"],
             [("Demand (ordered)", d["ecom"]["demand"],
               _money(ec.get("ly_demand")), d["ecom"]["demand_comp"]),
              ("Shipped (settled)", d["ecom"]["shipped"],
               _money(ec.get("ly_shipped")), d["ecom"]["shipped_comp"]),
              ("Returns recorded", d["ecom"]["returns"], "", ""),
              ("Settled return rate (matured window)",
               d["ecom"]["return_rate"], "", "")],
             [None, None, None, FORMULA["Comp"]]))
    a('<div class="key">Maturity at send time: <b>%s</b>. Settle lag %d days. '
      'The settled view above is computed with the same catalog functions on '
      'the settled basis — one formula home, two bases (BR-5).</div>'
      % (esc(d["ecom"]["matured"]), ec.get("settle_lag_days", 3)))

    a('<h2>What each version discloses</h2>')
    a('<div class="cards">')
    for title, ob in (("Flash as sent (demand basis)", flash_obj),
                      ("Settled view (shipped basis)", settled_obj)):
        items = "".join('<p class="disc"><b>%s</b>%s</p>'
                        % (esc(x["rule"]), esc(x["text"]))
                        for x in ob["disclosures"] if x["rule"] == "BR-4")
        a('<div class="card"><div class="n">%s</div>%s</div>' % (esc(title), items))
    a('</div>')

    a('<div class="pager"><a href="../day/%s.html">← the flash as sent</a>'
      '<a href="../index.html">archive index →</a></div>' % esc(flash_obj["date"]))
    a(_legend())
    a(_footer())
    return _page("Settled vs flash — %s" % d["date_long"], "\n".join(o),
                 depth=1, wrap_class="narrow")


def _money(v) -> str:
    from flash import fmt
    return fmt.money_compact(v) if v is not None else ""


# -- version history (BR-7) -------------------------------------------------

def render_history(versions: List[dict]) -> str:
    """Every version of one day, oldest first, with the reason each was issued."""
    v1 = versions[0]["obj"]
    d1 = v1["display"]
    o = []
    a = o.append
    a('<div class="crumbs"><a href="../index.html">← Flash archive</a> · '
      '<a href="%s.html">version 1</a></div>' % esc(v1["date"]))
    a('<header class="top">')
    a('<div class="eyebrow">%s · Restatement history · BR-7</div>' % esc(v1["company"]))
    a('<h1>%s — version history</h1>' % esc(d1["date_long"]))
    a('<div class="meta">%d versions in the archive · version 1 is preserved '
      'exactly as sent</div>' % len(versions))
    a('</header>')

    a(_band("note", "Corrections are versions, never edits",
            '<div>A flash is immutable once sent. When a figure changes, the '
            'archive appends a new version with a reason; the original stays '
            'at its own URL and its own timestamp. That is the whole of BR-7, '
            'and it is why this page can exist.</div>'))

    a('<h2>Versions</h2>')
    rows = []
    for v in versions:
        ob = v["obj"]
        rows.append((
            "Version %d%s" % (v["version"],
                              " — as sent" if v["version"] == 1 else " — restatement"),
            ob["display"]["net_sales"], ob["display"]["comp_pct"],
            ob["display"]["plan_attainment"],
            ob["ecom"].get("basis_in_headline", "—") if ob.get("ecom") else "—",
            v["created_at"]))
    a(_table(["", "Net sales", "Comp", "Plan", "E-comm basis", "Written at"], rows,
             [None, FORMULA["Net sales"], FORMULA["Comp"],
              FORMULA["Plan attainment"], None, None]))

    for v in versions[1:]:
        a('<h2>Why version %d was issued</h2>' % v["version"])
        a('<p class="narr">%s</p>' % esc(v["reason"] or v["obj"].get("reason") or ""))

    if len(versions) >= 2:
        a('<h2>Version %d vs version %d, figure by figure</h2>'
          % (versions[0]["version"], versions[-1]["version"]))
        heads, rows = _rows_compare(
            versions[0]["obj"], versions[-1]["obj"],
            "Version %d" % versions[0]["version"],
            "Version %d" % versions[-1]["version"])
        a(_table(heads, rows, [None, None, None, None]))

    a('<h2>Read either version in full</h2>')
    a('<div class="cards">')
    for v in versions:
        href = "%s.html" % v["obj"]["date"] if v["version"] == 1 else \
               "%s-v%d.html" % (v["obj"]["date"], v["version"])
        a('<div class="card"><div class="n">Version %d</div>'
          '<div class="h"><a href="%s">%s</a></div>'
          '<div>Written %s. Narrative: %s</div></div>'
          % (v["version"], esc(href), esc(v["obj"]["display"]["date_long"]),
             esc(v["created_at"]), esc(v["obj"]["narrative"])))
    a('</div>')

    a('<div class="pager"><a href="%s.html">← version 1, as sent</a>'
      '<a href="../index.html">archive index →</a></div>' % esc(v1["date"]))
    a(_legend())
    a(_footer())
    return _page("Version history — %s" % d1["date_long"], "\n".join(o),
                 depth=1, wrap_class="narrow")


# -- the index: a fiscal-week grid (PRD §8) ---------------------------------

def render_index(days: List[dict], storylines: Optional[List[dict]] = None,
                 today: Optional[str] = None) -> str:
    """The archive front door.

    Navigation is by **fiscal week**, not calendar month. A retailer's week is
    the unit that compares — Sunday to Saturday, inside a 4-5-4 period — and a
    calendar month cuts three of them in half. The grid below is therefore a
    fiscal-period stack of fiscal weeks; the calendar date is the small print
    inside each cell.
    """
    o = []
    a = o.append
    latest = days[-1]["versions"][0]["obj"] if days else None
    first = days[0]["versions"][0]["obj"] if days else None

    a('<header class="top">')
    a('<div class="eyebrow">%s · Daily Sales Flash</div>'
      % esc(latest["company"] if latest else "Lumière Beauty Co."))
    a('<h1>Flash archive</h1>')
    if latest and first:
        a('<div class="meta">%d days · %s through %s · fiscal %s–%s · '
          'every flash exactly as it was sent</div>'
          % (len(days), esc(first["display"]["date_long"]),
             esc(latest["display"]["date_long"]),
             esc(first["display"]["week_label"]),
             esc(latest["display"]["week_label"])))
    a('</header>')

    if latest:
        d = latest["display"]
        a('<h2>Latest complete day</h2>')
        a('<div class="tiles">%s%s%s</div>' % (
            _tile("Net sales", d["net_sales"], "", d["net_sales_exact"],
                  FORMULA["Net sales"]),
            _tile("Comp %s" % latest["comp"]["basis"], d["comp_pct"],
                  _num_class(latest["headline"]["comp_pct"]),
                  "vs %s" % d["comp_ly_date"], FORMULA["Comp"]),
            _tile("Plan attainment", d["plan_attainment"],
                  _num_class(latest["headline"]["plan_attainment"], pivot=1.0),
                  d["plan_gap"], FORMULA["Plan attainment"])))
        a('<p class="narr">%s</p>' % esc(latest["narrative"]))
        # `../email/…` is deliberate: from the disk it walks up to render/, and
        # served by app.py (where the site IS the root) the browser clamps the
        # leading `..` and lands on the /email/ alias. One href, both worlds.
        a('<div class="surfaces">Read it: <a href="day/%s.html">web</a> · '
          '<a href="../email/%s.html">email</a> · '
          '<a href="../print/%s.html">print</a> · '
          '<a href="../slack/%s.txt">Slack</a></div>'
          % tuple([esc(latest["date"])] * 4))
        if today:
            a('<div class="key">Generate-on-demand: with <code>app.py</code> '
              'running, <a href="today">/today</a> recomputes the flash for the '
              'latest complete day (%s) live from the database as it would be '
              'sent on the morning of %s. The demo clock is fixed there; '
              'nothing in this system calls the wall clock (NFR-2).</div>'
              % (esc(latest["display"]["date_short"]), esc(today)))

    if storylines:
        a('<h2>Planted storylines — where to see each one</h2>')
        a('<div class="cards">')
        for s in storylines:
            link = ('<a href="%s">%s</a>' % (esc(s["href"]), esc(s["where"]))
                    if s.get("href") else esc(s["where"]))
            a('<div class="card"><div class="n">Storyline %s · %s</div>'
              '<div class="h">%s</div><div>%s</div>'
              '<div class="key" style="padding-top:4px;">%s</div></div>'
              % (esc(str(s["n"])), esc(s["rule"]), esc(s["title"]),
                 esc(s["note"]), link))
        a('</div>')

    a('<h2>The archive, by fiscal week</h2>')
    a('<div class="key">NRF 4-5-4: weeks run Sunday to Saturday and periods '
      'group 4-5-4 inside a quarter. Calendar months are not a navigation unit '
      'here — they cut the comparison the reader actually wants.</div>')
    a(_calendar_grid(days))

    a(_legend())
    a(_footer())
    return _page("Daily Sales Flash — archive", "\n".join(o), depth=0)


def _calendar_grid(days: List[dict]) -> str:
    by_key: Dict[tuple, List[dict]] = {}
    order: List[tuple] = []
    for entry in days:
        ob = entry["versions"][0]["obj"]
        cal = ob["calendar"]
        key = (cal["fiscal_year"], cal["period"], cal["week"])
        if key not in by_key:
            by_key[key] = []
            order.append(key)
        by_key[key].append(entry)

    periods: List[tuple] = []
    for key in order:
        p = key[:2]
        if not periods or periods[-1][0] != p:
            periods.append((p, [key]))
        else:
            periods[-1][1].append(key)

    o = []
    for (fy, period), weeks in periods:
        label = by_key[weeks[0]][0]["versions"][0]["obj"]["calendar"]["period_label"]
        o.append('<div class="periodhead">Fiscal year %d · period %d · %s</div>'
                 % (fy, period, esc(label)))
        o.append('<div class="scroll"><table class="cal"><tr>')
        o.append('<th class="wk">Fiscal week</th>')
        for h in WEEKDAY_HEADS:
            o.append('<th>%s</th>' % h)
        o.append('</tr>')
        for key in weeks:
            entries = {e["versions"][0]["obj"]["calendar"]["day_of_week"]: e
                       for e in by_key[key]}
            o.append('<tr><td class="wk">FY%d W%02d<br>%s</td>'
                     % (key[0], key[2], esc(_week_range(by_key[key]))))
            for dow in range(1, 8):
                o.append(_cell(entries.get(dow)))
            o.append('</tr>')
        o.append('</table></div>')
    return "".join(o)


def _week_range(entries: List[dict]) -> str:
    from flash import fmt
    firstd = entries[0]["versions"][0]["obj"]["date"]
    lastd = entries[-1]["versions"][0]["obj"]["date"]
    if firstd == lastd:
        return fmt.day_short(firstd)
    return "%s – %s" % (fmt.day_short(firstd), fmt.day_short(lastd))


def _cell(entry: Optional[dict]) -> str:
    if entry is None:
        return '<td class="empty"></td>'
    ob = entry["versions"][0]["obj"]
    d = ob["display"]
    flags = []
    if len(entry["versions"]) > 1:
        flags.append('<span class="flag b">v%d</span>' % entry["versions"][-1]["version"])
    if entry.get("settled"):
        flags.append('<span class="flag">settled</span>')
    if ob["comp"]["holiday_code"]:
        flags.append('<span class="flag">%s</span>'
                     % esc(ob["comp"]["holiday_code"].replace("_", " ").title()))
    if ob["completeness"]["missing"]:
        flags.append('<span class="flag r">%d missing</span>'
                     % len(ob["completeness"]["missing"]))
    cls = "good" if (ob["headline"]["comp_pct"] or 0) >= 0 else "bad"
    return ('<td><a class="cell" href="day/%s.html">'
            '<span class="dnum">%s</span>'
            '<span class="amt">%s</span>'
            '<span class="cmp %s">comp %s</span>%s</a></td>'
            % (esc(ob["date"]), esc(d["date_short"]), esc(d["net_sales"]),
               cls, esc(d["comp_pct"]), "".join(flags)))


# -- the writer -------------------------------------------------------------

def day_href(date_iso: str, version: int = 1) -> str:
    return ("%s.html" % date_iso if version == 1
            else "%s-v%d.html" % (date_iso, version))


def write(path: str, text: str) -> str:
    """One place that touches the filesystem, so the byte-level rules (utf-8,
    LF newlines) are stated once and cannot drift between page types."""
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def build_site(out_dir: str, days: List[dict],
               storylines: Optional[List[dict]] = None,
               today: Optional[str] = None) -> List[str]:
    """Render the whole archive. Returns the written paths, sorted.

    `days` is a list of {"date", "versions", "settled"} — the archive rows as
    read back out of SQLite, not freshly computed objects. The site renders
    what was sent (BR-7); the only object here that is not an archive row is
    the settled *view*, which is labelled as a view everywhere it appears.
    """
    written = [write(os.path.join(out_dir, "assets", "site.css"), CSS)]
    days = sorted(days, key=lambda e: e["date"])

    for i, entry in enumerate(days):
        versions = entry["versions"]
        vlinks = [{"version": v["version"],
                   "href": day_href(entry["date"], v["version"])}
                  for v in versions]
        history = ("%s-history.html" % entry["date"]) if len(versions) > 1 else None
        settled = ("../ecom/%s-settled.html" % entry["date"]) if entry.get("settled") else None
        prev_e = days[i - 1] if i > 0 else None
        next_e = days[i + 1] if i + 1 < len(days) else None

        for v in versions:
            nav = {
                "stem": entry["date"] if v["version"] == 1
                        else "%s-v%d" % (entry["date"], v["version"]),
                "versions": vlinks,
                "history": history,
                "settled": settled,
                "prev_href": day_href(prev_e["date"]) if prev_e else None,
                "prev_label": (prev_e["versions"][0]["obj"]["display"]["date_short"]
                               if prev_e else None),
                "next_href": day_href(next_e["date"]) if next_e else None,
                "next_label": (next_e["versions"][0]["obj"]["display"]["date_short"]
                               if next_e else None),
            }
            written.append(write(
                os.path.join(out_dir, "day", day_href(entry["date"], v["version"])),
                render_day(v["obj"], nav)))

        if history:
            written.append(write(os.path.join(out_dir, "day", history),
                                 render_history(versions)))
        if entry.get("settled"):
            written.append(write(
                os.path.join(out_dir, "ecom", "%s-settled.html" % entry["date"]),
                render_settled(versions[0]["obj"], entry["settled"])))

    written.append(write(os.path.join(out_dir, "index.html"),
                         render_index(days, storylines=storylines, today=today)))
    return sorted(written)
