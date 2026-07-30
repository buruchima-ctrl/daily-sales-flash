# -*- coding: utf-8 -*-
"""Email surface — one self-contained HTML file per day (PRD §8).

Constraints, and why each one is here:

  * **Inline CSS only.** Not "mostly inline with a <style> block for the hard
    parts" — Gmail's web client strips <style> from forwarded mail, and a flash
    that survives the first send but breaks on the forward to the board is
    worse than one that never worked. Every declaration is a style attribute.
  * **Table layout.** Outlook's Word rendering engine has no flexbox and no
    grid. Tables are not nostalgia; they are the only box model that renders
    the same in Outlook, Gmail and Apple Mail.
  * **No external assets, no JS, no http(s) references at all.** Remote images
    are the tracking-pixel pattern corporate mail scanners strip, which would
    leave holes in the layout, and a flash must render with images off.
  * **Dark-mode safe.** Every cell declares its own background AND foreground,
    so a client that flips the page background cannot leave dark text on dark.
  * **375px.** Fixed pixel widths are capped at 100% and the layout is a single
    column; nothing here can produce a horizontal scrollbar on a phone.

The renderer reads only `obj["display"]` strings (BR-5) — it never formats a
number itself, so the email cannot round differently from the archive.
"""

from __future__ import annotations

from html import escape as esc

# Colours chosen to sit on either a white or a dark client background.
INK = "#1E2B38"
INK_SOFT = "#55636F"
PAPER = "#F7F5F0"
PANEL = "#FFFFFF"
RULE = "#DCD7CC"
GOLD = "#8A6416"
BLUE = "#2C5F8A"
CALC = "#2E7D5B"
BAD = "#A33A2A"
GOOD = "#2E7D5B"

DISPLAY = "'Avenir Next',Avenir,'Segoe UI',Helvetica,Arial,sans-serif"
BODY = "Charter,'Iowan Old Style',Georgia,'Times New Roman',serif"
DATA = "ui-monospace,'SF Mono',Menlo,Consolas,'Courier New',monospace"

WRAP = ("margin:0;padding:0;width:100%%;background:%s;color:%s;"
        "-webkit-text-size-adjust:100%%;" % (PAPER, INK))
CARD = ("width:100%%;max-width:600px;background:%s;border:1px solid %s;"
        "border-collapse:collapse;" % (PANEL, RULE))
CELL = "padding:16px 20px;font-family:%s;font-size:15px;line-height:1.5;color:%s;" % (BODY, INK)
EYEBROW = ("font-family:%s;font-size:11px;letter-spacing:0.14em;"
           "text-transform:uppercase;color:%s;" % (DISPLAY, INK_SOFT))
NUM = "font-family:%s;font-variant-numeric:tabular-nums;color:%s;" % (DATA, INK)


def subject_line(obj) -> str:
    return obj["subject"]


def render(obj) -> str:
    d = obj["display"]
    out = []
    a = out.append

    a('<!doctype html>')
    a('<html lang="en"><head>')
    a('<meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<meta name="color-scheme" content="light dark">')
    a('<meta name="supported-color-schemes" content="light dark">')
    a('<title>%s</title>' % esc(obj["subject"]))
    a("<!-- Subject: %s -->" % esc(obj["subject"]))
    a("<!-- Subject-line convention: Flash — {Day Mon D} · {net sales} · "
      "comp {comp pct} · plan {attainment}. Every token is the same display "
      "string the body prints (BR-5), so the subject cannot disagree with the "
      "flash it announces. -->")
    a('</head>')
    a('<body style="%s">' % WRAP)
    # preheader: what the phone shows in the list, before the mail is opened
    a('<div style="display:none;max-height:0;overflow:hidden;opacity:0;">%s</div>'
      % esc(_preheader(obj)))
    a('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" '
      'border="0" style="background:%s;"><tr><td align="center" style="padding:12px;">'
      % PAPER)
    a('<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="%s">' % CARD)

    _masthead(a, obj, d)
    _headline(a, obj, d)
    _banners(a, obj, d)
    _narrative(a, obj)
    _focus(a, obj, d)
    _windows(a, obj, d)
    _basket(a, obj, d)
    _slices(a, obj, d)
    _ecom(a, obj, d)
    _regions(a, obj, d)
    _recap(a, obj, d)
    _disclosures(a, obj)
    _method(a, obj)

    a('</table>')
    a('</td></tr></table>')
    a('</body></html>')
    return "\n".join(out) + "\n"


# -- sections ---------------------------------------------------------------

def _preheader(obj) -> str:
    d = obj["display"]
    return "%s · comp %s · plan %s · %s" % (
        d["net_sales"], d["comp_pct"], d["plan_attainment"], d["completeness"])


def _masthead(a, obj, d):
    a('<tr><td style="%spadding-bottom:4px;border-bottom:2px solid %s;">' % (CELL, RULE))
    a('<div style="%s">%s · Daily Sales Flash</div>' % (EYEBROW, esc(obj["company"])))
    a('<div style="font-family:%s;font-size:22px;font-weight:600;color:%s;'
      'padding-top:6px;line-height:1.25;">%s</div>' % (DISPLAY, INK, esc(d["date_long"])))
    a('<div style="font-family:%s;font-size:12px;color:%s;padding-top:4px;">'
      '%s · fiscal %s · week %s · generated for the morning of %s%s</div>'
      % (DISPLAY, INK_SOFT, esc(d["week_label"]), esc(d["period_label"]),
         obj["calendar"]["week"], esc(d["as_of"]),
         " · VERSION %d (restatement)" % obj["version"] if obj["version"] > 1 else ""))
    a('</td></tr>')


def _headline(a, obj, d):
    comp_colour = GOOD if (obj["headline"]["comp_pct"] or 0) >= 0 else BAD
    plan_colour = GOOD if (obj["headline"]["plan_attainment"] or 0) >= 1 else BAD
    tiles = [
        ("Net sales", d["net_sales"], INK, d["net_sales_exact"]),
        ("Comp %s" % obj["comp"]["basis"], d["comp_pct"], comp_colour,
         "vs %s" % d["comp_ly_date"]),
        ("Plan attainment", d["plan_attainment"], plan_colour, d["plan_gap"]),
    ]
    a('<tr><td style="padding:0;">')
    a('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">')
    a('<tr>')
    for label, value, colour, sub in tiles:
        # Horizontal padding is 10px, not the 20px the rest of the card uses.
        # These three tiles sit side by side and a table cell cannot be made
        # narrower than its widest unbreakable token — here "$172,646.63" and
        # "−$5.7K vs plan $178.3K". At 20px a side the row's min-content came to
        # 378px, which is wider than a 375px phone, and email clients have no
        # media queries to stack it. 10px brings the row to ~317px so the
        # headline fits the viewport it was designed for (PRD §8, NFR-5).
        a('<td width="33%%" align="left" valign="top" style="padding:16px 10px 14px;'
          'border-bottom:1px solid %s;">' % RULE)
        a('<div style="%s">%s</div>' % (EYEBROW, esc(label)))
        a('<div style="%sfont-size:24px;font-weight:600;color:%s;padding-top:4px;">'
          '%s</div>' % (NUM, colour, esc(value)))
        a('<div style="font-family:%s;font-size:11px;color:%s;padding-top:3px;">%s</div>'
          % (DATA, INK_SOFT, esc(sub)))
        a('</td>')
    a('</tr></table></td></tr>')


def _banners(a, obj, d):
    c = obj["comp"]
    if c["override_in_effect"]:
        _banner(a, GOLD, "#FBF4E4", "Holiday alignment in effect",
                "Leading comp %s is measured against %s — the same holiday last "
                "year. The raw week-aligned comparison (%s) reads %s. The "
                "adjusted figure leads; both are stated."
                % (d["comp_pct"], d["holiday_aligned_ly_date"],
                   d["week_aligned_ly_date"], d["week_aligned_pct"]))
    cm = obj["completeness"]
    if cm["missing"]:
        _banner(a, BAD, "#FBEDEA", "Incomplete — %s" % d["completeness"],
                "%s had not posted at generation time. Missing stores are "
                "excluded from totals and comp, never counted as zero. Posted "
                "sales are %s of the trailing-4 same-weekday average."
                % (", ".join(esc(n) for n in cm["missing_names"]), d["posted_pct"]))
    for line in d["focus"]["escalations"]:
        _banner(a, BAD, "#FBEDEA", "Escalation to store operations", line)
    if obj["version"] > 1 and obj["reason"]:
        _banner(a, BLUE, "#EAF1F7", "Restatement — version %d" % obj["version"],
                obj["reason"])


def _banner(a, colour, bg, title, body):
    a('<tr><td style="padding:0 20px 12px;">')
    a('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" '
      'border="0" style="background:%s;border-left:3px solid %s;"><tr>'
      '<td style="padding:10px 12px;">' % (bg, colour))
    a('<div style="font-family:%s;font-size:11px;letter-spacing:0.1em;'
      'text-transform:uppercase;color:%s;font-weight:600;">%s</div>'
      % (DISPLAY, colour, esc(title)))
    a('<div style="font-family:%s;font-size:13px;line-height:1.45;color:%s;'
      'padding-top:4px;">%s</div>' % (BODY, INK, esc(body)))
    a('</td></tr></table></td></tr>')


def _narrative(a, obj):
    a('<tr><td style="%spadding-top:4px;padding-bottom:14px;">' % CELL)
    a('<div style="font-size:15px;line-height:1.6;color:%s;">%s</div>'
      % (INK, esc(obj["narrative"])))
    a('</td></tr>')


def _focus(a, obj, d):
    f = d["focus"]
    _section(a, "Focus — what moved it")
    a('<tr><td style="padding:0 20px 6px;">')
    a('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">')
    for e in f["entries"]:
        colour = BAD if e["adverse"] else GOOD
        a('<tr><td style="padding:7px 0;border-bottom:1px solid %s;">' % RULE)
        a('<div style="font-family:%s;font-size:14px;line-height:1.45;color:%s;">'
          '<span style="color:%s;font-weight:600;">%s</span> %s</div>'
          % (BODY, INK, colour, "▼" if e["adverse"] else "▲", esc(e["line"])))
        for r in e["receipts"]:
            a('<div style="font-family:%s;font-size:12px;color:%s;padding-left:14px;'
              'padding-top:2px;">%s</div>' % (DATA, INK_SOFT, esc(r)))
        a('</td></tr>')
    a('<tr><td style="padding:7px 0;border-bottom:1px solid %s;">' % RULE)
    a('<div style="font-family:%s;font-size:13px;color:%s;">%s %s</div>'
      % (BODY, INK_SOFT, esc(f["remainder_label"]), esc(f["remainder"])))
    a('</td></tr>')
    a('<tr><td style="padding:8px 0 0;">')
    a('<div style="font-family:%s;font-size:11px;color:%s;">Named contributions '
      '+ all other = %s, the headline comp gap, to the cent (BR-6).</div>'
      % (DATA, CALC, esc(f["headline_gap"])))
    a('</td></tr>')
    a('</table></td></tr>')


def _windows(a, obj, d):
    _section(a, "Week, period, year to date")
    rows = [(d["windows"][k]["label"], d["windows"][k]["range"],
             d["windows"][k]["net_sales"], d["windows"][k]["comp_pct"],
             d["windows"][k]["plan_attainment"]) for k in ("WTD", "MTD", "YTD")]
    _table(a, ["", "Range", "Net sales", "Comp", "Plan"], rows,
           aligns=["left", "left", "right", "right", "right"])


def _basket(a, obj, d):
    """Catalog metrics #7-#10. The formula key at the foot of this mail names
    AOV / UPT / AUR; without this block it would be documenting rows that are
    not on the page."""
    _section(a, "Basket — transactions, AOV, UPT, AUR")
    rows = [
        ("Transactions", d["transactions"], d["txn_comp"]),
        ("Units", d["units"], ""),
        ("AOV — average order value", d["aov"], ""),
        ("UPT — units per transaction", d["upt"], ""),
        ("AUR — average unit retail", d["aur"], ""),
    ]
    _table(a, ["", "Day", "vs LY"], rows, aligns=["left", "right", "right"])


def _slices(a, obj, d):
    _section(a, "By channel")
    rows = [(r["label"], r["coverage"], r["net_sales"], r["comp_pct"],
             r["plan_attainment"]) for r in d["slices"]["channel"]]
    _table(a, ["Channel", "Posted", "Net sales", "Comp", "Plan"], rows,
           aligns=["left", "right", "right", "right", "right"])

    _section(a, "By region")
    rows = [(r["label"], r["coverage"], r["net_sales"], r["comp_pct"],
             r["plan_attainment"]) for r in d["slices"]["region"]]
    _table(a, ["Region", "Posted", "Net sales", "Comp", "Plan"], rows,
           aligns=["left", "right", "right", "right", "right"])


def _ecom(a, obj, d):
    if "ecom" not in d:
        return
    e = d["ecom"]
    _section(a, "E-commerce — demand vs shipped")
    rows = [
        ("Demand (ordered)", e["demand"], e["demand_comp"]),
        ("Shipped (settled)", e["shipped"], e["shipped_comp"]),
        ("Returns recorded", e["returns"], ""),
        ("Settled return rate (matured window)", e["return_rate"], ""),
    ]
    _table(a, ["", "Amount", "vs LY"], rows,
           aligns=["left", "right", "right"])
    a('<tr><td style="padding:0 20px 12px;">')
    a('<div style="font-family:%s;font-size:11px;color:%s;">Headline uses %s. '
      'This day is %s (settles after %d days); the archive shows both series '
      'without rewriting this flash (BR-4).</div>'
      % (DATA, INK_SOFT, esc(e["basis"]), esc(e["matured"]),
         obj["ecom"].get("settle_lag_days", 3)))
    a('</td></tr>')


def _regions(a, obj, d):
    _section(a, d["focus"]["trailing_label"])
    rows = [(r["label"], r["ly"], r["ty"], r["delta"], r["pct"])
            for r in d["focus"]["trailing_regions"]]
    _table(a, ["Region", "LY", "TY", "Δ", "%"], rows,
           aligns=["left", "right", "right", "right", "right"])


def _recap(a, obj, d):
    if "recap" not in d:
        return
    r = d["recap"]
    _section(a, "Monday trade recap — the week that closed")
    rows = [
        ("Week %s" % r["range"], r["net_sales"], r["comp_pct"], r["plan_attainment"]),
    ]
    _table(a, ["Closed week", "Net sales", "Comp", "Plan"], rows,
           aligns=["left", "right", "right", "right"])
    a('<tr><td style="padding:0 20px 12px;">')
    a('<div style="font-family:%s;font-size:12px;color:%s;">%s has %s of plan '
      'left across %s selling days — %s a day to make it.</div>'
      % (BODY, INK, esc(r["period_label"]), esc(r["remaining_plan"]),
         esc(r["remaining_days"]), esc(r["run_rate"])))
    a('</td></tr>')


def _disclosures(a, obj):
    _section(a, "Disclosures")
    a('<tr><td style="padding:0 20px 10px;">')
    for item in obj["disclosures"]:
        a('<div style="font-family:%s;font-size:12px;line-height:1.5;color:%s;'
          'padding-bottom:6px;"><span style="font-family:%s;color:%s;">%s</span> %s</div>'
          % (BODY, INK, DATA, GOLD, esc(item["rule"]), esc(item["text"])))
    a('</td></tr>')


def _method(a, obj):
    _section(a, "Formula key")
    a('<tr><td style="padding:0 20px 20px;">')
    for m in obj["method"]:
        a('<div style="font-family:%s;font-size:11px;line-height:1.5;color:%s;'
          'padding-bottom:4px;"><strong style="color:%s;">%s</strong> — %s</div>'
          % (DATA, INK_SOFT, INK, esc(m["metric"]), esc(m["formula"])))
    a('<div style="font-family:%s;font-size:11px;color:%s;padding-top:8px;'
      'border-top:1px solid %s;margin-top:8px;">Generated from seeded data for '
      'the morning of %s. No live systems were queried. Demo build.</div>'
      % (DATA, INK_SOFT, RULE, esc(obj["display"]["as_of"])))
    a('</td></tr>')


# -- primitives -------------------------------------------------------------

def _section(a, title):
    a('<tr><td style="padding:14px 20px 6px;">')
    a('<div style="%sborder-top:1px solid %s;padding-top:12px;">%s</div>'
      % (EYEBROW, RULE, esc(title)))
    a('</td></tr>')


def _table(a, headers, rows, aligns):
    a('<tr><td style="padding:0 20px 12px;">')
    a('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
      'border="0" style="border-collapse:collapse;">')
    a('<tr>')
    for h, al in zip(headers, aligns):
        a('<th align="%s" style="font-family:%s;font-size:10px;letter-spacing:0.08em;'
          'text-transform:uppercase;color:%s;font-weight:600;padding:0 0 5px;'
          'border-bottom:1px solid %s;">%s</th>' % (al, DISPLAY, INK_SOFT, RULE, esc(h)))
    a('</tr>')
    for row in rows:
        a('<tr>')
        for i, (cell, al) in enumerate(zip(row, aligns)):
            font = BODY if i == 0 else DATA
            size = "13px" if i == 0 else "12px"
            colour = INK
            if i > 0 and isinstance(cell, str) and cell.startswith("−"):
                colour = BAD
            a('<td align="%s" style="font-family:%s;font-size:%s;color:%s;'
              'font-variant-numeric:tabular-nums;padding:6px 0;border-bottom:'
              '1px solid %s;">%s</td>' % (al, font, size, colour, RULE, esc(str(cell))))
        a('</tr>')
    a('</table></td></tr>')
