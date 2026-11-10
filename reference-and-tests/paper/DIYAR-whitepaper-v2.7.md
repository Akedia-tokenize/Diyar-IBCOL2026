# DIYAR: A Provenance-Graded Evidence Layer for Sustainability Claims in the Built Environment
Fatemeh Zahra Bazrgar
Faculty of Humanities and Social Sciences, Kharazmi University
No. 43, Shahid Mofatteh Ave., Tehran, Iran
github.com/Akedia-tokenize/Diyar-IBCOL2026

**Abstract—** Buildings account for roughly a third of energy-related CO2 emissions, so climate targets depend on performance claims about individual assets being true. Often they are not: certified efficient dwellings have been measured consuming 39–54% more than their certificates predict, and a 2020 European Commission sweep judged 53.3% of environmental claims vague, misleading or unfounded. These claims now carry dated consequence: from 30 April 2026 a valuer must assess sustainability’s effect on value; for older buildings the EU Taxonomy accepts top-15% performance on “adequate evidence” it does not define; and the UAE federal climate law has required emissions reporting since 30 May 2025. What is missing is not data but provenance: proof that the data received is the data the meter sent, a record of which part of a rating rests on measurement and which on an interested party’s assertion, and a way to reproduce the result years later. This whitepaper designs and builds an evidence layer that grades every input by the path it arrived through, commits the record under a signed daily root for anchoring on a public chain, and makes every output independently replayable. On real, unlabelled metering data, seasonal drift pushes one-time calibration to 17.4% alerts against a nominal 5%, and recent-window calibration brings them back to about 5%; with one manipulated building among honest peers, quarterly testing reaches 80% detection only at about a 25% under-report; and a 17-mode failure taxonomy resolves at 4 tiers. The cost is about $179 per building-year under stated assumptions, nearly all of it people and physical inspection.

**Keywords—** SDG 9, SDG 11, SDG 13, provenance grading, verifiable evidence, conformal prediction, building performance gap, bitemporal replay

## I. Introduction

Decarbonising the built environment is a first-order climate objective: buildings and construction account for roughly a third of global energy-related CO2 emissions and about 32% of global energy demand [1]. Nearly every instrument aimed at it — retrofit subsidy, green lending, taxonomy alignment, performance standards — allocates capital on a claim about how one building performs. That claim layer is measurably unreliable: certified dwellings have been measured consuming 39–54% more than their certificates predict [2], and a 2020 European Commission assessment judged 53.3% of environmental claims vague or misleading, with up to 40% unsubstantiated [3]. When the claim is wrong, capital is misdirected and the emissions reduction is recorded rather than achieved; an evidence layer is therefore a climate instrument, not an administrative one.

The data largely exists. Dubai alone has more than 2 million smart electricity and water meters, monitored remotely every 15 minutes [4], and EU rules already set procedures for an eligible party’s non-discriminatory access to metering data [5]. What is missing sits in 3 places. Nothing between meter and report proves that the figure delivered is the figure the device produced; no rating discloses how much of itself rests on measurement and how much on an interested party’s word; and no published number can be recomputed a decade later, because its inputs, model and corrections were never pinned to a version.

We design and build that layer and test it on real metering data. Our contributions are: (1) a 7-level provenance grade ladder that shows, for every number, the path it came by and what it still rests on; (2) a 17-mode failure taxonomy that assigns each mode to the cheapest sufficient tier — 12 rules, 1 structural mechanism, 3 statistical tests and 1 learned model; (3) a measured detection limit: with one manipulated building among honest peers, quarterly testing reaches 80% detection only at about a 25% under-report, and less as manipulation becomes common, so below that limit provenance and random inspection carry the claim; and (4) a reference implementation on real data that carries grades end to end and replays any past output as it was known at the time.

## II. Problem Statement

The obligation is dated and specific. From 30 April 2026 a RICS valuer must assess sustainability’s effect on value [6]. For pre-2021 buildings the EU Taxonomy accepts top-15% performance as an alternative to EPC class A, “demonstrated by adequate evidence” it does not specify. Since 30 May 2025 the UAE federal climate law has required every entity to measure and report emissions, with its verification standard still being drafted [7]. Dubai Law No. (3) of 2026 requires a structural quality and safety certificate once a building is 20 years past completion and directs the Municipality to build a unified building database [8]; it is not an energy rule, but it builds the data infrastructure an evidence layer can connect to. Each demands evidence; none defines it (Annex F). The Green Claims Directive, meant to harmonise substantiation, has stalled since the Commission announced its intention to withdraw it in June 2025, so the gap stays open.

### A. Why Existing Instruments Do Not Close It

First, the performance gap is unpredictable, not merely large: across 62 buildings the mean deviation exceeded 34% with a standard deviation of 55% [9], so no constant correction removes it. Second, ratings hide their composition: no valuer, lender or supervisor can see how much of a rating rests on measurement and how much on the word of the party that benefits — the exposure the 2024 standards for automated valuation models address [10]. Third, a property is a story that keeps unfolding, but a certificate is one frame of it — Dubai’s new safety certificate runs for up to 10 years [8]. An evidence layer records the story, not the frame.

### B. The Custodian Problem

The fourth obstacle sets the architecture: every party able to hold the record is a party to the dispute (Fig. 3).

- *Developer:* sells fast and high, and exits at handover.
- *Owner:* wants a high sale price and a low tax assessment — 2 numbers in 2 contexts.
- *Operator:* wants low maintenance costs, and supplies the self-declared fields.
- *Bank and insurer:* interested in the decisions the record feeds.
- *Certifier:* interested in its certificate staying valuable.
- *Valuer:* as custodian, would audit its own work.
- *Regulator:* incentive-neutral, but its authority stops at the border.

Neutrality cannot be promised; it has to be structural.

*[Fig. 3 — figure]* Fig. 3 Trust boundaries: which way each party’s interest can push the claim; only the owner pushes both ways, in two contexts.

## III. Proposed Solution

### A. Evidence Grading

Every field is graded by the path through which it arrived, not by the plausibility of its value; Table I states, for each grade, what the reader still relies on.

**TABLE I. Evidence Grades and Residual Trust Assumptions**

| Grade | Path | Residual assumption |
|---|---|---|
| A1 | Device signature | Where the device is |
| A2 | Authoritative feed | Correctness of source |
| A2− | Endpoint proof | The notary |
| B | Accredited third party | Competence, independence |
| B− | Unstructured document | Above, plus extraction |
| C+ | Owner-uploaded document | Chain of custody |
| C | Self-declared | Everything |

The ladder is a projection of a plane: who asserts a field, and what a third party needs to check it (Fig. 2). The qualified grades come from that plane — A2− is an authoritative assertion verified through a notary, C+ a third party’s document whose custody runs through the beneficiary — which is why the residual assumption travels beside the grade. Grades propagate: a derived field inherits the grade of its weakest input, and an output also carries its composition — say, 60% of the energy it reports resting on A-grade evidence and 11% on self-declaration. Self-declared data is kept at the lowest grade rather than refused, because refusing it only moves it off the record, where it is ungraded and invisible.

Even A1 carries a residual assumption: a signed reading assumes the meter is where the registry says, because the signature covers the reading, not the location (Section VI).

*[Fig. 2 — figure]* Fig. 2 Two-dimensional evidence grade space. The 7-level ladder is this plane projected onto a line; A2− and C+ exist only because the projection loses one axis.

### B. System Architecture

The system has 5 layers (Fig. 1). Intake normalises meter telemetry (DLMS/COSEM [11]), operator interfaces [5], endpoint proofs, accredited assessments, bills, manual entry and authoritative feeds, and grades each field on arrival. A validation gate admits, flags or rejects. A temporal engine fits each building a baseline from its own history [12] and expresses each period as a residual, so a hot summer is not read as a failure; a baseline is accepted only if it meets ASHRAE Guideline 14 [13]. A commitment layer signs the root of the graded record daily for anchoring on a public chain, and a replay layer reconstructs any past output from committed state.

The gate has 2 parts with 2 outputs. The fast gate compares each day with the prior 28 days and emits only a *watch signal*; it opens no human case. The slow gate compares, each quarter, the building’s mean residual over the last 90 days with that of its committed reference quarter and ranks this drift against peers on the same site; at α = 5% it opens a *review case*. The words differ because the counts differ: about 18 watch signals per building-year against 0.189 review cases. Otherwise only a rule failure opens a human case.

*[Fig. 1 — figure]* Fig. 1 The architecture as two planes. The data plane never leaves custody; the proof spine takes one leaf per stage, including the gate’s own decision, and converges on one daily anchor. Dashed: not deployed.

Machine learning scores patterns in the gate and estimates unmeasured fields, recorded as estimates with their own grade; projections are emitted as intervals and never committed, since a projection recorded as fact becomes, one revision later, a fabricated measurement. Replay is bitemporal: each record carries a valid time, when the fact was true, and a record time, when the system learned it, so a late correction cannot silently rewrite history.

### C. Validation Gate

We enumerated 17 ways a record can be wrong across the 7 intake paths and assigned each to the cheapest tier that suffices, because each higher tier is less auditable (Table II; Annex A gives the method, path and implementation status of each mode).

**TABLE II. 17 Failure Modes in 4 Tiers**

| Tier | Failure modes |
|---|---|
| Rule (12) | Device clock drift; missing intervals; scale or unit error; stale operator cache; delivery-point ID mismatch; document forgery; post-signature tampering; wrong building or expired certificate; bill for another period or building; typing or unit slip; authoritative-feed lag; selective deletion of months |
| Structural (1) | Notary collusion — multi-notary committee with slashing |
| Statistical (3) | Copy of a prior period; optimistic rounding; physical meter relocation — drift against the committed baseline |
| Learned (1) | Implausible or contradictory inspector content — text model (not yet built) |

No rule mode needs a model. Selective deletion is a rule, not a pattern: a deleted month cannot be found from the remaining data (E3b), so all 12 bills are required. No analysis exposes a colluding notary, so a multi-notary committee with slashing moves the assumption from one party’s honesty to the cost of coordinating several. Against an adaptive machine adversary, rules and cryptography hold because their condition is structural, while statistics and models only cap its gain — which is why the slow gate’s reference is a committed, immutable baseline (Section VI).

The gate turns a score into a decision by split conformal prediction [14]: flagging when the p-value is at most α bounds the probability of flagging a clean record by α, distribution-free — but under exchangeability. We name the assumption because it can fail; on seasonal data the alert rate triples unless calibration is recent (Section V).

*[Fig. 4 — figure]* Fig. 4 Decision path through the validation gate, with the fast and slow gates. The counts below are the derivation: 12 rules, 1 structural mechanism, 3 statistical tests and 1 learned model.

## IV. Implementation

*Reference run.* We built a reference implementation, DIYAR-ref, choosing each component against a stated alternative, and ran it on 3 buildings of the Fox site in BDG2 [15] from 1 January to 31 March 2017, with real readings and weather and simulated keys, through intake, grading, rules, the fast gate, signed daily commitment and replay; the slow gate was evaluated offline (Section V). It produced 91 signed days, 645 fields and 647 versions (1.74 MB of records, 5.46 MB of ledger); the gate admitted 201 items and raised 1 rule flag and 8 conformal flags. Every replay check passed: roots matched on all 91 days; January as known on 4 February reproduced the published hashes, and as known today differed only where late readings arrived (coverage 99.06% → 99.87%); a 10% edit was caught by both the meter signature and the root; one field verified alone with a 320-byte proof, and a never-entered field was proven absent. All 8 negative checks (missing weather, repeated hours, 2,000 malformed proofs) fail closed (Annex B). Authoritative claims are signed with their unit and validity and each reading is bound to its own signed installation certificate (108 targeted tests); the baselines, trained on 2016 data never committed as signed records, are graded C, as are the performance figures built on them. Code, data and run logs are public at [github.com/Akedia-tokenize/Diyar-IBCOL2026](https://github.com/Akedia-tokenize/Diyar-IBCOL2026), and [akedia-tokenize.github.io/Diyar-IBCOL2026](https://akedia-tokenize.github.io/Diyar-IBCOL2026/) reruns the checks in any browser.

*Intake and commitment.* The top grade requires DLMS Security Suite 1, not the symmetric Suite 0, which cannot give non-repudiation. The record is a sparse Merkle tree keyed by field identifier, which gives selective disclosure of one field, non-membership proofs for absent required fields, and schema extension without re-keying; KZG commitments were rejected because a break of their assumption is retroactive over a 60-year horizon (Annex E). With a 256-bit hash, Grover’s search leaves about 2^128 work for a preimage [16]; collision search already costs about 2^128, and known quantum algorithms do not make it cheaper once their memory is counted (Annex E).

*Signatures.* Each reading carries the device’s ECDSA P-256 signature (64 bytes on a 43-byte record); one SLH-DSA-256s signature (FIPS 205 [17], 29,792 bytes) covers the global daily root and so protects every reading long-term, as long as SHA-256 and key custody hold (Annex E). Signing each reading with SLH-DSA-128s instead would raise 60-year storage from 11.25 TB to 837 TB.

*Anchor.* The design stores the daily root in an Ethereum contract’s state, once per day, and the root must cite the previous one or the transaction reverts: the non-equivocation of Catena [18], enforced by contract logic, where an event-only anchor would merely make equivocation detectable. The chain is chosen for longevity, not throughput — 32 bytes a day that must verify for 60 years — and each anchor’s proof bundle (transaction, receipt, receipt proof, block header) is kept in custody, as no chain promises to serve its history forever [19].

*Besu.* A permissioned QBFT chain orders writes once at least 4 independent consortium members exist; integrity comes from the tree and the anchor, and parameter governance, including the timelocked α, stays on Ethereum mainnet. The Dubai pilot runs on a witnessed transparency log plus the anchor; Besu enters in phase 2.

*Calibration, verification and scope.* Baselines are committed before the period they judge. Calibration uses a recent rolling window, not all labelled data, because one-time calibration over-alerts on seasonal data (E2); feedback updates calibration only, never the model, so reproducibility does not decay. Test vectors for 4 historical verifier failures all pass (Annex B). Keys were simulated; the anchor contract is built and tested on a local EVM, not deployed; Besu, RS custody, predicate proofs, public-randomness draws and the inspector-content model are designed, not built; the scope was 3 buildings over 3 months.

## V. Evaluation

Experiments use real, unlabelled BDG2 data [15]. The main site, Fox, is the dataset’s hottest (mean 25.1 °C) but cooler and drier than Dubai. Every E2–E4 result regenerates byte for byte from the 3 raw BDG2 files (Annex C).

*Conformal calibration (E2).* For the 106 Fox buildings that passed ASHRAE 14 (median CV(RMSE) 14.9% on the hourly 2016 fit; 13.2%, with NMBE −1.5%, on daily 2017 data out of time), baselines were fitted on 2016 and 4 calibration schemes run on March–December 2017 at α = 5%. One-time calibration flagged 16.3% of building-days and same-season (Mondrian) calibration 14.5%, because its 2016 scores are smaller than 2017’s. Recency brought observed alerts back to about 5% — rolling 28-day window 5.3% (worst month 8.4%), ACI [20] 5.1% (Annex C). Without labels these are alert rates, not false positives, and ACI targets 5% by design; the one-time excess is what broken exchangeability predicts, and recency removes it. Across all 12 sites (801 buildings) the rates were 17.4%, 16.8%, 5.4% and 5.05%.

*Detection limit (E3).* We altered clean data from a random day onward in random buildings. With one manipulated building among honest peers, the slow gate’s one-sided quarterly test at α = 5% (false-flag rate 4–5%) detects a 20% under-report with 67% power and a 30% one with 89% (Table III), and reaches 80% at about a 25% under-report (81% in a further 1,000 runs at 25%); clean quarter-to-quarter drift has a standard deviation of 13.3%. The test is one-sided in the direction the claim gains from — under-reporting for green-loan and subsidy claims (Fig. 3); a two-sided test catches the 20% under-report 9% of the time. Meter relocation (a signed meter reading a donor’s rescaled load; Annex C) adds the donor’s own drift: small relocations are caught more often than small under-reports, large ones slightly less.

**TABLE III. Detection Power (Slow Quarterly Gate, One-Sided, α = 5%, Fox)**

| *(a) One manipulated building, 1,000 runs per point* | | | | | | |
| Size | 5% | 10% | 15% | 20% | 30% | 40% |
|---|---|---|---|---|---|---|
| Under-report | 10% | 19% | 38% | 67% | 89% | 97% |
| Relocation | 23% | 33% | 46% | 57% | 79% | 92% |
| *(b) 20% under-report by prevalence, 300 runs per point* | | | | | | |
| Share | 1% | 5% | 10% | 20% |  |  |
| Detected | 70% | 49% | 32% | 20% |  |  |

*At 1% (1 of 106 buildings) (b) repeats (a); 70% vs 67% is Monte Carlo noise.*

When manipulation is common, peer comparison weakens: at 10% prevalence the 20% under-report is caught 32% of the time. Below this limit no statistical test carries the claim reliably; provenance grading and independent random inspection do. That is why evidence must be graded, not merely validated. In E3b, copying was always caught and rounding 98% of the time.

*Cost.* The cost of this design is human, not cryptographic. For 10,000 Dubai buildings it is about $1.79M a year, or $179 per building-year — about 12% of an ASHRAE Level 1 audit; technology is 0.5% of it, people and physical inspection 99.5%. The figure is a structured estimate: random inspection, onboarding and staff are assumptions making up 94.1% of the total, and even the review line rests on 4 assumptions. Varying inspection over 2–10% of buildings at $500–2,500 moves the figure between $139 and $379; varying onboarding too, between $39 and $479, with technology below 2.4% throughout. If the pilot confirms DEWA’s installation registry as an A2 source, onboarding falls toward zero and the figure toward $79. Anchoring costs about $29 a year at the contract’s measured gas (Annex D).

*Custody.* Sixty years of signed 15-minute, 5-channel meter telemetry for 10,000 buildings is 11.25 TB in one copy; the post-quantum layer adds only 0.65 GB, and the 2.49× overhead comes from device signatures. An RS(10,4) code replaces triple replication: 15.75 TB instead of 33.75 TB. The 14 shards are encrypted before encoding and spread over at least 4 independent custodians, none holding more than 4, so the system tolerates the loss or withholding of any one custodian, and the residual assumption of custody becomes the key, not the data (Annex E). A deposit prepaid at issuance, scaled to data volume, decouples storage from the operator’s survival; it prices storage only, at today’s prices (Annex D).

*Related work.* DIYAR’s commitment layer descends from key transparency, which also keeps a log of map roots [21]; it adds a per-field grade with its residual assumption, valid time separate from record time, and replay of derived numbers. Against a witnessed log, the public anchor adds one permissionless checkpoint that no operator or consortium member can fork, withdraw or outlive; Annex H compares the two under equivocation, deletion and operator failure. A zkTLS endpoint proof [22] is exactly the A2− path (Annex H).

*Pilot path.* Three phases, each with a pass criterion; legal basis in Annex F. *Phase 0*, subject to DEWA granting data access, repeats E2 and E3 on anonymised smart-meter records, as DEWA’s R&D Centre has done in a published study [23]; pass: baselines meet ASHRAE 14, the rolling gate stays below 10% each month, and Dubai’s noise floor is measured. *Phase 1* shadow-runs consenting buildings without affecting decisions; pass: replay reproduces 100% of reports and onboarding cost is measured. *Phase 2* adds the consortium and qualified signatures.

## VI. Discussion

The design does not make sustainability data accurate; it makes provenance legible, derivation reproducible without trusting the operator, and the grade of every input visible in the output — modest guarantees, but the ones the instruments now in force require and none supplies.

### A. What This Architecture Does Not Solve

*Physical binding.* A signature proves which device produced a reading, not where it is. Three utility methods shrink the gap: tamper events logged by the meter and committed under its signature [24]; voltage correlation with neighbouring meters, which reveals the transformer and phase [25]; and energy balance against the transformer meter. Together they narrow the assumption to “under the same transformer, with tamper sensors disabled”, on A2 utility evidence. In Dubai, DEWA’s installation registry would move it to “the registry is correct” (A2), so a building-level figure would be A2 even when the reading is A1. DIYAR-ref carries each meter’s signed installation certificate grade (B) into building-level energy.

*Omission.* A sparse Merkle tree proves absence, not intent. At enrolment DIYAR commits the list of mandatory fields before the period and the owner accepts it, and the enrolled population is reconciled against the registry; a missing field is then proven by non-membership and triggers a pre-announced consequence — dependent grades drop and a review case opens. Intent stays unproven, and the duty binds only members until a law extends it.

*Consortium legitimacy.* A permissioned ledger is only as neutral as its membership. In phases 0 and 1 a single operator writes, and neutrality rests on the public anchor, independent replay and witnesses.

*Calibration contamination.* Measured in E3: the fast gate absorbs a sustained 20% under-report, flagging it in 54% of runs on day 0 but at the clean 5.5% after day 28, as manipulated history enters its window — safe for the owner, unsafe for the lender. The slow gate’s committed baseline does not absorb the shift (Table III).

*Honest majority and adaptive cheats.* A patient cheat below the limit, or one of many (Table III(b)), escapes statistics. Independent, score-independent random inspection is therefore not a supplement to the gate but the only mechanism that makes sub-threshold manipulation detectable — a necessary condition of the design.

## VII. Ethical Considerations

*The model never decides.* The gate emits a flag and a record — p-value, model and calibration versions, reference peers — and a published rule turns it into an outcome. An owner must be able to contest something stated, and a rule can be argued with where a model cannot.

*The product is an evidence file.* DIYAR delivers the file and its grade composition; the valuer values and signs. It produces no value-adjustment factor, which would be a direct valuation input.

*Neutrality is a revenue constraint.* No revenue may depend on the size of the number produced; baselines are committed before any commercial relationship; disputes are resolved outside the operator; no token claims savings cash flow; and replay must run independently of the operator’s servers. The first constraint is why DIYAR forgoes efficiency-financing revenue, the most profitable position in the chain.

*α has a price.* α trades disturbance to innocent owners against detection — a policy choice — so it is published, timelocked and changed only through governance. The peer-rank test selects αn buildings, rounded down, at every quarterly test whatever their honesty — 5 of 106 at α = 5% — so the slow gate opens 0.189 review cases per building-year, each taking 2 reviewers 1 hour at $25.54, or $9.65 per building-year. α = 1% cuts cases to 0.038 but detection of a 20% under-report from 67% to 8%. The load, 47 cases per quarter per 1,000 buildings, is set by the rule and so budgetable in advance (Annex G).

*Inspection by public randomness.* Buildings for physical inspection are drawn from a public, verifiable randomness source and the draw is committed on chain, so the operator cannot choose and the owner cannot foresee.

*Consent and fairness.* Selective disclosure reveals one committed field, such as a lease clause, without the rest of the contract; proving a threshold without revealing the value needs a zero-knowledge range proof (designed, not built). Mondrian conditioning serves fairness across groups, not validity (E2); its wider sets for small groups are published, not hidden.

## VIII. Conclusion

The obligation to evidence sustainability performance is dated, in force and unaccompanied by a method; what is missing is not data but provenance and reproducibility. This whitepaper designed, built and tested on real data an evidence layer that grades every input by its path and names the residual assumption of every grade, including the strongest. Detection has a measured limit: with one manipulated building among honest peers, quarterly testing reaches 80% detection only at about a 25% under-report, and less as manipulation spreads. Below that limit, provenance grading and independent random inspection carry the claim — which is why evidence must be graded rather than merely validated. The cost is human: about $179 per building-year under stated assumptions, nearly all of it people and physical inspection. Almost every component is adopted rather than invented; the contribution is the thin layer that does not yet exist. Its principal limitation is also its thesis: an evidence layer is worth little in its first year and more every year after, because what it accumulates is history.

## References

[1] United Nations Environment Programme, “Global status report for buildings and construction 2024/2025,” UNEP, Nairobi, Kenya, 2025.
[2] B. Coyne and E. Denny, “Mind the energy performance gap: Testing the accuracy of building energy performance certificates in Ireland,” *Energy Efficiency*, vol. 14, no. 6, art. 57, Aug. 2021, doi: 10.1007/s12053-021-09960-1.
[3] European Commission, DG Justice and Consumers, “Environmental claims in the EU: Inventory and reliability assessment — Final report,” Publications Office of the EU, Brussels, 2020.
[4] Dubai Electricity and Water Authority, press release on smart-meter growth, Dubai, UAE, 16 Sep. 2022.
[5] “Commission Implementing Regulation (EU) 2023/1162 on interoperability requirements and procedures for access to metering and consumption data,” *Off. J. Eur. Union*, Jun. 2023.
[6] Royal Institution of Chartered Surveyors, *ESG and Sustainability in Commercial Property Valuation*, RICS Global Standard, 4th ed., London, U.K., 2025.
[7] United Arab Emirates, *Federal Decree-Law No. (11) of 2024 on the Reduction of Climate Change Effects*, 2024 (in force 30 May 2025).
[8] Government of Dubai, *Law No. (3) of 2026 Concerning the Quality and Safety of Buildings in the Emirate of Dubai*, Dubai, UAE, issued 27 Feb. 2026.
[9] C. van Dronkelaar et al., “A review of the energy performance gap and its underlying causes in non-domestic buildings,” *Front. Mech. Eng.*, vol. 1, art. 17, Jan. 2016, doi: 10.3389/fmech.2015.00017.
[10] Board of Governors of the Federal Reserve System et al., “Quality control standards for automated valuation models,” Final Rule, *U.S. Federal Register*, Aug. 2024.
[11] DLMS User Association, *DLMS/COSEM Architecture and Protocols*, Green Book, Geneva, Switzerland, 2023.
[12] CalTRACK Working Group, “CalTRACK methods, version 2.0,” 2020.
[13] *Measurement of Energy, Demand, and Water Savings*, ASHRAE Guideline 14-2014, ASHRAE, Atlanta, GA, USA, 2014.
[14] V. Vovk, A. Gammerman, and G. Shafer, *Algorithmic Learning in a Random World*. New York, NY, USA: Springer, 2005.
[15] C. Miller et al., “The Building Data Genome Project 2, energy meter data from the ASHRAE Great Energy Predictor III competition,” *Sci. Data*, vol. 7, art. 368, 2020.
[16] L. K. Grover, “A fast quantum mechanical algorithm for database search,” in *Proc. 28th ACM Symp. Theory of Computing (STOC)*, 1996, pp. 212–219.
[17] *Stateless Hash-Based Digital Signature Standard*, FIPS PUB 205, National Institute of Standards and Technology, Aug. 2024.
[18] A. Tomescu and S. Devadas, “Catena: Efficient non-equivocation via Bitcoin,” in *Proc. IEEE Symp. Security and Privacy (S&P)*, 2017, pp. 393–409.
[19] Ethereum Foundation, “Partial history expiry announcement,” *Ethereum Foundation Blog*, Jul. 2025 (EIP-4444).
[20] I. Gibbs and E. Candès, “Adaptive conformal inference under distribution shift,” in *Proc. Adv. Neural Inf. Process. Syst. (NeurIPS)*, vol. 34, 2021.
[21] M. S. Melara et al., “CONIKS: Bringing key transparency to end users,” in *Proc. 24th USENIX Security Symp.*, 2015, pp. 383–398.
[22] TLSNotary, project documentation, 2026. [Online]. Available: https://tlsnotary.org
[23] P. Manandhar et al., “Understanding energy behavioral changes due to COVID-19 in the residents of Dubai using electricity consumption data and their impacts,” *Energies*, vol. 16, no. 1, art. 285, 2023, doi: 10.3390/en16010285.
[24] S. McLaughlin et al., “A multi-sensor energy theft detection framework for advanced metering infrastructures,” *IEEE J. Sel. Areas Commun.*, vol. 31, no. 7, pp. 1319–1330, 2013.
[25] W. Luan et al., “Smart meter data analytics for distribution network connectivity verification,” *IEEE Trans. Smart Grid*, vol. 6, no. 4, pp. 1964–1971, 2015.
