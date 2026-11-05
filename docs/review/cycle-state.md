# Build cycle state (orchestrator: Hermes, Simplex chat with Matt)

Cycle per batch: DEVELOPER -> orchestrator runs pytest -> REVIEWER + TESTER in parallel -> DEVELOPER iterates -> repeat until both say `VERDICT: SATISFIED` (max 3 rounds per batch, then ask the user).
Batches: 1R (review rulings R1-R9 on S0-S2), 2 (S3+S4), 3 (S5+S5b), 4 (S6). Stop before S7 (first real API call needs the user's go-ahead).

| Batch | Round | Status |
|---|---|---|
| 1R | 1 | developer dispatched |
