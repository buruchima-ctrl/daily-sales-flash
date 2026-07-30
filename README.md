# Daily Sales Flash — build summary

**Live demo:** [snowy-thistle-v3fy.here.now](https://snowy-thistle-v3fy.here.now/) — the generated archive, exactly as `run_flash.py --all` renders it.

Lumière Beauty Co., 25 stores across five US regions plus e-commerce. This
generator turns a daily sales fact table into a **send-ready morning flash**:
one computed object per day, rendered to four surfaces that cannot disagree —
email HTML, a Slack text block, a print one-pager, and a browsable web archive.

Python 3.9+ **standard library and SQLite only**. Zero pip installs, runs
offline, no server needed to generate. Built against `02-BRD.md` (business
rules BR-1..BR-8) and `03-PRD.md` (Approved v1.1).

---

## Run it

```bash
cd "Sales Flash"

python3 seed.py                    # build flash.db: roster, calendar, 2+ years of facts
python3 run_flash.py --all         # generate the 60-day archive, all four surfaces
python3 app.py                     # browse it at http://127.0.0.1:8765/
```

Other entry points:

```bash
python3 run_flash.py --date              # the latest complete day (2026-07-23)
python3 run_flash.py --date 2026-07-04   # any day; renders all four surfaces
python3 run_flash.py --check             # storyline assertions + full test suite + determinism
python3 -m unittest discover tests       # the tests on their own
python3 app.py --port 9000 --host 0.0.0.0
```

`--date` renders **from the archive** when the day is already there (BR-7: the
site shows what was sent, not a fresh recompute) and computes-then-archives the
day only when it is absent.

### What lands where

```
flash.db                     SQLite: stores, calendar, sales_day, plan_day, flash_archive
render/email/2026-07-23.html inline-CSS email, phone-first, ≤100KB, no external assets
render/slack/2026-07-23.txt  paste-ready plain-text block
render/print/2026-07-23.html @media print one-pager (Letter portrait, 0.5in)
render/site/index.html       archive index — fiscal-week calendar navigation
render/site/day/*.html       one page per archived day (one per version)
render/site/day/*-history.html  restatement history (BR-7)
render/site/ecom/*-settled.html settled-vs-flash comparison (BR-4)
render/site/assets/site.css  the only shared asset; relative link, nothing external
```

Restated days render twice: `2026-07-20.html` (version 1, as sent) and
`2026-07-20-v2.html`, plus `2026-07-20-history.html`. The email/Slack/print
files for a version 2 carry the `-v2` suffix.

### Server endpoints (`app.py`)

| Path | What it does |
|------|--------------|
| `/` | the archive index |
| `/day/…`, `/ecom/…`, `/assets/…` | the generated site |
| `/email/…`, `/print/…`, `/slack/…` | aliases onto the sibling render folders, so the archive's links resolve |
| `/today` | **generates** the latest complete day live from `flash.db` (web surface) |
| `/today.email.html`, `/today.print.html`, `/today.txt`, `/today.json` | the same object, other surfaces |

`/today` does not write to `flash_archive`: a browser refresh is not a send
(BR-7). "Today" is fixed at **2026-07-24**, latest complete day
**2026-07-23** — no code path in this system calls the wall clock.

---

## Planted storylines — the index

Each of the eight storylines (PRD §7), and the exact file where it is visible.
Paths are relative to `render/site/`. The archive index renders the same eight
as cards from `run_flash.storyline_index()`, which is the copy that ships with
the build; the table below is prose and can drift from it, so trust the site if
the two ever disagree.

| # | Storyline | Rule | Where to see it |
|---|-----------|------|-----------------|
| 1 | **Holiday shift — July 4.** The holiday-aligned comp (+25.7% vs Fri Jul 4, 2025) leads; the raw week-aligned comp is stated beside it, along with the same-calendar-date figure the old spreadsheet printed. A second disclosure names the weekday trade-off the alignment buys. | BR-1 | `day/2026-07-04.html` — gold banner at the top, then the two BR-1 disclosures. Also `render/email/2026-07-04.html`, `render/print/2026-07-04.html`, `render/slack/2026-07-04.txt`. |
| 2 | **Soft Southeast.** LB-009 (Palmetto Landing) and LB-010 (Sunset Terrace) have run at ×0.78 since 2026-07-10. Both are named in the focus panel with their dollar deltas and percentages; the trailing-14-day table shows Southeast at −$21.1K (−4.2%), the only region that far down. | BR-6, PRD §6 | `day/2026-07-23.html` — "Focus — what moved it", then "Trailing 14 days". |
| 3 | **Remodel closure — LB-013.** Lakeview Arcade went down 2026-06-15 and posts nothing. Out of the comp set on **both** sides of the comparison, disclosed by name with its open date. | BR-2 | `day/2026-07-23.html` — Disclosures, "Excluded from comp on both sides — closed for remodel". |
| 4 | **Late posters, one escalating.** LB-021 (Santa Rosa Plaza) missed 2026-07-22 **and** 07-23 and escalates to store ops; LB-005 (Granite Hill Commons) missed 07-23 only and does not. Totals are reported-store figures — 22 of 24 — never zero-filled. | BR-3 | `day/2026-07-23.html` — red completeness banner, red escalation banner, and two BR-3 disclosures. |
| 5 | **E-commerce maturation.** Demand read −8.0% on the send morning; the shipped series settled at +5.0%. The sent flash is **unchanged**; the settled view sits beside it at its own URL and says so. | BR-4 | `ecom/2026-07-23-settled.html` — the two bases side by side; linked from a green banner on `day/2026-07-23.html`. |
| 6 | **New store — LB-025.** Opened 2025-08-01, fewer than 13 full fiscal periods. Inside total net sales, outside comp, disclosed. | BR-2 | `day/2026-07-23.html` — Disclosures, "In total sales but not in comp — fewer than 13 full fiscal periods". |
| 7 | **Bright spot — LB-022.** Pacific Heights Court (West) at ×1.18 since 2026-07-17, +$2.5K (+22.1%) — the panel's single favourable slot. | PRD §6.2 | `day/2026-07-23.html` — the ▲ line at the foot of the focus panel. |
| 8 | **Restatement — version 2.** 2026-07-20 re-issued on the settled basis with a reason string carrying the numbers. Version 1 is preserved byte-for-byte at its own URL. | BR-7 | `day/2026-07-20-history.html` — both versions, the reason, and a figure-by-figure diff. Version 1: `day/2026-07-20.html`. Version 2: `day/2026-07-20-v2.html`. |

The archive index (`index.html`) links all eight, and the fiscal-week grid
flags them in place: `v2` on the restated day, `settled` on the maturation day,
the holiday code on holidays, and `n missing` on incomplete days.

---

## Conventions

**One formula home (BR-5).** Every metric is computed in exactly one function
in `flash/catalog.py`. `flash/compute.py` assembles the per-day object and
attaches **display strings** built by `flash/fmt.py`; the four renderers print
those strings and never format a number themselves. That is why the surfaces
cannot disagree — and `tests/test_render.py` proves it by asserting every
shared display value appears verbatim in all four rendered files.

**One place to be right about dates.** `ly_aligned_date` is materialized into
the `calendar` table at seed time, so every comp is a join rather than a
computation. The one judgement call that is *not* a lookup — whether a holiday
override leads — lives in `compute._comp_block`, once, and always carries both
figures with the adjusted one leading (BR-1).

**Missing is not zero (BR-3).** An unposted store has no `sales_day` row at
all. Totals are reported-store figures with the completeness banner attached;
there is no imputation anywhere in v1.

**Immutability (BR-7).** `archive.write_version` refuses to overwrite: no
upsert, no `INSERT OR REPLACE`, no force flag. A correction goes through
`restate()`, which appends version+1 with a reason. `--all` clears the whole
table and rebuilds — the only sanctioned way to rewrite an archive row is to
rebuild the entire archive from the seed.

**Determinism (NFR-2).** No `now()` anywhere: `as_of` is derived from the flash
date, `created_at` from `as_of`, and all seed randomness is a SHA-256 of
`(entity, date, tag)`. JSON serializes with `sort_keys`. Two consecutive
`--all` runs produce a byte-identical `render/` tree and an identical
`flash_archive` export.

**Assertions name the fix (NFR-4).** Every assertion failure names the rule or
storyline it guards, the offending rows, and where to fix it — for example
`BR-6 broken on 2026-07-23: named contributions … + all other … but the
headline comp gap is …; an entry's covers set in flash/focus.py overlaps
another's.`

**Every catalog metric reaches a reader.** All fifteen metrics in PRD §5 are
computed once and rendered somewhere a reviewer can find them — including the
basket four (transactions vs LY, AOV, UPT, AUR), which sit in their own block
on email, Slack and the archive and as a one-line strip on the print handout.
A metric that the catalog computes and nobody ever sees is a metric that is
quietly wrong forever, so `tests/test_render.py` names those four in their own
test rather than trusting the general sweep to catch them.

**Design tokens (PRD §8).** Gold = an input the business asserted; blue = a
figure presented as given; green = calculated here. Avenir display / Charter
body / monospace data, all OS-resident — no webfonts, no network. Every
generated HTML file declares `<meta charset="utf-8">`; the site makes zero
external requests and every internal link is relative (519 links checked, 518
resolve to a file and one is the `/today` server route).

**One page means one page.** Letter portrait at 0.5in margins leaves a 7.5 ×
10in box — 960px at 96dpi — and every type size in `render_print.py` is set
against that budget rather than to taste. The fullest day in the archive is
2026-07-23, which carries an incompleteness band, an escalation band and seven
disclosures; it comes to 883px. All 61 generated handouts fit. Nothing in a
stdlib build can measure CSS layout, so this one is checked in a browser: load
`/print/<date>.html`, clone `.sheet` at `width:7.5in` with the margins zeroed,
and read its height. A handout that quietly spills onto a second page loses its
disclosures, which is the half nobody would choose to drop.

**The phone is the design constraint, not an afterthought.** The email's three
headline tiles sit side by side in a table cell, and a table cell cannot be
narrower than its widest unbreakable token — here `$172,646.63`. At the card's
usual 20px of side padding the headline row's minimum width came to 378px,
wider than a 375px phone, and email clients have no media queries to stack it.
Those tiles use 10px instead. The whole mail now renders without horizontal
scroll down to a 344px viewport, measured in a browser rather than assumed.

---

## Deviations from the PRD, and why

Nothing was asked; where the PRD was silent the simplest option consistent with
the BRD was taken, and it is recorded here.

1. **53-week years are FY2023, FY2028, FY2034** — not the draft's FY2029 guess.
   Corrected during the foundation phase; none falls inside the archive's comp
   path (FY2026 vs FY2025), so the restated-shift logic is covered by synthetic
   unit test, which PRD §10 explicitly permits.
2. **The site links `../email/…` rather than absolute paths.** One href has to
   work in two worlds: opened from the disk (`file://`, where `..` walks up to
   `render/`) and served by `app.py` (where the site is the web root and a
   browser clamps the leading `..` onto the `/email/` alias). Relative links
   were chosen over a base URL so the folder can be copied and still work.
3. **A shared `assets/site.css` instead of inline CSS on the web surface.** The
   email is inline-only because mail clients demand it; the archive is 64 HTML
   files, and duplicating 7KB of CSS into each of them would have been weight
   with no benefit. It is a relative link to a file inside `render/site/`, so
   the "zero external requests" rule still holds.
4. **The settled view is a page, not an archive version.** BR-4 asks for both
   to be visible without rewriting history; BR-7 says a version is something
   that was *sent*. A maturation view that nobody sent is therefore published
   at its own URL (`ecom/2026-07-23-settled.html`) and labelled a view, while
   the planted restatement of 2026-07-20 — which *was* re-issued — is a real
   version 2 in `flash_archive`.
5. **`--date` renders from the archive when the day is already archived.** A
   re-render that recomputed could quietly differ from what was sent; that is
   precisely the defect BR-7 exists to prevent. Days not yet in the archive are
   computed and written as version 1.
6. **`/today` regenerates rather than serving a cached page,** and deliberately
   does not archive. It demonstrates the generate-on-demand path; `--all` is
   what publishes.
7. **The focus panel's region roll-up did not fire on 2026-07-23** — e-commerce
   is the single largest adverse contributor that day, so the panel names it,
   then the two Southeast doors individually (each labelled with its region).
   The §6.3 ">60% of the gap" roll-up is measured against the adverse mass, not
   the net gap: against the net, a day that nets to near zero would let a tiny
   region "explain 60%" of nothing. Storyline 2 stays visible through the named
   doors and the trailing-14-day region table.
8. **Print drops the window ranges, the e-commerce table and the formula key**
   to hold one page (PRD §8). The basket survives the cut as a single line
   rather than a table, because the trade meeting always asks whether a soft
   day was traffic or spend, and that answer is transactions and AOV. The
   cross-surface test asserts on the intersection of what all four surfaces
   claim to show — 45–48 values per day, ×4 surfaces, ×3 sampled days — rather
   than on the union.

---

## Test suite

`python3 run_flash.py --check` runs all of it: rebuild the DB, assert the
storylines manifest in the data, run the tests, verify a byte-identical rebuild.

| File | What it guards |
|------|----------------|
| `tests/test_calendar.py` | NRF 4-5-4 boundaries, 53-week years, label parsing that rejects ambiguity, day-aligned LY |
| `tests/test_catalog.py` | formulas, comp-set rules (new store, remodel, missing), BR-6 reconciliation per scope |
| `tests/test_compute.py` | BR-1 holiday lead + raw stated, BR-6 to the cent on all 60 archived days, BR-2 exclusions disclosed by name, BR-3 missing-not-zero and the two-day escalation, BR-4 demand vs settled, BR-7 immutability and version chains |
| `tests/test_render.py` | BR-5 all four surfaces agree on every shared display value, PRD §5 metrics #7–#10 reach every surface, email ≤100KB with no external assets or `<style>`/`<script>`/`<link>`, utf-8 in every generated HTML file, link integrity across the built archive, byte-identical re-render |

48 tests, all green.

### Re-deriving the numbers yourself

The tests check the build against itself, which is worth exactly as much as the
build. To check it against something else, go at `flash.db` with raw SQL and no
imports from `flash/`:

```sql
-- day-aligned LY is same fiscal week, same weekday, prior fiscal year.
-- Expect zero rows.
SELECT t.date, l.date FROM calendar t JOIN calendar l ON l.date = t.ly_aligned_date
WHERE t.restated = 0 AND (l.fiscal_year <> t.fiscal_year - 1
   OR l.week <> t.week OR l.day_of_week <> t.day_of_week);
```

Then rebuild one day's comp by hand: take the stores open 13 full fiscal periods
before the current one, drop anything inside a remodel window on either side of
the comparison, drop anything unposted on either side, and divide the surviving
TY sum by the surviving LY sum. For 2026-07-23 that is 21 entities,
`$161,668.98 ÷ $165,588.49 − 1 = −2.3670%`, and the archived flash carries
`-0.023670183839468395`. For an ordinary day with nobody missing, 2026-07-15
gives 23 entities and `+2.3454%`.

The focus panel is checkable the same way. Sum each region's `(TY − LY)` on
2026-07-23 and the six numbers come to `−$3,919.51` — the headline gap, to the
cent, which is the whole of BR-6. Southeast contributes `−$1,816.37` of it, and
LB-009 and LB-010 are `−$1,772.46` and `−$1,226.06` inside that, meaning the two
planted doors are worth more than the region's entire shortfall. Four Southeast
doors were up on the day and partly covered for them. That is why the panel
names the doors rather than the region: on this particular day, "Southeast is
soft" would have understated the two stores that actually moved.
