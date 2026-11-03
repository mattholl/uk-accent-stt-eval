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
- `data/audio/*.wav`: 36 clips, 48 kHz mono 16-bit, 3.2 minutes in total
- `references/*.txt`: the dataset transcript for each clip
- `manifests/clips_in.csv`: the manifest the pipeline reads, `set=pilot`

Sample design: male subsets only (Irish exists only as male, so this holds gender constant), 2 speakers per label, 3 clips each, at most 12 s per clip. Re-run it with `--speakers N --clips N` for more. It is rate-limited by the server and retries on its own.

## Your own samples (`demo` set)
The few informal samples you already have go in `recordings/` as WAV (convert with `ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav`). They are listed in `manifests/demo_in.csv` (same columns as `clips_in.csv`) with `set=demo`, `region=unknown`, and `task=unknown` unless you know it. The fetch script never touches that file. This whole set is optional: with no `demo_in.csv` the demo step is skipped. They are transcribed so you can read and hear the result. They are not scored into the dialect numbers: no standard text, no verified accent label. A reference text is optional. With one, the clip gets its own WER in `utterance_scores.csv` and the notebook, but never enters the speaker or region tables.

## Rejected or not used
| Source | Why not |
|---|---|
| Mozilla Common Voice | Noisy self-reported accent labels, probably in the model's training data. Not checked in detail. |
| IViE, ABI-1 | Access and licence unverified. IViE would cover Leeds, Liverpool and Newcastle if it can be had. A candidate for a later round if you want Scouse, Geordie or Yorkshire. |

## Privacy and licence
Dataset audio is sent to ElevenLabs, whose logging defaults to on (zero retention is enterprise only), and is public data anyway. CC BY-SA requires attribution and share-alike if you redistribute clips or derived data. Your own samples: do not publish the raw audio.
