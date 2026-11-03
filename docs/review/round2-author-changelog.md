# Round 2: changelog, other doc edits, unsure items

=====CHANGELOG=====
- 1: pilot cap 20 min, `--max-audio-minutes 20`, delta ≤6,966. Re-ran in Python: 18×231+18×116 = 6,246; 20 min = 6,930; +36 = 6,966. Worst-case tolerance (21 min, 7,290) is rejected by the cap.
- 2, 42, 43, 41, 44 (jiwer), 45–48: adopted. SLR83 moved to the Appendix with facts kept. `full` and `spot` stages cut. `jiwer` dropped. `run_info.csv`, `rank` and rate columns cut. `norm-frozen` tag replaced by a SHA256 in the run manifest.
- 3, 4, 19, 20, 21: adopted (per-clip sum, integer charge math, `wire_params`, raw file written on cache hit, `skipped_budget` → exit 3). `--refresh` wording fixed.
- 5, 6, 7, 9, 10: adopted (pyproject only, `.env.sample`, `__main__.py`, "8 regions + baseline", stale §13 refs removed).
- 8: fixed `ID_RE` and `parse_clip_id`. Spont passage_id is `spont`.
- 11: smoke is recomputed inside `select_stage`.
- 12, 14, 15, 16, 17, 18: adopted. Detail: `HttpError.__init__`, `ReadTimeout`/`ConnectError`, a single `settle`, `credits_already_used`, fake keyed by clip_id, `validate_response`, `call_with_retry`.
- 13: adopted. Only ReadTimeout is booked, and it is not retried. ConnectError is retried and not booked. Note: the critic's "23% of quota" is wrong. 4×231 = 924, which is 9.2%; one booking is 2.3%. The policy is unchanged.
- 22–29: adopted (`'cause` rule, replace with a space, corrected test, no year pairs, number order, single `normalise.csv`, `huh`, hypothesis = `text`).
- 30: backtrace boundaries. 31: CER dropped. 32: `ValueError`, no `ref_empty`.
- 33, 34, 35–38: adopted. `MIN_SPEAKERS_CI=5`, `percentile_interval`, the permutation test, Holm and diff CI deferred. 35 and 36 become moot. No "all" stratum, no B/seed columns.
- 37: moot, replaced by "five identical speakers".
- 39: X1 marks dollar figures UNVERIFIED. 40: S0 passage task and Rainbow fallback.
- 49, 50, 51, 52: adopted (global `--config`, dummy paths, AUTO/MANUAL labels, `test_version.py`, `ledger=None` rule).
- 53: python-dotenv cut for a 6-line `.env.local` parser. 54: no subcommand → exit 2.
- 55: `[unclear]` markers banned (`W_REF_BRACKET`), so there is no `n_unclear`.
=====OTHER DOC EDITS=====
Changes vs round 1 only:
- README/plan.md: 8 regions + baseline, 5 CSV outputs, quick start without `slr83`. Drop the "RQ4 own vs SLR83" item; SLR83 is an optional phase 2.
- plan.md budget: pilot 18 min nominal, cap 20 min = 6,930 credits (ledger delta ≤6,966); smoke reuses a pilot clip; no SLR83 spot; reserve ~3,000 credits. Remove the $1.65 / $0.22/h figure or mark it UNVERIFIED.
- methodology.md: remove CER, `words[]` hypothesis extraction and the year-pair rule. Stats section: pooled WER and diff only, 95% bootstrap CI only for n≥5, permutation/Holm/diff CI deferred. Normalisation: 11 rules and one `normalise.csv`. Validity risks: SLR83 items move to the appendix.
- data-sources.md: SLR83 row becomes "optional phase 2, verified facts in the plan appendix". Drop the `source` and `region_scope` columns. Reference style guide bans bracket markers. Comma excerpt: internal use, Rainbow fallback.
- elevenlabs-api-notes.md: only ReadTimeout is booked and it is not retried; connect errors are retried and not booked; there is no tenacity.
- open-questions.md: budget line "pilot 18 min, cap 20 min, no SLR83"; remove the SLR83 zip-name/speaker-ID open item (appendix only); Comma licence: decided as internal use.
=====UNSURE=====
- Dependency pins are unverified offline; S0 must check them with `pip index versions`.
- Comma excerpt: ~100 words ≈ 40 s is a guess, and the licence is not checked (internal use assumed). The coder must copy the real text and must not invent it.
- Free-key STT access and the 330 credits/min rate are unverified until S7. The billing period start is manual.
- Rejecting a 21 min worst-case pilot may annoy the recorders. The cap could go to 21 min (7,290 credits, leaving 2,700).
- `huh` as a filler could hide a genuine "huh". It is accepted as known noise.
- Register contractions are mapped by assumption (P10). Delete the `register` rows if the user disagrees.
- Python 3.11–3.13 are untested.
