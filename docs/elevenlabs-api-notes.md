# ElevenLabs STT API notes

Sources: https://elevenlabs.io/docs/capabilities/speech-to-text, /api-reference/speech-to-text/convert, /pricing, /pricing/api (retrieved 2026-11-02). How we call it is specified in [implementation-plan.md](implementation-plan.md) section 5, which wins on any conflict.

## Facts from the docs
- Models: Scribe v2 (batch), Scribe v2 Realtime, Scribe v2 Medical. This project uses **Scribe v2 batch**.
- Endpoint: `POST https://api.elevenlabs.io/v1/speech-to-text`, multipart form, header `xi-api-key`.
- Required: `model_id`, and exactly one of `file` or `source_url`.
- Params we use: `language_code`, `timestamps_granularity`, `tag_audio_events`, `no_verbatim` (scribe_v2 only), `diarize`, `seed`, `file_format`. See methodology.md for the values. `temperature` is left unset.
- Surcharged features we avoid: `keyterms` (+20%), `transcript_edit` (+30%), `detect_speaker_roles` (+10%).
- Limits: minimum 100 ms audio. Maximum file size is stated inconsistently (3 GB in the FAQ, 5 GB in the API reference), which is irrelevant for short clips.
- Output: word-level items typed `word`, `spacing` or `audio_event`, plus `language_code`, `language_probability` and `text`. We score `text` only and keep the whole response.
- Published accuracy claim: English is in the "Excellent (<=5% WER)" tier. No per-accent breakdown.
- `enable_logging=false` (zero retention) is enterprise only.
- `seed` gives best-effort determinism only.
- `no_verbatim`: `false` (default) keeps fillers, false starts and repetitions. `true` makes the model drop them. The docs do not define what counts as a filler, and no price difference was found.

## Free tier and credits
- Free plan: $0, 10,000 credits a month, Speech to Text listed as included, 8 concurrent STT requests, credits do not roll over. Scribe costs about 330 credits per audio minute, so about 30 minutes a month.
- Pay-as-you-go API price: $0.22 per hour of audio. **Unverified as a credit conversion, and not used in any decision.** Credits are the only unit in the plan.
- **Unverified:** whether a free key can call the STT API at all, whether billing rounds per request, and the free-plan terms for research use. The smoke test (S7) settles the first. Reconcile the ledger against the ElevenLabs dashboard before the real pilot.

## Key setup
1. Sign up at https://elevenlabs.io/app/sign-up.
2. Create a key at https://elevenlabs.io/app/api/api-keys. If you can, scope it to Speech to Text and give it a credit quota.
3. Put `ELEVENLABS_API_KEY=<key>` in `.env.local` (gitignored), or set it in the environment. The code reads the environment first, then `.env.local`, and never reads any other `.env*` file.
4. Never paste the key into chat, code or logs. The onboarding CLI (`npx @elevenlabs/cli onboard init`) already created `.env.local` and updated `.gitignore`.

## How we call it
- Plain `requests`, one POST per clip, timeouts 10 s connect and 120 s read. No retries inside the transcriber.
- Retries (up to 3, exponential backoff with jitter, honouring `Retry-After`) apply to 429, 5xx and connection errors only. Read timeouts, malformed responses and other 4xx are not retried. 401, 402 and 403 abort the run.
- Credit ledger: a clip is charged `ceil(seconds / 60 x 330 x 1.05)` credits (the 1.05 is a safety margin). It is booked once, only for a 200 response, a read timeout (the request was sent and may be billed) or a malformed 200. Connection errors, 429, 5xx and auth errors are never booked.
- Gate for real runs: `--backend elevenlabs` and `--max-audio-minutes N` must both be given, and the credits needed must fit in the ledger's remaining budget. Concurrency is capped at 8.
- Every response is cached by the hash of the audio plus the parameters, so a re-run costs nothing. `--refresh` re-sends the same request. To get a different draw, change `seed` in `config/study.toml`.
