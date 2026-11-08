# UK & Irish Regional Accent Accuracy: ElevenLabs Scribe STT

**Status:** Code built and tested on the fake backend (steps S0 to S6, 414 tests). Run against the real API with a working key in `.env.local` (steps S7 and S8): the 36-clip pilot, a 34-clip Midlands top-up (`midlands-extra-001`, 3 speakers total for that region), and one demo clip (`demo-001`).
**Created:** 2026-11-02

## Goal

Benchmark the transcription accuracy of one model, the ElevenLabs Speech-to-Text API (Scribe v2, batch), across six regional English accent groups of the UK and Ireland (the labels of an open dataset). The study measures how word error rate varies by group against a Southern English comparison group. Output is CSV tables plus a pandas/matplotlib notebook (graphs and audio players) for an internal report.

## Key terms

- **WER (Word Error Rate):** the standard accuracy measure for speech-to-text, `(S + D + I) / N`. S = substituted, D = deleted, I = inserted words; N = words in the reference transcript. Lower is better, 0% is perfect, and it can exceed 100% if there are many insertions.
- **STT (Speech-to-Text):** automatic transcription of audio into text.
- **Credits:** ElevenLabs' billing unit. The free tier gives 10,000 credits a month, about 30 minutes of Scribe audio.

## Scope

- **In:** Scribe v2 batch only. Six dialect labels from the dataset `ylacombe/english_dialects` (a Hugging Face copy of OpenSLR SLR83): Irish, Midlands, Northern, Scottish, Southern, Welsh. Southern is the comparison group (it is self-identified Southern English, not SSBE). Read speech. WER only.
- **Not covered, no source:** Scouse, Geordie, Lancashire, Yorkshire (any Yorkshire speakers are inside "Northern", not separable), Northern Ireland, SSBE, spontaneous speech.
- **Out:** other vendors, non-UK/Irish English, realtime/latency, diarization, language auto-detect, character error rate (CER), a written report. Graphs are in scope, as a notebook.

## The one plan

[docs/implementation-plan.md](docs/implementation-plan.md) is the single source of truth for everything a coder needs: decisions, repo layout, signatures, CSV schemas, normalisation rules, budget, tests and build order. The other docs give context and must not contradict it. If they do, the implementation plan wins and the other doc is a bug.

## Approach in one paragraph

Code is built and tested against a fake transcription backend (the default). The real API is gated behind an explicit flag and a `--max-audio-minutes` cap, because the free key allows only about 30 minutes of audio a month. There is no credit ledger and no response cache: a finished clip is simply not sent again when you resume a run. The first real run is a pilot of 36 clips (3.2 minutes, about 1,060 credits) from that dataset: 6 labels x 2 male speakers x 3 clips. The clips are already downloaded to `data/audio/`. Your own informal samples, if you supply any, are a separate optional `demo` set: they are transcribed so you can read and listen, but there is no standard text and no statistics. With about 2 speakers per region the pilot validates the pipeline only. It does not support conclusions about accents. A full study (about 10 speakers per region) needs a paid plan and your approval first.

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

### Real evals (calls ElevenLabs and uses credits: about 1,100 for the 36-clip pilot)

The API key goes in `.env.local` as `ELEVENLABS_API_KEY=...` (gitignored), or in the `ELEVENLABS_API_KEY` environment variable. Never paste it into chat or commit it. The 36 pilot clips are already in `data/audio/` (re-fetch with `python3 scripts/fetch_english_dialects_samples.py`).

```
ukstt build-manifest                       # validates the 36 clips; writes manifests/clips.csv
ukstt select --stage smoke
ukstt transcribe --backend elevenlabs --max-audio-minutes 0.5 --workers 1 --clips manifests/smoke.csv --run-id smoke-001
ukstt select --stage pilot
ukstt transcribe --backend elevenlabs --max-audio-minutes 4 --clips manifests/pilot.csv --run-id pilot-001
ukstt score --run-id pilot-001
ukstt stats --run-id pilot-001
```

Results are in `results/pilot-001/`. Running `transcribe` again with the same `--run-id` sends nothing (finished clips are skipped); add `--force` to send them all again. `--max-audio-minutes` is required for the real backend and is the only spend guard. Before sending, `transcribe` prints `to send: N clips, M.MM min (about C credits at 330 credits/min, unverified; check the dashboard)` for the clips that will actually be sent (resume-aware); the credit figure is an estimate and nothing enforces it.

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
