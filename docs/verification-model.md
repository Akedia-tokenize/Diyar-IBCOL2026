# Evidence grades and verification

A grade describes the path a number arrived through and what you still have to trust. It is not a score of truth.

| Grade | Path | What you still trust |
|---|---|---|
| A1 | Device signature | Device identity and physical location |
| A2 | Signed authoritative source | Correctness of the source |
| A2− | Endpoint proof | The notary |
| B | Accredited third party, such as a signed installation certificate | Competence and independence of the third party |
| B− | Third party document, extracted | The third party and the extraction |
| C+ | Document uploaded by the owner | Chain of custody |
| C | Typed in, or derived from data never committed as signed records | Everything |

A building figure takes the weaker grade of its inputs. January energy for the Fox office building is B: the readings are A1 and the meter certificate is B.

## Checks in the browser

The Verify page runs 11 checks on the published files:

1. Daily chain commitments
2. ECDSA P256 daily signatures
3. SLH DSA daily signatures
4. Record canonical hashes
5. Reconstructed signed sparse Merkle roots
6. Signatures of the authoritative sources
7. Installer certificates that bind each meter to its building
8. Hashes of the published January reports
9. A proof that a field is absent, for the Renna occupant count
10. A selective disclosure inclusion proof
11. All 6,497 hourly meter signatures, in the deep check

Each check shows Passed, Failed or Not run, and only after it has really run. Green, red and yellow are used for check results only.

## What a valid signature does not prove

A signature proves who signed a value. It does not prove where the meter is, that it was calibrated, or that the method behind a claim is right. The tamper lab shows this with 6 cases: the checks catch 5, and the lying meter that signs a wrong reading is not detectable by cryptography. Physical binding and inspection answer that case.
