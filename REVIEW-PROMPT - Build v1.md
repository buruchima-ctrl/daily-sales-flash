# Reviewer Session Prompt — Daily Sales Flash, Build v1
**Prepared:** 2026-07-25 by the strategy layer (Claude Fable) · **Status: LINED UP — do not launch until (a) the Opus build session reports complete and (b) Barma has done his own read of the build report.**
**How to use:** paste everything below the rule into a fresh session (Fable or Opus — a session that did NOT build the product). The deliverable is `Sales Flash/REVIEW - Build v1 - Signoff.md`, modeled on `Leases/REVIEW - Build v1 - Signoff.md`.

---

You are the REVIEWER for the Daily Sales Flash build in Barma's retail decision-systems portfolio. You are not the builder and you take nothing on the builder's word: every claim you accept, you re-derive. The Leases review (`/Users/barmauruchima/Documents/Claude/Projects/Leases/REVIEW - Build v1 - Signoff.md`) is your template for rigor and for the shape of the record you write.

## Ground rules
- REVIEW session, not a build. You may write throwaway verification scripts in the scratchpad, but you do not amend product code. If something fails, it goes on the punchlist for the builder — you fix nothing.
- Independence: read the spec before the code, and compute expected values by hand/SQL before looking at rendered output.
- Work only inside `Sales Flash/` (read) + your scratchpad (write). The one product file you create is `Sales Flash/REVIEW - Build v1 - Signoff.md`.
- Nothing external: no publishing, no deploys.

## Read in this order (all under /Users/barmauruchima/Documents/Claude/Projects/)
1. `Sales Flash/01-Strategy.md` (approved D1–D5) → `02-BRD.md` (BR-1…BR-8) → `03-PRD.md` (the contract: §4 calendar spec, §5 metric catalog, §6 focus panel, §7 as-built storyline assignments, §8 surfaces, §9 NFRs, §10 acceptance checklist, §11 approved defaults).
2. `Sales Flash/README.md` — the builder's summary and claimed deviations. Treat every claim as unverified.
3. `Portfolio Analysis/README.md` "Bugs this build caught" — the defect classes to hunt for here (label parsing that accepts ambiguity, off-by-one period indexing, mismatched comparison windows, freeze-before-write ordering).

## What you verify

**Static (spec compliance, before running anything):**
- PRD §2 deliverables all present; schema matches PRD §3; no pip imports anywhere (stdlib + sqlite3 only, NFR-1); no `now()`/`datetime.today()` in any compute or render path (NFR-2); every generated HTML file declares `<meta charset="utf-8">` and the email surface has no external asset references (NFR-5 — grep, don't trust).
- BR-5 discipline: each §5 metric computed in exactly one catalog function; renderers consume the computed object, never re-derive.

**Dynamic (executed, not read):**
1. **Determinism:** delete generated artifacts, run `seed.py` + `run_flash.py --all` twice from scratch, byte-compare DB exports and every rendered file (NFR-2). Time the archive regeneration (< 30s, NFR-3).
2. **Calendar (the moat — hardest check):** hand-derive the NRF 4-5-4 mapping for at least 6 dates across both fiscal years (year start = Sunday nearest Feb 1; 4-5-4 grouping; day-of-week), and verify `ly_aligned_date` for each by direct SQL against the calendar table. Verify the holiday-override rule on July 4 (PRD §4.3) and the 53-week synthetic unit test exists and passes (PRD §4.1: FY2023/FY2028/FY2034, none in the archive window).
3. **Comp % by hand:** pick one ordinary day; compute comp-store TY and LY-aligned sums by direct SQL (new store LB-025 excluded, remodel LB-013 days excluded, ECOM per §11); match the flash's number exactly (§10 item 2).
4. **All eight §7 storylines** surface where the PRD says: holiday-shift week (raw ≠ adjusted, adjusted leads); soft Southeast LB-009/LB-010 found and decomposed by the focus panel; LB-013 remodel exclusion with footer disclosure; LB-021 two-day late-poster escalation + LB-005 single-day (missing ≠ zero — verify totals via SQL); ECOM 2026-07-23 demand −8% settling positive with no silent rewrite (BR-4/BR-7); LB-022 bright spot; 2026-07-20 restatement version 2 with reason rendered.
5. **BR-6 reconciliation:** re-add the focus panel's named contributions + "all other" for two days by SQL; must equal the headline gap to the cent.
6. **Surfaces agree:** for three sampled days, every number identical across email, Slack text, print, and web archive (BR-5). Email file ≤100KB, inline CSS only, renders without horizontal scroll at 375px (drive it in the browser preview at mobile width).
7. **Immutability:** attempt an in-place archive overwrite path (re-generate an already-archived day); confirm version-append behavior, not mutation (BR-7).

## The record you write
`Sales Flash/REVIEW - Build v1 - Signoff.md`, same structure as the Leases record: date, reviewer, spec, builder; **verdict first** (PASSED / PASSED WITH NOTES / FAILED with punchlist); "What was verified" split static/dynamic with the actual numbers you re-derived (not "checked ✓" — the numbers); non-blocking notes; builder deviations reviewed and accepted or challenged; carried-forward scope. If FAILED: a numbered punchlist naming file, symptom, spec clause, and the evidence.

## After the record
Report back to Barma: verdict, the two or three strongest receipts, every note/punchlist item, and — only if PASSED — the reminder that the Promo & Markdown Effectiveness build (portfolio handoff §8 queue, item 8; specs approved 2026-07-25) is now unblocked. Do not start that build; do not update the portfolio page (its queue item 7 status flip is a separate step Barma triggers).
