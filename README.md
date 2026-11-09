# UK & Irish Regional Accent Accuracy: ElevenLabs Scribe STT

**Status:** Built and tested on the fake backend (steps S0–S6, 414 tests). Ran against the real API: a 1-clip smoke test, a 36-clip pilot, the main 840-clip evaluation (47 speakers, 85.6 minutes of audio; 82.4 minutes sent in that run, the other 36 reused from the pilot), a 34-clip Midlands top-up, and four demo runs (7 clips) of your own recordings.
**Created:** 2026-11-02

## Goal

Benchmark the transcription accuracy of one model, the ElevenLabs Speech-to-Text API (Scribe v2, batch), across six regional English accent groups of the UK and Ireland (the labels of an open dataset). The study measures how word error rate varies by group against a Southern English comparison group. Output is CSV tables plus a pandas/matplotlib notebook (graphs and audio players) for an internal report.

## Key terms

- **WER (Word Error Rate):** the standard accuracy measure for speech-to-text, `(S + D + I) / N`. S = substituted, D = deleted, I = inserted words; N = words in the reference transcript. Lower is better, 0% is perfect, and it can exceed 100% if there are many insertions.
- **STT (Speech-to-Text):** automatic transcription of audio into text.
- **Credits:** ElevenLabs' billing unit. The free tier gives 10,000 credits a month; measured cost on this account is about 61 credits per audio minute, so about 2.7 hours of Scribe audio.

## Scope

- **In:** Scribe v2 batch only. Six dialect labels from the dataset `ylacombe/english_dialects` (a Hugging Face copy of OpenSLR SLR83): Irish, Midlands, Northern, Scottish, Southern, Welsh. Southern is the comparison group (it is self-identified Southern English, not SSBE). Read speech. WER only.
- **Not covered, no source:** Scouse, Geordie, Lancashire, Yorkshire (any Yorkshire speakers are inside "Northern", not separable), Northern Ireland, SSBE, spontaneous speech.
- **Out:** other vendors, non-UK/Irish English, realtime/latency, diarization, language auto-detect, character error rate (CER), a written report. Graphs are in scope, as a notebook.

## The one plan

[docs/implementation-plan.md](docs/implementation-plan.md) is the single source of truth for everything a coder needs: decisions, repo layout, signatures, CSV schemas, normalisation rules, budget, tests and build order. The other docs give context and must not contradict it. If they do, the implementation plan wins and the other doc is a bug.

## Approach in one paragraph

Code is built and tested against a fake transcription backend (the default). The real API is gated behind an explicit flag and a `--max-audio-minutes` cap. There is no credit ledger and no response cache: a finished clip is simply not sent again when you resume a run. Four real runs have been made: `smoke-001` (1 clip), `pilot-001` (36 clips, 3.2 min), `large-001` (the main evaluation: 840 clips from the open dataset, 47 speakers, 85.6 min of audio, 10 to 11 speakers in four regions and 3 each in Irish and Midlands), and `midlands-extra-001` (a 34-clip top-up, scored separately and not merged into `large-001`). Results for each run are in `results/<run-id>/`, the saved run manifest and per-clip text in `runs/<run-id>/`, and the regional tables quoted below come from `results/large-001/`. Your own recordings are a separate optional `demo` set (`demo-001` to `demo-004`): they are transcribed so you can read and listen, but they are kept out of the regional statistics. Irish and Midlands have only 3 speakers each, so their figures are flagged `low_n` and get no confidence interval; the sample is still small enough that the study validates the pipeline and gives a first regional read more than it settles accent effects. A larger study (well beyond the free tier) needs a paid plan and your approval first.

## Results so far

Main run `large-001`: 840 read-speech clips, 47 speakers, 85.6 minutes of audio (82.4 minutes sent in the run; 36 clips reused from the pilot). WER against the Southern comparison group, from `results/large-001/region_summary.csv`:

Southern 2.73% (95% CI 2.03–3.55), Midlands 2.25% (3 speakers, `low_n`), Scottish 2.43% (1.39–3.70), Welsh 2.81% (2.04–3.53), Northern 3.44% (2.45–4.28), Irish 5.79% (3 speakers, `low_n`).

Only Irish sits clearly above Southern (+3.1 points), and that rests on 3 speakers. Northern is +0.7 points and its interval overlaps Southern's. Most remaining errors are US/UK spelling variants, proper nouns and one-word slips, not mishearing. The caveat stands: with 3 speakers in Irish and Midlands and 10 to 11 elsewhere, this is a first regional read, not a settled accent effect. There is no separate Yorkshire figure: the dataset has no Yorkshire label, so Yorkshire speakers sit inside "Northern". Your own recordings (`demo-001` to `demo-004`) are informal samples, not a measured set, and are excluded from these numbers.

## Quick start

`ukstt` is the command-line tool of this project. Run everything from the repo root.

### Set up

```
python3 -m venv .venv
source .venv/bin/activate                  # or prefix every command with .venv/bin/
pip install -e '.[dev,notebook]'           # installs the `ukstt` command; drop ",notebook" if you do not want the notebook libraries
```

### Run the tests (no network, no key needed)

```
pytest -q                                  # 414 tests, about 5 s
```

### Try it on made-up data (free: fake audio, fake transcriber)

```
ukstt make-dummy-data --out dummy
ukstt build-manifest --in dummy/manifests/clips_in.csv --out dummy/manifests/clips.csv --report dummy/manifests/validation_report.csv
ukstt select --clips dummy/manifests/clips.csv --stage pilot
ukstt transcribe --clips dummy/manifests/pilot.csv --run-id dummy-pilot-001      # fake backend is the default
ukstt score --run-id dummy-pilot-001 --clips dummy/manifests/pilot.csv
ukstt stats --run-id dummy-pilot-001
```

### Real evals (calls ElevenLabs and uses credits)

The API key goes in `.env.local` as `ELEVENLABS_API_KEY=...` (gitignored), or in the `ELEVENLABS_API_KEY` environment variable. Never paste it into chat or commit it. The audio is already in `data/audio/` (re-fetch with `python3 scripts/fetch_english_dialects_samples.py`).

Measured cost on this account: about 61 credits per audio minute. The 36-clip pilot (3.2 min) used about 200 credits, and the main 840-clip run used about 5,030 credits for the 82.4 minutes it sent.

```
ukstt build-manifest                       # validates manifests/clips_in.csv (70 clips); writes manifests/clips.csv
ukstt select --stage smoke
ukstt transcribe --backend elevenlabs --max-audio-minutes 0.5 --workers 1 --clips manifests/smoke.csv --run-id smoke-001
ukstt select --stage pilot
ukstt transcribe --backend elevenlabs --max-audio-minutes 4 --clips manifests/pilot.csv --run-id pilot-001
ukstt score --run-id pilot-001
ukstt stats --run-id pilot-001
```

Results are in `results/pilot-001/`. Running `transcribe` again with the same `--run-id` sends nothing (finished clips are skipped); add `--force` to send them all again. `--max-audio-minutes` is required for the real backend and is the only spend guard. Before sending, `transcribe` prints `to send: N clips, M.MM min (about C credits...)` for the clips that will actually be sent (resume-aware); the credit figure is still computed at 330 credits/min and is an over-estimate for this account (measured: about 61 credits/min), and nothing enforces it.

### The main run (`large-001`, 840 clips)

The full evaluation set is 840 clips from the open dataset. Its manifest is saved in `runs/large-001/clips.csv`, because the fetch manifests for the second expansion are no longer in `manifests/`. Select the pilot set without the default 10-minute cap:

```
ukstt select --clips runs/large-001/clips.csv --stage pilot --cap-minutes 120 --out manifests/pilot_840.csv
ukstt transcribe --backend elevenlabs --max-audio-minutes 90 --workers 4 --clips manifests/pilot_840.csv --run-id large-001
ukstt score --run-id large-001
ukstt stats --run-id large-001
```

That is 85.61 minutes of audio, 82.41 of it to send (about 5,030 credits) because `runs/large-001/raw/` already holds the 36 pilot results and a resumed run sends only the remaining 804 clips. If the quota runs out, the run stops with exit 5 and keeps what it has; run the same command again to continue.

### Larger runs (more speakers and clips)

Keep the 36-clip pilot manifest, fetch a different, larger set, and avoid sending the pilot clips again. `--list` first shows how many speakers each subset has (it scans once and caches `data/hf_speakers.json`; no audio). The output below is an example; read your own.

```
python3 scripts/fetch_english_dialects_samples.py --list --genders both
cp manifests/clips_in.csv manifests/clips_in_pilot36.csv               # backup of the old manifest
python3 scripts/fetch_english_dialects_samples.py --speakers 3 --clips-per-label 20 \
    --exclude-from manifests/clips_in.csv --out manifests/clips_in_large.csv
ukstt build-manifest --in manifests/clips_in.csv --in manifests/clips_in_large.csv
ukstt select --stage pilot --cap-minutes 20                            # the default cap is 10 minutes
ukstt transcribe --backend elevenlabs --max-audio-minutes 20 --clips manifests/pilot.csv --run-id large-001
ukstt score --run-id large-001 && ukstt stats --run-id large-001
```

`--speakers N` uses at most N speakers per label (those with the most rows); `--clips-per-label N` spreads N clips over them (a label that cannot reach N is reported on stderr and gets what exists); add `--genders both` for the female subsets too (irish has none), and keep `--clips` for a per-speaker count. Female speakers get an `f` in their id (`midlands_f3397`), so they never collide with male ones. The example run holds the 36 pilot clips plus about 120 new ones (about 12 to 15 min); a new run id sends all of them, so read the `to send:` line and the dashboard before spending, and lower `--clips-per-label` if needed. To run only the new clips, build with `--in manifests/clips_in_large.csv` alone.

### Look at the results (notebook)

```
jupyter lab                                # opens http://localhost:8888
```

Open `notebooks/results.ipynb`, set `RUN_ID` in its first cell (for example `"pilot-001"`) and choose Run, Run All Cells. On a remote machine use `jupyter lab --no-browser --ip=127.0.0.1 --port=8888` and forward the port with `ssh -N -L 8888:127.0.0.1:8888 USER@HOST`.

### Your own samples (optional demo set)

Put WAVs in `recordings/`, your transcripts in `references/`, list them in `manifests/demo_in.csv` (see docs/data-sources.md), then:

```
ukstt build-manifest
ukstt select --stage demo
ukstt transcribe --backend elevenlabs --max-audio-minutes 3 --clips manifests/demo.csv --run-id demo-001
ukstt score --run-id demo-001
```

The full command list is in docs/implementation-plan.md section 10.

## Docs

- [docs/implementation-plan.md](docs/implementation-plan.md): **source of truth** for the build
- [docs/plan.md](docs/plan.md): objectives, research questions, phases, budget summary
- [docs/methodology.md](docs/methodology.md): study design, normalisation, metrics, statistics, validity risks
- [docs/data-sources.md](docs/data-sources.md): where the audio comes from (open datasets under discussion; your own samples as a demo set)
- [docs/elevenlabs-api-notes.md](docs/elevenlabs-api-notes.md): API facts and how we call it
- [docs/open-questions.md](docs/open-questions.md): your decisions and what is still open
- [docs/review/](docs/review/): author/critic history (audit trail only, not authoritative)

## Licence

The code in this repository is MIT licensed, see [LICENSE](LICENSE). The pilot audio and transcripts come from `ylacombe/english_dialects` (OpenSLR SLR83), licensed CC BY-SA 4.0: if you redistribute that data or anything derived from it, you must give attribution and share alike. See [docs/data-sources.md](docs/data-sources.md) for details.
