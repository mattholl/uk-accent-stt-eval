# Plan

Details live in [implementation-plan.md](implementation-plan.md), which wins on any conflict.

## Research questions
1. What is Scribe v2's WER on regional UK and Irish English, overall and per region?
2. How does WER differ by dialect label against the Southern English comparison group? Labels (from the dataset): `southern` (comparison), `midlands`, `northern`, `scottish`, `welsh`, `irish`. Scouse, Geordie, Lancashire, Yorkshire, Northern Ireland and SSBE have no source in this dataset.
3. Which error types dominate per label (substitutions of place and personal names, deletions, insertions)? Answered descriptively from `error_pairs.csv`.
4. (Dropped for the pilot: the dataset has read speech only, so there is no read vs spontaneous comparison.)

Dropped from the earlier draft: "do public-dataset results match own recordings" (the pilot uses the open dataset; clips found online are a demo set with no statistics), and the finer regions Scouse, Geordie, Lancashire, Yorkshire, Northern Ireland and SSBE (no source).

## Hypothesis (to test, not assumed)
WER will be higher for stronger regional accents and dialect vocabulary than for the Southern English comparison group. ElevenLabs states English is in its "Excellent (<=5% WER)" tier overall but publishes no per-accent figures.

## Constraint that shapes everything
The free ElevenLabs key allows about 10,000 credits a month, roughly 2.7 hours of audio at the measured 61 credits per minute. So the code is developed against a fake backend, and real calls need an explicit flag and a minutes cap. Credits are not counted in code (no ledger, no cache; added only if needed): check the ElevenLabs dashboard. The free key's access to the STT API is unverified until the real smoke test (S7).

## Phases (build order S0 to S9, details and acceptance checks in implementation-plan.md section 12)
| Phase | Steps | Needs recordings? | Needs API key? |
|---|---|---|---|
| Scaffold | S0 | no | no |
| Normalise, score, stats | S1, S2 | no | no |
| Manifests, dummy data, fake backend, runner, end to end on dummy data | S3 to S5 | no | no |
| Notebook with graphs and audio players | S5b | no (dummy data) | no |
| Real backend and gate | S6 | no (mocked HTTP) | no |
| Real smoke test | S7 | already fetched (36 dataset clips) | yes |
| Real pilot, then optional demo | S8 | dataset clips fetched; demo only if you supply samples | yes |
| Approval gate for a full study | S9 | n/a | n/a |

## Budget (credits; details in implementation-plan.md section 9)
- About 61 credits per minute of audio, measured on this account (the 330 figure from the pricing page was wrong by 5x). Not enforced in code.
- Pilot: 36 clips, 192 s (3.2 min) = about 200 credits. The smoke-test clip is a pilot clip, so it is sent twice (a few seconds).
- Main run: 840 clips, 85.6 minutes of audio; 82.4 minutes sent = about 5,030 credits (dashboard went 217 to 5,247).
- Demo set (clips found online): under 3 minutes = under 190 credits.
- That leaves roughly 4,750 credits of the 10,000 after the main run.
- A full study of about 7.5 h = about 27,500 credits. It cannot run on a free key and needs your approval and a paid plan.
- Dollar figures are unverified and not used in any decision.

## Hypothesis testing in the pilot
None. The report gives pooled WER and the difference from the Southern baseline. Irish and Midlands (3 speakers each) are flagged `low_n`; permutation tests and Holm correction are deferred. Bootstrap confidence intervals appear only from 5 speakers per region. Permutation tests and Holm correction are deferred to a funded full study.

## Deliverables
- Scripts, config and tests (package `ukstt`)
- Raw API responses and reference transcripts
- Five CSVs per run: `utterance_scores`, `speaker_scores`, `region_summary`, `pairwise_vs_baseline`, `error_pairs`
- `notebooks/results.ipynb`: pandas and matplotlib graphs (WER by region, error mix, per-speaker spread, top error pairs) plus a clip browser with audio players
- Audio stays on disk locally, so you can listen
- No written report for now ("just give me the data")
