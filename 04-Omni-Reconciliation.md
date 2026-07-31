# Omni Metrics Reconciliation — built flash vs. "BRD - DTC DSF Omni Metrics v3"
**Author:** Strategy layer (Claude Fable) · **Date:** 2026-07-30 · **Status:** Analysis for owner review — no build authorized yet; Opus executes only after sign-off
**Source document:** `BRD - DTC DSF Omni Metrics v3.docx` (v3, Mar 2021, author P. Tran) — a real-world corporate BRD adding omni-channel metrics to a DTC Daily Sales Flash
**Reconciled against:** the shipped v1 build (`03-PRD.md` Approved v1.1; catalog metrics #1–15; schema `stores` / `calendar` / `sales_day` / `plan_day` / `flash_archive`)

---

## 1. What the source document is (and isn't)

The Omni BRD is a **metric-definition catalog**: 58 numbered metrics in five families — BOPIS (#1–17), Real-Time Delivery (#18–29), OOFIS "Order Online From In Store" (#30–35), BORIS "Buy Online Return In Store" (#36–50), Click & Reserve (#51–58) — plus three placeholder families (Online Appointment Booking, Virtual Selling, Ship-from-Store) that are explicitly incomplete in the source ("Pending Jamie Relle metrics", "Available in FY22").

It is **not** a flash spec. It says nothing about comps, calendar alignment, plan, completeness disclosure, narrative, or delivery surfaces — everything our Strategy doc treats as the product. Its implied stack (Tableau → PowerBI dashboards, Enterprise Data Lake ingestion) is the client's, not ours. So the reconciliation question is: *which omni **concepts** does our data spine and catalog absorb, and what would have to change* — not "implement 58 dashboard tiles."

## 2. Headline reconciliation

| Verdict | Count | What |
|---|---|---|
| Already in the catalog | 8 of 58 | The FSS/Online AOV baselines and %-of-sales denominators (BOPIS #9–10, RTD #21–22, BORIS #45–46, C&R #55–56 are all the *same two metrics* restated per family — our catalog #8 AOV scoped by channel) |
| Derivable once numerators exist | 14 of 58 | All "% AOV Lift" and "% of FSS/Online Sales" ratios (#11–14, #23–26, #34–35, #49–50, #57–58) — pure arithmetic on new numerators over existing denominators |
| Needs new data at **order grain** | 26 of 58 | Everything counting orders, pickups, deliveries, items, upsell, or saved sales (#1–8, #18–20, #30–33, #36–44, #51–54) — our `sales_day` is day × entity aggregate; these need an order/event table |
| Needs a new **customer dimension** | 6 of 58 | New Buyers / Total Buyers / % New-to-File (#15–17, #27–29) — no customer identity exists anywhere in our schema |
| Defer (incomplete in the source itself) | 3 families | Appointments (#59..x), Virtual Selling (#60..x), Ship-from-Store (#61..x) |

**Bottom line: the v1 build's channel model (stores *or* ECOM) has no representation of store↔online interaction, which is the entire subject of this BRD.** The gap is structural (schema), not metric-formula-level. That is also the good news: it lands exactly on Strategy Pillar 5 — the flash is a data spine, and this is the spine's first requested extension.

## 3. What our build already handles well (concepts, not numbers)

1. **Dual-basis honesty (BR-4) generalizes cleanly.** The BRD's central distinction — BOPIS #1–2 "picked up only, excludes in-progress/partial/cancelled" vs #6–8 "All-Inclusive" — is the same settled-vs-demand duality our ECOM handling already enforces. The `ecom_basis` switch in the catalog is the pattern to extend: every omni family gets a *recognized* basis (picked-up / delivered / returned) and an *all-inclusive* basis, never silently mixed.
2. **One formula home (BR-5) fixes the BRD's own redundancy.** AOV FSS and AOV Online are defined four separate times in the source (once per family, with drifting wording). In our catalog they are one function with a channel scope — the discipline the source document needed.
3. **Window language maps 1:1.** Every definition says "within the selected period of time"; our day/WTD/MTD/YTD fiscal windows are exactly that, calendar-true.
4. **"In the relevant market"** (used inconsistently in ~10 definitions) is a no-op for single-market Lumière; if multi-market ever arrives, it's a scope parameter like `region`.

## 4. What would have to change (for Opus, when authorized)

### 4.1 Schema — the real work
- **`omni_order`** (order grain): order_id, order_type (BOPIS / RTD / OOFIS / CR), store_id, customer_id, created_date, fulfilled_date (pickup/delivery), status (completed / in_progress / partial / cancelled), sales, items, upsell_sales, upsell_txn_link. One table covers #1–8, #18–20, #30–33, #51–54.
- **`return_event`** (BORIS, #36–44): return_date, store_id, customer_id, order_ref, amount, items, saved_order_link. Note this is *store-side returns of online orders* — a different concept from our existing `returns_recorded` (aggregate ECOM returns), which stays as-is.
- **`customer`** (minimal): customer_id, first_purchase_date — enough to compute new-to-file (#15–17, #27–29) deterministically. This is a **new dimension for the whole spine** and the single biggest scope decision.
- `sales_day` unchanged; omni aggregates roll up from the new tables.

### 4.2 The double-counting rule (needs an owner decision before any build)
A BOPIS order is an online-demand order fulfilled in a store; upsell is store sales triggered by a pickup. The BRD never states how these interact with headline totals. **Proposed rule (BR-9 candidate):** headline net sales are unchanged — omni metrics *attribute* existing sales, never add to them. BOPIS sales live inside ECOM demand; upsell lives inside store sales; every omni panel carries a footer stating the attribution. Without this rule, the flash's headline and its omni panel would double-count, the exact credibility failure BR-5 exists to prevent.

### 4.3 Timing bases multiply (completeness impact)
The BRD recognizes BOPIS at **pickup**, RTD at **delivery**, OOFIS at **creation** (explicitly *including* in-progress and cancelled — inconsistent with its own BOPIS treatment), BORIS at **return**. Each basis has its own maturation lag, so the completeness banner (BR-3) gains omni rows: "BOPIS pickups posted through …", etc.

### 4.4 Surfaces — protect Pillar 2
Fifty-eight tiles is the dashboard-nobody-asked-for failure mode our Strategy doc names explicitly. Recommendation: omni metrics enter the **catalog and archive** in full, but the **flash itself** surfaces omni only through the existing exception machinery — an omni mover can win a focus-panel slot (e.g. "BOPIS pickups −18% vs LY, the largest adverse omni move"), plus one omni summary line in the day flash. The full grid lives on a per-day omni page in the web archive.

## 5. Defects in the source BRD (fix in adaptation, don't inherit)

| # | Issue |
|---|---|
| #19 | "%$ RTD Sales" — stray %; it's a $ metric |
| #36 | "# Return Savings from Shipping" — labeled #, defined as $ (orders × US$7.46 label cost; make the constant a parameter) |
| #40 | "# Items **sold**" inside the BORIS *returns* family — copy-paste from OOFIS; drop or rename |
| Appointments | "% Appointments Completed with Purchase" listed twice; second should be *without* |
| OOFIS #30–33 | Includes in-progress/cancelled with no all-inclusive/recognized split — normalize to the BOPIS dual-basis pattern |
| Numbering | "59..x / 60..x / 61..x" families have no actual definitions — cannot be built from this document |

## 6. Recommended phasing (owner decision — nothing proceeds until approved)

| Tier | Scope | Why this cut |
|---|---|---|
| **Omni v1** | `omni_order` + BOPIS (#1–14) + BORIS (#36–44 ex-#40) + the attribution rule + archive omni page + seeded storylines (e.g. a BOPIS-upsell bright spot; a BORIS save-rate story) | The two families every retailer recognizes; exercises both new tables and both new timing bases |
| **Omni v2** | RTD, OOFIS, C&R (#18–35, #51–58) | Same machinery, more order types — cheap once v1 lands |
| **Customer dimension** | #15–17, #27–29 new-to-file | Deliberately its own tier: adds a dimension to the whole spine and deserves its own storyline design |
| **Deferred** | Appointments, Virtual, Ship-from-Store | Undefined in the source; revisit if a v4 of the client BRD ever specifies them |

## 7. Open questions for Barma

1. Approve the **attribution rule** in §4.2 (omni attributes, never adds)?
2. Approve the **surface policy** in §4.4 (catalog + archive in full; flash shows exceptions only)?
3. Which **tier** does Opus build first — and does the customer dimension make the cut?
4. FSS is read as *Free-Standing Stores* (i.e., our store channel) throughout — confirm.
