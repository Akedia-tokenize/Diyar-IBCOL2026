# ANNEX D.1 — Pilot-to-Scale Cost & Funding Requirements (proposed supplement)

**DIYAR / IBCOL 2026 · Working addendum · 10 November 2026**  
**Document status:** This supplement is **not yet incorporated into** the submitted `DIYAR whitepaper v2.7.pdf`. The original paper, reference experiment outputs, financial workbook and 112-number reconciliation remain unchanged.

## D.1.1. Cost definition: annualized economics versus Year-1 cash

The current financial baseline reports **USD 1,785,795.12/year for 10,000 buildings**, or **USD 178.58 per building-year**. It uses the assumptions in the published six-sheet `DIYAR_cost_model.xlsx`, including 3 staff FTE, 4 consortium validator nodes, 1 compute VM, and a physical installation / meter-binding onboarding visit priced at **USD 1,000 per building**. The onboarding fee is **annualized across ten years**, so just USD 100 per building enters the reported annual expense.

A deployment that onboards *all* buildings during its first year needs to **pay USD 1,000 each**, not only the economic annualization. Therefore:

```
Year-1 priced cash subtotal
   = Annualized economic cost
   - (number of buildings × $100 annualized onboarding)
   + (number of buildings × $1,000 upfront onboarding)
   = Annualized economic cost + $900 × newly onboarded buildings
```

The table below is **mechanical scaling of the unchanged reference architecture**, not optimized deployment engineering.

| Unchanged reference stack | Annualized cost (USD/year) | Year-1 priced cash subtotal (USD) | Year-1 subtotal per building (USD) |
| --- | ---: | ---: | ---: |
| 100 buildings | 204,829 | 294,829 | 2,948 |
| 1,000 buildings | 348,553 | 1,248,553 | 1,249 |
| 10,000 buildings | 1,785,795 | 10,785,795 | 1,079 |

The unchanged stack retains **3 FTE, 4 Besu validators, 0 notary nodes and 1 compute VM at every scale**. This is deliberately conservative in fixed-cost allocation and **not** a recommended architecture for a 100-building pilot.

## D.1.2. Illustrative phase-1 pilot (100 buildings)

The paper describes a phase-1 **witnessed transparency log + public anchoring** approach, with Besu deferred to phase 2. The separate planning case below therefore removes the four Besu nodes and hypothesizes one staff FTE while retaining one compute VM, source inspection/review assumptions, and the original historic gas basis. **Neither staffing sufficiency nor the full witnessed-log operating cost has been validated.**

| Item | Reference 100-building stack | Illustrative lean 100-building case |
| --- | ---: | ---: |
| Staff FTE | 3 | 1 (new, unvalidated assumption) |
| Besu validators | 4 | 0 (phase-1 hypothesis) |
| Compute VMs / notaries | 1 / 0 | 1 / 0 |
| Normalized annual cost | $204,829 | $77,765 |
| First-year priced cash subtotal | $294,829 | $167,765 |

**USD 167,765 is not a complete pilot budget, procurement estimate, or amount that can responsibly be requested as full funding.** It omits witnessed-log operations and several other unresolved workstreams listed below.

### Physical scale and work volumes

At the base-case workload of 5% random annual physical inspections and 0.189 slow-gate review cases per building-year:

- **100 buildings:** approximately 5 inspection visits, 18.9 review cases, and **100 initial onboarding events** if all join in the first year.
- **1,000 buildings:** 50 inspection visits, 189 review cases and 1,000 onboarding events.
- **10,000 buildings:** 500 inspections, 1,890 reviews and 10,000 onboarding events.

These workloads are not automatically handled by the assumed 3 staff FTE. Inspector capacity, contracting, approvals and staged onboarding must be validated.

## D.1.3. Unpriced costs and feasibility requirements

| Cost or dependency not yet validated | Needed before a defensible funding request |
| --- | --- |
| Meter access, owner consent and data rights | Named utility/operator interface, consent process, actual SLA and access permission |
| System integration and data normalization | Scope of work and supplier price for building registry, ingestion, security and corrections |
| Meter-to-building attestation | Quote from appropriately qualified professional; reconcile scope against the existing $1,000 onboarding assumption **without double counting** |
| Witness independence and operations | Witness count, governance, service level and service price for a phase-1 transparency log |
| HSM/PKI, key rotation and recovery | Security architecture, procurement quotes, incident handling and custody commitments |
| Legal, insurance, procurement and contingency | Local scope, owners, currency/taxes where applicable, and approval process |

The existing $1,000 **onboarding** and $1,000 **physical inspection** prices are project **assumptions**. Published prices for generic property snagging or energy audits are **not interchangeable** with an accredited meter-binding and installation check. Obtain scope-matched quotes before replacing either number.

## D.1.4. Payment and independence

A named sponsor, lender/valuer, asset owner or public innovation partner **might** finance a pilot. **No committed buyer or sponsor is established by the model.** A proposed verifier charge should be a **fixed or effort-based fee**, independent of whether a claim passes, fails or receives a lower provenance grade. This is a governance recommendation, *not* a validated revenue model.

A funding request should be conditional on four stage-gates:

1. **Scope:** identified 100-building cohort, consent, access route and pilot deliverables;
2. **Capacity:** verified staff, independent witnesses, inspectors and technical throughput;
3. **Procurement:** externally sourced quotes, security and legal commitments, contingency;
4. **Assurance:** independent rerun, fail-closed test plan and signed acceptance criteria.

## D.1.5. Provenance and limitations

**Numerical source:** [DIYAR original six-sheet financial model](../reference-and-tests/DIYAR_cost_model.xlsx), including `Inputs`, `Annual cost`, `Custody deposit` and `Review vs alpha`. See the [machine-readable scenario snapshot](../results/pilot-to-scale/scenario_snapshot.csv) and [scenario assumptions register](../results/pilot-to-scale/README.md). The supplemental spreadsheet distributed with this draft contains formula-driven calculations and a reconciliation check that recovers the original 10,000-building figure without changing the original workbook.

This supplement contains **new scenario parameters but no new independently verified supplier costs**. The 10,000-building figure also does **not** imply that all 10,000 buildings must be onboarded in one year. Phase-1 assumptions must not be presented as completed implementation or regulatory approval.
