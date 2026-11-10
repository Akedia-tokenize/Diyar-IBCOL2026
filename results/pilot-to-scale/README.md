# Pilot-to-Scale financial supplement

**Status: proposed Annex D.1; not yet incorporated into the original v2.7 PDF.**

[**Read the proposed financial appendix**](../../paper/Annex-D.1-Pilot-to-Scale-SUPPLEMENT.md) · [**Download the scenario CSV**](scenario_snapshot.csv) · [**Open original cost model**](../../reference-and-tests/DIYAR_cost_model.xlsx)

This supplement examines what changes when all buildings are onboarded in a program's first year, rather than spreading onboarding across the 10-year amortization period. The published model retains a USD 178.58 normalized annual cost per building at 10,000 buildings.

| Buildings | Full-stack annual economic cost | Full-stack Year-1 priced cash |
| ---: | ---: | ---: |
| 100 | $204,829 | $294,829 |
| 1,000 | $348,553 | $1,248,553 |
| 10,000 | $1,785,795 | $10,785,795 |

A separate *hypothetical* 100-building phase-1 case, **1 FTE / zero Besu validators / one compute VM**, calculates **$167,765** Year-1 priced cash. This is **not** a complete pilot quote because witnessed-log costs, HSM/PKI, data access, integration, legal and procurement remain unpriced.

The Excel workbook companion, `DIYAR_Pilot_to_Scale_Financial_Supplement_v1.xlsx`, is distributed separately to the project team. It is **not included as a binary in this GitHub update**. It contains six formula-driven documentation/scenario/check sheets and leaves the original six-sheet workbook unchanged.

**Cost accounting:** Normalized annual expense recognizes $100/building/year of a one-time $1,000 onboarding cost; the first-year cash bridge instead recognizes the full $1,000 for each newly enrolled building.

**Sources and caveats:** These are derivatives of the [original workbook](../../reference-and-tests/DIYAR_cost_model.xlsx), not a fresh estimate from signed Dubai supplier quotes. Generic UAE field-inspection and building-audit quotations differ in scope and must not be substituted without procurement.
