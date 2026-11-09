# Open questions

Decisions live in [implementation-plan.md](implementation-plan.md) section 1 (DECIDED / PROPOSED). That file wins over this one. Nothing below blocks building S0 to S8.

## Earlier answers, kept for the record
- Regions: originally SSBE baseline plus Scouse, Geordie, Welsh, Lancashire, Yorkshire, Scottish, Northern Ireland and Irish. Superseded: the chosen dataset has six coarse labels (Irish, Midlands, Northern, Scottish, Southern, Welsh) and you said that is fine. The baseline is self-identified Southern English, not SSBE (D1, "doesn't matter").
- Speech: read only in the pilot (the dataset has no spontaneous speech). No auto-detect. No ethics sign-off. Output: "just give me the data", plus a notebook for graphs.
- Free key: ElevenLabs Free plan, about 30 minutes of audio a month. `no_verbatim=false`, fillers removed by a fixed list on both sides (P5, P6).
- Pilot: 36 clips, 3.2 min, six labels x 2 male speakers x 3 clips (P1).

## Resolved with you (2026-11-03)
- Baseline wording "Southern English (self-identified)": yes.
- Demo samples: count unknown. You will write the transcripts yourself. Without a transcript a demo clip is transcribed and shown only.
- README "v1 (simple)" line: removed. `.gitignore` additions: ok.

## Open
- **API key: rejected.** The key is in `.env.local`, but `onboard check` reports that ElevenLabs rejects the key ending `ff19`. Create a new key and put it after `ELEVENLABS_API_KEY=` in `.env.local`. Whether a free key can call STT is a separate question, settled by the first real call (S7). The old `.env` copy is still on disk: delete it once the new key works.
- **Demo samples.** Put WAVs in `recordings/`, your transcripts in `references/`, and list them in `manifests/demo_in.csv` (see data-sources.md). With none, the demo step is skipped.
- **Register contractions (P10).** `gonna`, `wanna`, `gotta`, `kinda`, `sorta`, `cos` are mapped to long forms on both sides. Dialect words are never mapped. Tell me if you want this changed.
- **Full study** (about 10 speakers per region, about 7.5 h, about 27,500 credits at the measured 61 credits/min): needs a paid plan and your approval after the pilot (S9). Not part of this build. Irish and Midlands showed only about 3 speakers each, so they may never reach 5.
