# UK & Irish Regional Accent Accuracy: ElevenLabs Scribe STT

**Status:** Planning complete (round 3, consistency pass). Ready for a coder. No code yet.
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
Code is built and tested against a fake transcription backend (the default). The real API is gated behind an explicit flag, a minutes cap and a credit ledger, because the free key allows only about 30 minutes of audio a month. The first real run is a pilot of 36 clips (3.2 minutes, about 1,150 credits) from that dataset: 6 labels x 2 male speakers x 3 clips. The clips are already downloaded to `data/audio/`. Your own informal samples, if you supply any, are a separate optional `demo` set: they are transcribed so you can read and listen, but there is no standard text and no statistics. With about 2 speakers per region the pilot validates the pipeline only. It does not support conclusions about accents. A full study (about 10 speakers per region) needs a paid plan and your approval first.

## Quick start (once built; see build order S0 to S9)
`ukstt` is the command-line tool this project will build. `pip install -e .[dev]` installs the Python package `ukstt` and registers the `ukstt` command. It does not exist yet, so these commands will not work until step S0 to S5 are coded. The `dummy` commands use made-up audio and a fake transcriber, so they cost nothing.
```
pip install -e .[dev]
ukstt make-dummy-data --out dummy
ukstt build-manifest --in dummy/manifests/clips_in.csv --out dummy/manifests/clips.csv --report dummy/manifests/validation_report.csv
ukstt select --clips dummy/manifests/clips.csv --stage pilot
ukstt transcribe --clips dummy/manifests/pilot.csv --run-id dummy-pilot-001      # fake backend is the default
ukstt score --run-id dummy-pilot-001 --clips dummy/manifests/pilot.csv
ukstt stats --run-id dummy-pilot-001
```
For the real pilot (after S6), run `ukstt build-manifest` with no flags, then `ukstt select` for each stage. The full command list is in implementation-plan.md section 10.
The API key goes in `.env.local` as `ELEVENLABS_API_KEY=...` (gitignored) or the `ELEVENLABS_API_KEY` environment variable. Never paste it into chat or commit it.

## Docs
- [docs/implementation-plan.md](docs/implementation-plan.md): **source of truth** for the build
- [docs/plan.md](docs/plan.md): objectives, research questions, phases, budget summary
- [docs/methodology.md](docs/methodology.md): study design, normalisation, metrics, statistics, validity risks
- [docs/data-sources.md](docs/data-sources.md): where the audio comes from (open datasets under discussion; your own samples as a demo set)
- [docs/elevenlabs-api-notes.md](docs/elevenlabs-api-notes.md): API facts and how we call it
- [docs/open-questions.md](docs/open-questions.md): your decisions and what is still open
- [docs/review/](docs/review/): author/critic history (audit trail only, not authoritative)
