# Critique of docs/implementation-plan.md

I checked the budget arithmetic by running Python. I did not run the plan's code or make API calls. The plan is not ready to code. Fix the 3 blockers and the SHOULD items marked in the top 10 first. Several of the cuts also remove coder-facing ambiguity, not just work.

## A. Contradictions and arithmetic

1. **BLOCKER, §6 gate, §9, §12 S8, §5 stage selection.** The pilot budget gate cannot pass on real recordings.
   - `--max-audio-minutes 18` and "ledger delta <= 6,237" assume exactly 18.000 min.
   - Clips are allowed ±5 s each (read 40±5, spont 20±5), and `select` allows up to 18.9 min.
   - Any real recording set slightly over nominal fails its own gate.
   - Per-clip `ceil` also breaks the 6,237 figure. I computed 18×231 + 18×116 = **6,246**, which is above 6,237.
   - Fix, §5 pilot bullet: "Error if total duration > 20.0 min."
   - Fix, real runs: `--max-audio-minutes 20` for the pilot.
   - Fix, S8: "ledger delta <= 6,966" (6,930 for 20 min, plus 36 for per-clip rounding).
   - Fix, §9: add a row "Pilot cap 20.0 min = 6,930 credits".
   - If SLR83 is deferred (item 18), the reserve is then about 3,000 credits.

2. **SHOULD, §9 spot row and §5 SLR83 clips.** Spot clips are 18–22 s each.
   - Six clips can total 132 s, which is above `--max-audio-minutes 2` and above the 693-credit figure.
   - Per-clip ceil gives 6×116 = 696.
   - Fix: gate `--max-audio-minutes 2.5` and state "about 696–800 credits". Or cut SLR83 (item 18).

3. **SHOULD, §6 gate step 4.** "`charge_credits(that sum)`" is ambiguous.
   - Ceil of the sum differs from the sum of per-clip ceils.
   - Fix wording: "`sum(charge_credits(c.duration_s) for c in todo)` must be <= `ledger.remaining()`."

4. **SHOULD, §3 `charge_credits` and constants.** The charge uses a float formula.
   - It happens to give exact results for 20 s, 40 s and 60 s. I checked: 40 s gives 231.0 and 20 s gives 115.5.
   - It is still fragile for other durations.
   - Fix: `LEDGER_FACTOR_PCT: int = 105` and `credits = -(-round(audio_seconds*1000) * credits_per_min * factor_pct // 6_000_000)`.
   - Equivalently, keep floats but round to 6 dp before `ceil`.
   - Change `StudyConfig.ledger_factor` to the same integer.

5. **SHOULD, §1 header and §4.** "Python >=3.11" and "sandbox 3.14.9; other versions untested" contradict each other.
   - Fix: "`requires-python = '>=3.11'`. Developed on 3.14.9. Code must avoid 3.12+ syntax (no `type` statements, no PEP 695 generics)."
   - The pins (`requests==2.34.2`, `pytest==9.2.0`, and others) could not be verified offline. Add: "Verify each pin with `pip index versions` in S0, and bump if one does not exist."

6. **SHOULD, §3 layout and S0.** The dependency files disagree.
   - The layout lists `requirements*.txt` and also pyproject pins, and S0 uses `pip install -e .[dev]`.
   - Fix: delete `requirements*.txt`. Put the pins in `pyproject.toml` under `[project].dependencies` and `[project.optional-dependencies].dev`.
   - Add `src/ukstt/__main__.py`. The layout lacks it, but §11 promises `python -m ukstt`.
   - Add `[tool.setuptools.packages.find] where=["src"]`.

7. **SHOULD, §3 line 61.** The `.env.example (ELEVENLABS_API_KEY=*** line is malformed. The repo actually contains `.env.sample`, not `.env.example`.
   - Fix: use `.env.sample` throughout.
   - Fix: `.gitignore` rule `.env*` except `.env.sample`.
   - S0 acceptance: `git check-ignore .env .env.local`.

8. **BLOCKER, §3 `ID_RE`.** The comment says "ids must not contain `__`", but the regex allows it.
   - It also allows a trailing `_`, so `a_` + `__read` becomes `a___read`, which is ambiguous to split.
   - Fix: `ID_RE = r"^(?!.*__)[a-z0-9](?:[a-z0-9_]{0,46}[a-z0-9])?$"`.
   - Add: "`parse_clip_id(s) -> (speaker, task, passage)` uses `s.split('__')` and requires exactly 3 parts."
   - Apply `ID_RE` to speaker_id and passage_id, not to clip_id (which can be about 100 characters).
   - Missing from §5: a rule that `passage_id` for spont is the literal `spont`.

9. **NIT, D2 and §2.** D2 writes "ni (Northern Ireland)" while regions.csv `display_name` is "Northern Irish".
   - Fix: display_name = "Northern Irish English" everywhere, and add: "region_id `ni` is the only abbreviation".
   - D2 lists 9 ids and the user said 8 regions plus a baseline. Fix: say "8 regions + baseline".

10. **NIT, §5, §13 and the round-1 doc.** The Comma licence and SLR83 speaker-ID rule are marked "(§13)" or "(see §13)", but §13 is the build order.
    - Fix: change the references to "§5/S9" or add a §14 "Open items".

## B. Signatures that cannot work as written

11. **BLOCKER, §3 `select_stage(clips_csv, stage, out_csv, config)`.** `smoke` is defined as "the first ssbe read clip of pilot.csv", but the function does not receive pilot.csv.
    - Fix: smoke is computed from the same internal pilot selection, with no file dependency.
    - Wording: "smoke = first row (sorted by clip_id) of the pilot selection with region=ssbe and task=read. `select_stage` recomputes pilot internally."

12. **SHOULD, §3 `HttpError`.** Only attribute annotations are given, yet the fake raises `HttpError(429, retry_after=1)`.
    - Fix: `class HttpError(TranscribeError): def __init__(self, status:int, body:str="", retry_after:float|None=None)`.
    - Rename `TimeoutError_` to `ReadTimeout` (not a shadow of the builtin).
    - Mapping: `requests.ReadTimeout` → `ReadTimeout`; `requests.ConnectTimeout` and `ConnectionError` → `ConnectError`.

13. **BLOCKER, §6 Ledger and Retries.** Timeout handling is wrong and expensive.
    - Booking every timeout is conservative, but `requests.ConnectTimeout` is a subclass of both `ConnectionError` and `Timeout`.
    - A connect timeout means the request was never sent, so it must not be booked.
    - A read timeout retried 4 times books 4× the credits for one clip. That is about 23% of the free quota on the 40 s clip alone.
    - Fix: "Only `ReadTimeout` is booked (outcome `timeout`). `ConnectError` is retried and not booked. `ReadTimeout` is not retried (clip → `failed`, exit 4); a rerun is the user's choice."
    - Also drop `TimeoutError_` from the retry list in §6 Retries.

14. **SHOULD, §6 Ledger and §3 `Ledger`.** `reserve()`, `book()` and `release()` are separate calls, and "book() and release()" can interleave across threads.
    - A concurrent `remaining()` can then double-count or under-count.
    - Fix: one method, `settle(reservation:int, booking: Booking|None) -> None`, which updates spent and in-flight under one `threading.Lock`.
    - Document: "single-process only; no file lock".
    - Retries re-reserve per attempt, so state that a reservation is made per HTTP attempt.

15. **SHOULD, §3 `ledger` and the config.** The ledger is an estimate of credits, but the account may already have used credits this month.
    - Fix: add `credits_already_used: int = 0` to study.toml and `StudyConfig`. `spent()` = booked + that offset.
    - Say in §9: "reconcile `ukstt ledger show` against the ElevenLabs dashboard before S8".

16. **SHOULD, §3 FakeTranscriber vs. §3 `write_test_wav`.** Fake references are keyed by audio sha256 but failures are keyed by file stem.
    - Dummy clips with identical bytes (same seed) would collapse to one reference and also hit the same cache entry.
    - Fix: `make_dummy_data` must derive the noise seed from `clip_id` (`seed = int(sha256(clip_id)[:8], 16)`).
    - `from_clips(clips_csv, references_root, fake_toml)`: `reference_path` is repo-root-relative, so `references_root` is redundant. Fix signature: `from_clips(clips_csv: Path, fake_toml: Path, repo_root: Path = Path("."))`.
    - Keying failures by stem is fine because the stem equals the clip_id. Say so.
    - Add: "`FakeTranscriber` ignores `params` except `tag_audio_events`".

17. **SHOULD, §6 FakeTranscriber `malformed`/`empty` and §3 `Transcriber`.** The fake returns `{"oops":1}` and "the runner turns it into `MalformedResponse` via validation", while the real class raises it inside `transcribe`.
    - Fix: put `validate_response(raw: Mapping) -> None` in `base.py` (raise `MalformedResponse` if there is no `text` key or `text` is not a str). The runner calls it for both backends.
    - The real class raises only for a non-JSON body.
    - The fake `empty` response then passes validation; it is a legitimate empty hypothesis scored as `D=N`.

18. **SHOULD, §6 Retries.** `wait_exponential_jitter` plus "honour Retry-After, use the larger" needs a custom `wait` callable, and tenacity is a dependency just for 4 attempts.
    - Fix, simplest: cut tenacity.
    - Wording: "`call_with_retry(fn, max_retries, sleep)`: loop; delay = `max(retry_after or 0, min(30, 2*2**k) + random.Random(seed).uniform(0, 1))`".
    - That is about 15 lines, and the injectable `sleep` falls out for free.

19. **SHOULD, §6 and §3 cache.** Params in `study.toml` are native types (bool) but are sent as `"true"`/`"false"`.
    - Fix: `cache_key` takes the on-the-wire string-ified dict (`{k: str(v).lower() if bool else str(v)}`). Add one `wire_params(params)` helper used by both the cache key and the POST.
    - `--refresh` "for variance repeats" with a constant seed in the key gives the same output, so it is not a variance check.
    - Fix: say "`--refresh` re-sends the same request; for a different draw, change `seed` in `[params]`".

20. **NIT, §6 resume.** A clip served from the cache is "done if its raw file exists".
    - Fix: "On a cache hit, write `runs/<id>/raw/<clip_id>.json` from the cache response and then log `cached`."

21. **NIT, §6 exit codes.** `skipped_budget` mid-run has no exit code. Fix: "any `skipped_budget` → exit 3 (after finishing the other clips)".

## C. Normalisation ordering bugs (§7)

22. **BLOCKER, §7 rules 6/8.** `'cause → because` can never fire.
    - Rule 6 keeps only apostrophes between two letters, so the leading apostrophe in `'cause` is stripped first and the token becomes `cause`.
    - Fix: add to rule 1, after the quote normalisation, a regex `(?<![\w])'cause\b` → ` because `. Remove `'cause` from equivalences.csv.
    - Also normalise `‘’ʼ′` and the backtick to `'` in rule 1.
    - Leading and trailing apostrophes (quote marks, `dogs'`) are dropped. State this in rule 6.

23. **BLOCKER, §7 rule 6.** "All other characters are removed" glues tokens.
    - Examples: `yes,no` → `yesno`, `7:30` → `seven:thirty` → `seventhirty`, `end.Start` → `endstart`.
    - Fix wording: "Replace every character that is not a letter, digit, whitespace or a between-letters apostrophe with a space."
    - Then `u.s.` → `u s` (accepted noise; document it).

24. **SHOULD, §12 test_normalise line 487.** The expected output contradicts the rules.
    - `It's £5, 1,000 and 3.5%` must keep `it's` (apostrophe between letters), but the test text writes `its`.
    - Fix: `["it's","five","pounds","one","thousand","and","three","point","five","per","cent"]`.
    - Make the thousands-comma regex `(?<=\d),(?=\d{3}(?!\d))` so that `5, 1,000` is handled correctly.

25. **SHOULD, §7 rule 4.** The number rules are under-specified in ways a coder will trip on.
    - Year pairs: what is `1905` ("nineteen oh five"), `1900` ("nineteen hundred"), `2010` ("twenty ten")?
    - Any count such as `1,500 people` is also read as a year.
    - Fix, cutting: delete the year-pair rule. State "integers 0–999,999,999 are read as cardinals (British 'and'). Years are not special-cased; spoken years in hypotheses are known noise reported through `n_digit_tokens_hyp`."
    - Keep the reference style guide's "no digits" rule, and keep Comma, which has no digits.
    - State the processing order: `£n` → `n%` → thousands commas → decimals → ordinals → integers.
    - Add: "Leading-zero strings (`007`, `0123`) and digit-letter mixes (`5pm`, `1990s`) are left untouched (then rule 6 keeps them as one token)."
    - Drop `£5.50` support. `£n.nn` falls into decimals and gives "five point five zero pounds".

26. **SHOULD, §7 `hyp` and `ref` digits and "and".** British "and" in `105` → "one hundred and five".
    - A speaker who says "one hundred five" or "a hundred" scores errors. That is inherent, so say so in one sentence.
    - Hyphen rule (5): `twenty-one` → `twenty one`, which matches `int_to_words(21)` = "twenty one" (no hyphen). State "int_to_words never emits hyphens".

27. **NIT, §7 rule 10.** `uh-huh` → rule 5 splits it into `uh huh`; `uh` is dropped but `huh` stays as a spurious insertion.
    - Fix: add `huh` to the fillers, or note it as known noise.
    - Order check: filler removal happens after the equivalences, which is fine. A reference that is only fillers gives `E_REF_EMPTY_AFTER_NORM`, which is correct.

28. **SHOULD, §7 and the config.** `spelling_us_uk.csv` is described only as "a closed list (color→colour, etc.)". The coder has no content.
    - Fix: either ship the starter list in the plan, or merge it into a single `config/normalise.csv` (`from,to,class` with class in `register|orthography|spelling|filler`; `to` is empty for fillers) and say "seed the spelling class from the words that appear in the passage and in Scribe's pilot output".
    - That collapses 3 resource files into 1: no fillers.txt, no spelling_us_uk.csv, and a simpler `load_normaliser_resources`.
    - Hypotheses are normalised with ref and hyp on the same lists, so there is no asymmetry.

29. **SHOULD, §7 `extract_hypothesis` and `hyp_source`.** The `words[]` path adds a code path, a column and tests for no benefit.
    - With `tag_audio_events=false`, `text` carries the same words, and rule 2 already strips bracketed spans.
    - Fix, cut: "Hypothesis = `raw['text']`." Delete `hyp_source` and the `words`-based extraction and `test_extract` cases.
    - Keep `words[]` in the stored raw JSON.

## D. Scoring edge cases (§8)

30. **SHOULD, §8 alignment.** The backtrace must handle the boundaries explicitly, and the plan says "else insertion".
    - Fix wording: "If i==0 emit I; if j==0 emit D; otherwise apply priorities 1–4."
    - I hand-verified both tie-break tests (`a b` vs `b a` → S=2, and `a b c` vs `b c d` → D=1, I=1), and they come out as stated.

31. **SHOULD, §8 CER.** CER adds a character DP, a `char_dist` column, region-level CER aggregation (not defined), and tests. The user asked for WER.
    - Fix, defer: remove `char_distance`, `n_ref_chars`, `char_dist`, `cer` from the pilot.
    - If kept, define: "region cer = Σchar_dist / Σn_ref_chars over the same speakers as WER".

32. **NIT, §8 N=0 rows.** Empty ref plus non-empty hyp is excluded silently as `ref_empty` while the manifest already refuses such refs.
    - Fix: "scoring raises `ValueError` if n_ref==0 for an own clip. Only status `ref_empty` is possible, and only for hand-made input." Or drop the status.
    - "WER never clipped" is fine, and the `hello` vs `hello there you` test gives 2.0, which is correct.

## E. Stats spec (§10)

33. **BLOCKER, §10 n=2 per region.** The bootstrap CI for n_speakers = 2 is not an interval estimate.
    - It spans [min, max] of the two speakers, with probability 1/2 mass at each end.
    - The plan only returns NA for n<2, so every pilot row reports a misleading CI.
    - Fix: `MIN_SPEAKERS_CI = 5`. `bootstrap_ci` returns `None` below that, with the CSV cells empty and `low_n=true`.
    - Then the pilot reports only pooled WER, counts and S/D/I rates. That is honest.
    - State "95% CI" explicitly (it is never stated), and `alpha=0.05` as a constant.
    - The indices `reps[250]` and `reps[9749]` are right for B=10000 and give 250 values below and 250 above.
    - The test "assert via a spy list" is not implementable as written. Fix: build a controlled `reps` with a helper `percentile_interval(sorted_reps)` and assert `(reps[250], reps[9749])`.

34. **BLOCKER (over-engineering plus contradiction), §10 permutation, Holm, difference CI.** These are built even though P3 says the full study is "not built or run in v1".
    - With 2 vs 2 speakers the minimum p is 0.333, so no p-value can be useful.
    - Fix, defer: pilot `pairwise_vs_baseline.csv` = `source,task,region,n_spk_region,n_spk_base,wer_region,wer_base,diff,low_n`. No p, no CIs.
    - This deletes `permutation_test`, `holm`, `bootstrap_diff_ci`, and the exact/Monte Carlo threshold. About 100 lines and 8 tests are gone.
    - If the user wants them kept, apply items 35–37.

35. **SHOULD (if kept), Holm.** The family size is fixed at m=8, but the families are per (source=own, task), and regions with NA p-values (n<2) must drop out.
    - Fix: "m = number of non-NA p-values in the family; Holm is not applied to `task=all`."
    - The Holm test values check out ([0.03, 0.06, 0.06]).

36. **SHOULD (if kept), permutation test.** The unit is the speaker (ok), but the statistic is the pooled ratio, with a 50,000 threshold.
    - 10 vs 10 gives 184,756 combinations, so it is always Monte Carlo at full scale.
    - Write that into the test ("12 vs 12 → monte_carlo" is fine), and note that "n large" is not needed.
    - Seed Monte Carlo with `random.Random(f"{SEED}:{key}")`, the same as the bootstrap.

37. **NIT, §12 test_stats line 507.** "Bootstrap on a single value (degenerate) → CI lo=hi" collides with "n<2 → None".
    - Fix: "two speakers with identical rates → lo=hi", but this only applies if the CI threshold is lowered. With item 33 use five identical speakers.

38. **SHOULD, §10 "all" strata and §11 `region_summary.csv`.** The pooled "all" task row is secondary but unspecified in the families, in the n_ref weighting, and in the `region_scope`/`B`/`seed` columns.
    - Fix, cut: no `all` stratum. Drop the `B` and `seed` columns (put them in run_info.csv).
    - Drop `n_f,n_m,n_other` for the pilot (`speaker_scores.csv` already has gender and age).

## F. Unverified or inconsistent facts

39. **SHOULD, cost claim.** I found no "$1.65 for 7.5 h" in the plan or in any docs/*.md. The plan says only that 7.5 h = 450 min × 330 = 148,500 credits, which agrees with the arithmetic.
    - If the parent's cost figure comes from elsewhere, it is inconsistent: 330 credits/min is about 19,800 credits/h. $1.65 for 7.5 h is about $0.22/h, so it implies a price per credit that nobody has verified.
    - Fix: either delete any dollar figure from outputs, or add "Dollar cost: UNVERIFIED, not used in any decision. Credits are the only unit."

40. **SHOULD, §5 Comma licence.** The plan leaves it "unchecked" but the pilot depends on `references/read/comma_excerpt1.txt`, whose text is not in the plan. It is an internal report with no redistribution, so the licence does not block the pilot.
    - Fix: decide now. Wording: "Use Comma excerpt 1 (first sentences up to about 100 words). Internal use only; the text stays out of any published output. Rainbow Passage is the fallback only if the user objects."
    - Add the exact excerpt text, or a S0 task "write `references/read/comma_excerpt1.txt` and print it for the recorders". Recorders cannot read a passage that is not defined, so as it stands the pilot cannot start.

41. **SHOULD, §5 SLR83 speaker rule.** The `speaker_of` rule is explicitly unconfirmed. The plan knows this and has `slr83 inspect`.
    - If SLR83 is kept, add the failure behaviour to S9: "if the rule fails, abort `slr83 build` with exit 2; do not guess".
    - Selection rule fix: "Prefix of whole lines in line_id order; stop at the first prefix whose duration is in [18, 22]. If a line overshoots 22 s, skip to the next speaker. Sort speakers by `speaker_id` only (drop `-n_lines`)."

## G. Over-engineering: CUT or defer for 36 clips

42. **CUT SLR83 for the pilot (S9, `slr83.py`, `slr83 fetch/inspect/build`, the `spot` stage, `slr83_*` coarse regions, `region_scope`, `source`).**
    - Justification: 6 clips of one speaker each, no baseline group, no tests, read speech only, male-only.
    - It tells you nothing about regional claims and nothing the 36 own clips don't already validate about the pipeline.
    - It costs about 700 credits (7% of quota), a large download, a speaker-ID guess, a zip-fixture test suite, and 2 CSV columns that otherwise stay `own`/`fine`.
    - Do this unless the user explicitly wants SLR83. Move the section to an "Appendix: optional phase 2".

43. **CUT or defer:** `full` stage and the "refuses unless covered" logic, because the full study is "not built or run in v1".

44. **CUT:** `jiwer` cross-check and `responses`+socket-block conftest as separate pins.
    - Keep `responses`.
    - Keep jiwer only as an optional skipped test, or drop it. The hand-computed tests plus the property test are enough.

45. **CUT:** `run_manifest.json` fields `pins, git_commit, python_version, ledger_remaining_at_start` and `run_info.csv`.
    - Keep `run_id, backend, params, clips_file_sha256, created_utc`. The rest is not used by the resume check.

46. **SHOULD, DEFER:** `error_pairs.csv`'s `rank` column and the S/D/I rate columns.
    - Keep `error_pairs.csv`, because it is the useful diagnostic for accents, but drop `rank` (it is the row order).

47. **SHOULD, DEFER:** the `norm-frozen` git tag mechanic. The repo has no commits yet.
    - Fix: replace with "store a SHA256 of the normaliser resource files in `run_manifest.json`; abort resume if it changes".

48. **NIT, §6 FakeTranscriber.** `audio_event` generation, `words[]` with `spacing` items, and `transcription_id` are unused if item 29 is adopted.
    - Fix: the fake returns `{"language_code","language_probability","text","words":[...word-type only...]}`.

## H. Missing pieces a coder will trip on

49. **SHOULD.** Several CLI options named in tests or stages are not in §11.
    - `--out` for `make-dummy-data` is documented, but `--speakers-per-region` is called inconsistently in the e2e test ("10 speakers/region").
    - `ukstt ledger show` needs `--config`.
    - `transcribe` has no `--config config/study.toml` flag, though `load_config` takes a path.
    - `score` needs the `--out` default to be stated: `results/<run_id>`.
    - Fix: add a global `--config PATH` (default `config/study.toml`).
    - Add: "All paths are relative to the current directory; run from the repo root. Manifest paths are repo-root-relative."

50. **SHOULD.** The `make-dummy-data` output location is ambiguous. `--out dummy` creates `dummy/recordings`, `dummy/references`, and so on, but S3 then runs `build-manifest` with the default `recordings`/`references` flags.
    - Fix, S3 wording: "`build-manifest --recordings dummy/recordings --speakers dummy/recordings/speakers.csv --references dummy/references --out dummy/manifests/clips.csv ...`".
    - Same for S4 (`--clips dummy/manifests/pilot.csv`). The S4 text uses `manifests/pilot.csv`, which would not exist.
    - Dummy data must be gitignored (`dummy/`).

51. **SHOULD.** §12 acceptance checks that are not testable as stated.
    - "e2e: recovered region WERs within 0.03 of configured fake rates (pooled over a larger dummy set with 10 speakers/region)" needs a stated word count: with 10 speakers × 100 words, the sampling SD at p=0.12 is about 0.01, which is ok.
    - Fix wording: "dummy set: 10 speakers/region, 100-word read refs; tolerance 0.03".
    - S8 "ssbe read WER < 0.25 (soft)" and "hand-inspect 3 clips" are fine as manual checks, but label them `MANUAL`.
    - S6 "`git check-ignore .env.local`" is fine.
    - "`pytest -q` passes (collects 0 or placeholder tests)": pytest exits 5 on 0 tests. Fix: "add `tests/test_version.py`".

52. **SHOULD, build order.** `manifest.py` calls `normalise` (for `E_REF_EMPTY_AFTER_NORM` and `W_REF_DIGITS`), which is S1, so S3 is fine. But `aggregate.py` in S5 needs `stats.py` (S2), and S4's runner needs `Cache` plus the `Ledger=None` path.
    - Fix: state in S4 "`ledger=None` is legal for the fake backend only; the runner raises if backend is real and ledger is None".

53. **NIT, §6 `.env.local` lookup.** Real key lookup order is "env var, then `.env.local`". If python-dotenv stays, say `load_dotenv(".env.local", override=False)`.
    - Optionally cut python-dotenv with a 6-line parser. The plan forbids reading `.env`, so say `.env.local` only.

54. **NIT, §11 `ukstt --version`.** Fine as a no-subcommand flag. Add `ukstt` returns exit 2 with usage when no subcommand is given.

55. **NIT, §5 reference README.** "`[unclear]` and `[laughs]` are allowed and are stripped by rule 2". Stripping `[unclear]` hides a reference gap, so you can't see unclear spans in WER. Add: "Report `n_unclear` per clip in `utterance_scores.csv`", or ban the markers for the pilot (items are 20–40 s, so just re-record or re-transcribe).

## Top 10 fixes, ranked

1. **Item 1.** Fix the budget and gate numbers: pilot cap 20 min, `--max-audio-minutes 20`, ledger delta ≤ 6,966. Today the gate fails on any real data.
2. **Item 13.** Timeout booking: book only read timeouts and do not retry them. Connect timeouts are never booked.
3. **Item 33.** CI threshold `MIN_SPEAKERS_CI=5`. The n=2 bootstrap is meaningless.
4. **Item 34.** Defer permutation, Holm and difference CI to the full-study phase.
5. **Item 8.** Fix `ID_RE` so it actually forbids `__` and edge underscores.
6. **Item 11.** Fix the `select_stage` smoke computation (it has no pilot.csv input).
7. **Items 22 and 23.** Normalisation: handle `'cause` before stripping, and replace punctuation with a space instead of deleting it.
8. **Item 40.** Supply the passage text (`comma_excerpt1.txt`). Nobody can record the pilot without it.
9. **Item 42.** Cut SLR83 from the pilot. It removes 3 CLI commands, a module, a stage, a download, and 2 columns.
10. **Items 29, 31 and 28.** Simplify: hypothesis = `text` only, no CER, and one `normalise.csv` resource file.

Next in line after those: items 24 (test expectation), 25 (drop year pairs), 50 (dummy paths), 6/7 (`pyproject` and `.env.sample`), 14 (single `settle` method), 17 (response validation for both backends).

## Verdict

**Needs one more revision.** The structure, the pilot-first build order and the budget concept are sound. Items 1, 8, 13, 22/23, 33/34 and 40 would each cause a visible failure or wrong numbers on first contact with real data. The cuts in items 34 and 42 to 48 also shorten the plan by about a third.

Nothing was written or modified. I read only the plan and grep-matched the other docs, and did not open any `.env*` file. One local Python arithmetic check was the only command run.