# Methodology

Exact rules, signatures and schemas are in [implementation-plan.md](implementation-plan.md), which wins on any conflict. This file explains the design.

## System under test
ElevenLabs `POST /v1/speech-to-text`, `model_id=scribe_v2`, one request per clip. Fixed for every run and recorded in the run manifest:

| Param | Value | Why |
|---|---|---|
| `language_code` | `eng` | Auto-detect is out of scope (your decision) |
| `tag_audio_events` | `false` | Keeps "(laughter)" tokens out of WER |
| `timestamps_granularity` | `word` | Word list is stored in the raw JSON |
| `diarize` | `false` | Extra cost, not relevant |
| `no_verbatim` | `false` | Keep fillers in the transcript, then strip a fixed list from both sides (see below) |
| `seed` | `20261102` | Best-effort determinism |
| `file_format` | `other` | Plain WAV upload |
| `temperature`, keyterms, `transcript_edit`, speaker roles | unset | Surcharged or bias-inducing |

The full raw JSON response is stored for every clip. The scored hypothesis is `raw["text"]` only.

## Data
See [data-sources.md](data-sources.md). The pilot uses 36 clips from `ylacombe/english_dialects` (OpenSLR SLR83 copy): 6 dialect labels x 2 male speakers x 3 clips, 3.2 minutes. Read speech only, so there is a single `read` stratum. Every pilot clip has a speaker ID, a label and a human reference transcript from the dataset. Your own informal samples are a separate `demo` set: transcribed and shown, never scored into regional numbers.

## Audio
No resampling in the package. Input must be PCM16 mono WAV at 16 kHz or higher, and the validator rejects anything else with an `ffmpeg` hint (dataset importers do the conversion). Minimum 100 ms (API limit). Silence is billed. Audio files are kept on disk so you can listen.

## Text normalisation (reference and hypothesis, same code)
Eleven ordered rules, in implementation-plan.md section 6. Summary:
- NFKC, lowercase, bracketed spans removed, `'cause` fixed before punctuation stripping.
- Numbers expanded to British words (with "and"). Years are not special-cased.
- Every character that is not a letter, digit, space or between-letters apostrophe becomes a space (so `7:30` and `yes,no` split correctly).
- One file, `config/normalise.csv`, holds the maps: register contractions (`gonna` to `going to`), orthography, US/UK spelling, and the filler list (`um uh er hmm huh ...`). `no_verbatim=false` plus this fixed list is deterministic, whereas `no_verbatim=true` would depend on the model's own idea of a filler.
- **Dialect words are never mapped** (`wee`, `nowt`, `aye`, `cannae` ...). A wrong transcription of them counts as an error, because that is part of what is measured.
- The file is frozen before real results are scored. Its SHA256 is stored in the run manifest, and scoring refuses to run if it changed.

## Metrics
- **WER** = (S + D + I) / N, never clipped (it can exceed 1.0). Computed as a micro-average (sum of errors over sum of reference words) per region and task, not as a mean of per-clip WERs.
- Alignment is Levenshtein with a fixed tie-break order, so results are deterministic.
- S/D/I counts per region, and the most frequent error word pairs per region (`error_pairs.csv`).
- A clip with an empty hypothesis scores D = N. A reference that normalises to zero words is rejected at manifest time.
- CER and language-ID mismatch are not computed.

## Statistics (pilot)
- The unit is the **speaker**, because clips from one speaker are not independent.
- Report n speakers and n words per region.
- Difference from baseline = WER(label) minus WER(southern). No p-values.
- 95% bootstrap CI (resampling speakers, fixed seed, 10,000 resamples, percentile method) only when a region has at least 5 speakers. At 2 speakers a bootstrap is not an interval estimate, so those cells are empty and the row has `low_n=true`.
- Permutation tests, Holm correction and difference CIs are deferred to a funded full study (about 10 speakers per region). At 2 vs 2 speakers the smallest possible p-value is 1/3, so they could not be informative.

## Validity risks
- Reference transcript errors or style differences inflate WER (a dataset's transcription conventions may differ from Scribe's). The shared normaliser absorbs punctuation, case, numbers and fillers but not every convention. A reference drafted from Scribe output biases WER low and is flagged in `notes`.
- Recording quality (mic, noise) correlated with region, which a crowdsourced dataset will not control. It is reported, not corrected.
- Few speakers per region: speaker effects dominate. The pilot cannot say anything about accents.
- Read and spontaneous speech differ in difficulty, hence separate strata.
- Region labels are self-identified and coarse ("Northern" is northern England in general; the dataset gives no town, so Yorkshire and the rest cannot be separated). Labels are never split or pooled. The comparison group is self-identified Southern English, not SSBE.
- Speaker IDs repeat across the dataset's subsets, so speakers are keyed `<label>_<id>`. Whether a repeated ID is the same person is unknown.
- The sentences were written to elicit accent differences (place names, airline and personal names), so they may be harder than ordinary speech.
- Normalisation choices (register contractions, filler list, number style) shape WER. They are fixed before scoring and documented, not tuned.
- Public datasets may overlap model training data (Common Voice especially), which would flatter WER. Another reason the pilot proves the pipeline, not the accents.
- API determinism is best-effort even with a seed. A repeat run with a changed `seed` (not `--refresh`, which re-sends the same request) measures variance, if budget allows.
