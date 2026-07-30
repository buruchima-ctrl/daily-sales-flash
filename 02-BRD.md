# Daily Sales Flash — Business Requirements Document (BRD)
**Author:** Strategy layer (Claude Fable) · **Builder:** Opus · **Date:** 2026-07-24 · **Status:** Approved v1.1 — builds on `01-Strategy.md` (all decisions approved 2026-07-24); defers to it on intent

---

## 1. Business context

Lumière Beauty Co. (per Strategy D2): a specialty beauty retailer with 25 stores across five US regions plus a growing e-commerce channel. Leadership gets sales numbers today via a manually assembled spreadsheet email that arrives between 8:30 and 10:00, compares against last year's *calendar date*, and goes silent when the analyst is out. Nobody trusts the Tuesday-after-a-holiday numbers, e-comm returns make every Monday look better than it was, and the two stores that post late are silently treated as zero.

## 2. Business objectives

| # | Objective | Measure for the prototype |
|---|-----------|---------------------------|
| O1 | Flash arrives daily with zero analyst effort | Fully generated from data; no manual step between seed and send-ready output |
| O2 | Calendar-true comparisons | 100% of comps day-aligned (fiscal week + day-of-week); holiday map applied; restated 53-week handling documented |
| O3 | Self-explaining variances | Every headline gap decomposed to named drivers that sum to the gap |
| O4 | Disclosed data quality | Completeness banner on every flash; unsettled e-comm never presented as final |
| O5 | Multi-surface from one compute | Email HTML, Slack text, print one-pager, and web archive rendered from the same computed object — numbers cannot differ across surfaces |

## 3. Users

| Role | What they need from the flash |
|------|-------------------------------|
| CEO / Leadership | The headline in 20 seconds on a phone: total, comp, plan, the three things that moved |
| Head of Stores | Region/store decomposition; which doors drove the miss; late-poster escalations |
| E-commerce lead | Demand vs shipped, settled comp, return-adjusted view when matured |
| Merchandising / Planning | WTD/MTD vs plan, gap-to-go run rate in the Monday recap |
| FP&A | The archive: consistent history, restatement-free, exportable |

## 4. Scope

### In scope (v1)
1. **Daily flash** — yesterday + WTD + MTD (fiscal period) + YTD: net sales, comp %, plan attainment, transactions, AOV, UPT, AUR; total / channel / region / store.
2. **Comp engine** — day-aligned LY per the NRF 4-5-4 calendar, holiday-shift mapping, comp-store rules (new stores enter comp after 13 full fiscal periods; remodel/closure days excluded with disclosure).
3. **Focus panel** — up to three adverse movers + one bright spot, each with a plain-English decomposed reason; drivers reconcile to the gap.
4. **Data-quality banner** — stores reported / expected, % sales posted, e-comm settlement status; two-day late posters escalate.
5. **Narrative paragraph** — template-composed English summary of the day (no LLM dependency; deterministic composition from computed facts).
6. **Monday trade recap edition** — the closed week vs LY/plan, gap-to-go for the new week.
7. **Four render surfaces** from one compute: email HTML (inline CSS, phone-first, no external assets), Slack text block, print one-pager, web archive with calendar navigation.
8. **Seeded demo** — 2+ years of daily history for the 25 Lumière stores + e-comm so every comp window works, with planted storylines (§6 of the PRD) that the flash must surface.

### Out of scope (v1)
- Real POS/ERP integration; actual email/Slack transmission (outputs are send-ready artifacts) · traffic & conversion (schema-ready, per D5) · inventory, sell-through, markdown & promo effectiveness (that is the next product, which consumes this data spine) · intraday flashes · multi-currency · authentication · LLM-generated narrative.

## 5. Business rules (enforced in code, not just documented)

| ID | Rule |
|----|------|
| BR-1 | Every LY comparison is day-aligned: same fiscal week, same day-of-week, holiday map applied. Raw-date comparison never appears without the aligned figure leading. |
| BR-2 | Comp store definition: 13 full fiscal periods of operation; remodel/closure days excluded from both years of the comp; every exclusion disclosed in the flash footer. |
| BR-3 | A store that hasn't posted is *missing*, never zero. Totals show reported-store figures with completeness disclosed; no imputation in v1. |
| BR-4 | E-comm demand (ordered) and shipped are distinct series; day-of comp uses demand, labeled; settled figures replace them as they mature, and the archive shows both without rewriting history silently. |
| BR-5 | One formula home: every metric computed in exactly one catalog function; all four surfaces render the same computed object (the Supply Chain BR-13 discipline). |
| BR-6 | Focus-panel drivers must reconcile: named contributions sum to the headline gap to the cent. |
| BR-7 | A generated flash for a given day is immutable once "sent" (written to the archive); corrections issue a new version marked as a restatement, never an in-place overwrite (Door Engine snapshot discipline, one-day grain). |
| BR-8 | 53-week years: LY comps use the NRF restated calendar (shift one week); the flash notes when restatement is in effect. |

## 6. Success criteria for the prototype

A viewer can, in one sitting: (1) open yesterday's flash on a phone-width screen and get the story in 20 seconds; (2) trace any focus-panel reason down to the stores behind it and watch the numbers reconcile; (3) find a planted holiday-shift week and see raw vs adjusted comps both stated, adjusted leading; (4) catch the planted late-poster day and see it disclosed, not zero-filled; (5) regenerate the entire 60-day archive byte-for-byte from the seed (determinism, the Lease Toolkit standard).
