# Data sources

The clip file format the code needs is in [implementation-plan.md](implementation-plan.md) section 4, which wins on any conflict. Verified dataset facts are in its appendix.

## Decided: pilot data
**`ylacombe/english_dialects`** on Hugging Face (https://huggingface.co/datasets/ylacombe/english_dialects), a copy of OpenSLR SLR83 (Google, "Crowdsourced high-quality UK and Ireland English Dialect speech data set"). Licence CC BY-SA 4.0 (verified from the dataset tags). Paper: Demirsahin et al., LREC 2020.

- **Labels:** Irish, Midlands, Northern, Scottish, Southern, Welsh. Speakers self-identified. These are the pilot's "regions".
- **Not in it:** Scouse, Geordie, Lancashire, Yorkshire, Northern Ireland, SSBE. There is **no Yorkshire label**: any Yorkshire speakers are inside "Northern" and cannot be separated (no town is given). "Southern" is self-identified Southern English, used as the comparison group instead of SSBE.
- **Content:** read sentences only, written to elicit accent differences (place names, airlines, personal names, plus sentences shared with other corpora). Transcripts are capitalised and unpunctuated; numbers are mostly spelled out (3 of the 36 fetched references contain digits, which the normaliser handles).
- **Size:** 17,877 clips, 8.98 GB. We never download it all. The fetch script pulls a few clips through the Hugging Face datasets-server API.
- **Speaker IDs** repeat across subsets (the same number appears under different dialects). They are almost certainly different people: the number is only unique within a subset. We key speakers as `<label>_<id>` so they never collide.

## Already fetched
`python3 scripts/fetch_english_dialects_samples.py` (needs no API key) wrote:
- `data/audio/*.wav`: 840 clips, 48 kHz mono 16-bit, 85.6 minutes in total (36 in the first pilot fetch, 204 in the first expansion, 600 in the second)
- `references/*.txt`: the dataset transcript for each clip
- `manifests/clips_in.csv`: the manifest the pipeline reads, `set=pilot`

Sample design: male subsets only (Irish exists only as male, so this holds gender constant). The pilot took 2 speakers per label x 3 clips; the study set takes up to 34 or 100 clips per label across up to 10 speakers, so four labels reach 10 to 11 speakers and Irish and Midlands stay at their 3. Clips are at most 60 s (the pilot fetch capped at 12 s). It is rate-limited by the server and retries on its own.

### Larger sets (R29)
`--list [--genders both]` prints, per subset, the rows, the number of speakers and the rows per speaker (it scans the whole subset in pages of 100 once and caches it in `data/hf_speakers.json`; delete the file to rescan; no audio is downloaded). Options: `--speakers N` (at most N speakers per label, those with the most rows, ties by id), `--clips-per-label N` (N clips per label spread round-robin over them; stderr warning if a label cannot reach N) or `--clips N` (per speaker, the old option), `--genders male|female|both` (default male), `--max-seconds`, `--out CSV` (default `manifests/clips_in.csv`; another name leaves the existing manifest alone) and `--exclude-from CSV` (repeatable; skips the clip_ids listed there, e.g. the 36 pilot clips). Female speakers are keyed `<label>_f<number>` (male ids are unchanged), because the same number occurs in male and female subsets. Verified speaker counts: irish_male 3 x 150 rows, midlands_male 3 x 150, midlands_female 2 (150 and 96), welsh_male 11 x 150. The 36 clips already fetched were chosen from 8 sampled windows; the new script takes clips in dataset order within each speaker, so a re-run picks partly different clips (the ids have the same form).

## Your own samples (`demo` set)
The few informal samples you already have go in `recordings/` as WAV (convert with `ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav`). They are listed in `manifests/demo_in.csv` (same columns as `clips_in.csv`) with `set=demo`, `region=unknown`, and `task=unknown` unless you know it. The fetch script never touches that file. This whole set is optional: with no `demo_in.csv` the demo step is skipped. They are transcribed so you can read and hear the result. They are not scored into the dialect numbers: no standard text, no verified accent label. A reference text is optional. With one, the clip gets its own WER in `utterance_scores.csv` and the notebook, but never enters the speaker or region tables.

## Rejected or not used
| Source | Why not |
|---|---|
| Mozilla Common Voice | Noisy self-reported accent labels, probably in the model's training data. Not checked in detail. |
| IViE, ABI-1 | Access and licence unverified. IViE would cover Leeds, Liverpool and Newcastle if it can be had. A candidate for a later round if you want Scouse, Geordie or Yorkshire. |

## Privacy and licence
Dataset audio is sent to ElevenLabs, whose logging defaults to on (zero retention is enterprise only), and is public data anyway. CC BY-SA requires attribution and share-alike if you redistribute clips or derived data. Your own samples: do not publish the raw audio.
