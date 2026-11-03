# Implementation plan: uk-accent-stt-eval

Status: round 2, ready for the coder. Tags: **DECIDED** = user decision, **VERIFIED** = checked fact, **PROPOSED** = plan author's choice, changeable. Package `ukstt`. `requires-python = ">=3.11"`. Developed on 3.14.9. Avoid 3.12+ syntax (no `type` statements, no PEP 695 generics).

**Conventions.** Run everything from the repo root. All paths are relative to the current directory. Manifest paths are repo-root-relative POSIX. Every subcommand accepts a global `--config PATH` (default `config/study.toml`). `ukstt` with no subcommand prints usage and exits 2.

## 1. Decisions

| # | Topic | Value | Tag |
|---|---|---|---|
| D1 | Baseline | Standard Southern British English, `ssbe` | DECIDED |
| D2 | Regions | 8 regions plus baseline: scouse, geordie, welsh, lancashire, yorkshire, scottish, ni, irish, plus ssbe. `ni` is the only abbreviation (display name "Northern Irish English"). `irish` = Republic of Ireland. | DECIDED |
| D3 | Speech type | Read and spontaneous, analysed as separate strata (`task`) | DECIDED |
| D4 | Ethics | No sign-off. Pseudonymous speaker IDs are kept anyway. | DECIDED |
| D5 | Language | `language_code=eng` fixed. No auto-detect. | DECIDED |
| D6 | Output | Internal, CSV tables only | DECIDED |
| D7 | Key | Free ElevenLabs key: 10,000 credits/month, about 330 credits per audio minute (pricing page), so about 30 min/month | DECIDED |
| D8 | Dev approach | Default backend is `fake`. The real API is gated. | DECIDED |
| P1 | Pilot | 3 regions (`ssbe`, `scottish`, `scouse`) x 2 speakers x (40 s read + 20 s spont) = 12 clips, 6.0 min nominal. The other 6 regions stay in `regions.csv` for the full study. Validates the pipeline only, not regional claims. | PROPOSED |
| P2 | Pilot cap | Pilot refused if total duration > 8.0 min (clip tolerance is +/-5 s, so this absorbs real recordings). | PROPOSED |
| P3 | Full study | About 10 speakers/region, about 7.5 h = 148,500 credits. Needs a paid plan and user approval. Not built or run. | PROPOSED |
| P4 | Who records | UNANSWERED. The drop-folder contract (§5) works for any recorder. | PROPOSED |
| P5 | Scribe params | `model_id=scribe_v2, language_code=eng, tag_audio_events=false, timestamps_granularity=word, diarize=false, no_verbatim=false, seed=20261102, file_format=other`. `temperature` unset, no keyterms or surcharged options. | PROPOSED |
| P6 | Fillers | Kept in the verbatim transcript, stripped from both sides by the `filler` rows in `config/normalise.csv` | PROPOSED |
| P7 | Audio | No resampling. Input must be PCM16 mono WAV >=16 kHz. | PROPOSED |
| P8 | Stats (pilot) | Pooled WER, per-region diff to baseline, speaker bootstrap 95% CI only when n_speakers >= 5. Permutation, Holm and difference CIs are deferred to the full study. | PROPOSED |
| P9 | Dependencies | Runtime: `requests` only. Stdlib for math, WAV, CSV. No numpy/scipy/tenacity/dotenv. | PROPOSED |
| P10 | Register contractions | `gonna wanna gotta kinda sorta cos 'cause` are mapped to long forms on both sides. Dialect words are never mapped. | PROPOSED |
| X1 | Dollar cost | Any dollar figure (e.g. the $0.22/h API pay-as-you-go price) is **UNVERIFIED** as a credit conversion and is used in no decision. Credits are the only unit. | NOTE |

## 2. Regions

`config/regions.csv`: `region_id,display_name,country,grew_up_area,is_baseline`

| region_id | display_name | country | grew_up_area (speaker eligibility) |
|---|---|---|---|
| ssbe | Standard Southern British | England | South-East England, self-described RP/SSBE (baseline) |
| scouse | Scouse | England | Liverpool/Merseyside |
| geordie | Geordie | England | Tyneside |
| welsh | Welsh English | Wales | Wales, English-first |
| lancashire | Lancashire | England | Lancashire (not Merseyside or Greater Manchester) |
| yorkshire | Yorkshire | England | Yorkshire |
| scottish | Scottish English | Scotland | Scotland; record the town |
| ni | Northern Irish English | Northern Ireland | the six counties |
| irish | Irish English | Ireland | Republic of Ireland |

Own data only in the pilot. Baseline = `ssbe`. SLR83 is out of the pilot (see the Appendix).

## 3. Repository layout

```
uk-accent-stt-eval/
  pyproject.toml     # name=ukstt; [project].dependencies=[requests==…]; [project.optional-dependencies].dev=[pytest==…, responses==…]
                     # [project.scripts] ukstt="ukstt.cli:main"; [tool.setuptools.packages.find] where=["src"]
  .env.sample        # ELEVENLABS_API_KEY=*** value)
  .gitignore         # .env* except .env.sample; cache/ runs/ ledger/ results/ dummy/ recordings/**/*.wav
  config/            # study.toml regions.csv normalise.csv fake.toml
  references/        # README.md  read/<passage_id>.txt  spont/<speaker_id>.txt
  recordings/        # speakers.csv  <speaker_id>/<clip_id>.wav
  manifests/         # clips.csv validation_report.csv pilot.csv smoke.csv
  cache/<backend>/<key[:2]>/<key>.json   ledger/ledger.csv   runs/<run_id>/…   results/<run_id>/…
  src/ukstt/
    __init__.py (__version__="0.1.0")  __main__.py (calls cli.main)  constants.py  config.py  csvio.py  audio.py
    manifest.py  dummy.py  numbers.py  normalise.py  score.py  stats.py  aggregate.py  cli.py
    transcribe/{__init__.py, base.py, fake.py, elevenlabs.py, cache.py, ledger.py, runner.py}
  tests/
```

Pins are placeholders until S0 verifies each with `pip index versions <pkg>`; bump any that do not exist. Suggested: `requests==2.34.2`, `pytest==9.2.0`, `responses==0.26.3`.

### Signatures (type-annotated)

```python
# constants.py
SEED = 20261102; B = 10_000; ALPHA = 0.05; MIN_SPEAKERS_CI = 5; BASELINE = "ssbe"
CREDITS_PER_MIN = 330; LEDGER_FACTOR_PCT = 105; MAX_WORKERS = 8; PILOT_CAP_MIN = 8.0; PILOT_REGIONS = ("ssbe", "scottish", "scouse")
ID_RE = r"^(?!.*__)[a-z0-9](?:[a-z0-9_]{0,46}[a-z0-9])?$"   # speaker_id and passage_id only, never clip_id

# config.py  (study.toml -> frozen dataclass)
@dataclass(frozen=True)
class StudyConfig:
    params: dict[str, object]            # native types; sent via wire_params()
    monthly_credit_cap: int              # 10000
    credits_already_used: int            # used this month outside this repo; default 0
    credits_per_min: int; ledger_factor_pct: int; ledger_period_start: str   # "2026-11-01"
    max_retries: int                     # 3
    connect_timeout_s: float; read_timeout_s: float   # 10, 120
    default_workers: int                 # 4
    runs_dir: Path; cache_dir: Path; ledger_path: Path; results_dir: Path
def load_config(path: Path = Path("config/study.toml")) -> StudyConfig: ...

# csvio.py (UTF-8, LF, newline='')
def read_csv(path) -> list[dict[str, str]]: ...
def write_csv(path, rows, fieldnames) -> None: ...      # atomic tmp + os.replace
def fmt_float(x: float | None) -> str: ...              # '' for None/NaN else f"{x:.6f}"

# audio.py
@dataclass(frozen=True)
class WavInfo: sample_rate_hz:int; channels:int; sampwidth_bytes:int; n_frames:int; duration_s:float
def probe_wav(path) -> WavInfo: ...        # wave.Error -> ValueError
def sha256_file(path) -> str: ...
def write_test_wav(path, seconds: float, sample_rate_hz: int = 16000, seed: int = 0) -> None: ...  # low-amplitude noise

# manifest.py
@dataclass(frozen=True)
class Issue: level: str; code: str; path: str; message: str      # level: error|warning
def parse_clip_id(s: str) -> tuple[str, str, str]: ...   # s.split("__"), exactly 3 parts, else ValueError
def build_manifest(recordings_dir, speakers_csv, references_dir, regions_csv, out_csv, report_csv, strict=False) -> list[Issue]: ...
def select_stage(clips_csv: Path, stage: str, out_csv: Path) -> list[dict[str, str]]: ...   # stage: smoke|pilot

# dummy.py
def make_dummy_data(out_dir: Path, speakers_per_region: int = 2, read_s: float = 40, spont_s: float = 20,
                    read_words: int = 100, seed: int = SEED) -> None: ...

# numbers.py
def int_to_words(n: int) -> str: ...       # British "and", never emits hyphens: 21 -> "twenty one", 105 -> "one hundred and five"
def expand_numbers(text: str) -> str: ...

# normalise.py
def load_normalise_csv(path: Path = Path("config/normalise.csv")) -> tuple[dict[str, str], frozenset[str]]: ...  # (token map, fillers)
def normalise(text: str, mapping: Mapping[str, str], fillers: frozenset[str]) -> list[str]: ...
def normalise_default(text: str) -> list[str]: ...   # loads config/normalise.csv once (lru_cache)

# score.py
@dataclass(frozen=True)
class Alignment:
    n_ref:int; n_hyp:int; hits:int; subs:int; dels:int; ins:int
    ops: tuple[tuple[str, str | None, str | None], ...]    # ('H'|'S'|'D'|'I', ref_word, hyp_word)
    errors: int (property); wer: float | None (property)    # None iff n_ref == 0
def align(ref: Sequence[str], hyp: Sequence[str]) -> Alignment: ...

# stats.py
@dataclass(frozen=True)
class SpeakerCounts: speaker_id: str; errors: int; n_ref: int
def pooled_wer(sp: Sequence[SpeakerCounts]) -> float: ...
def percentile_interval(sorted_reps: Sequence[float], alpha: float = ALPHA) -> tuple[float, float]: ...  # (reps[int(B*a/2)], reps[int(B*(1-a/2))-1])
def bootstrap_ci(sp, key: str, B: int = B, seed: int = SEED) -> tuple[float, float] | None: ...   # None if len(sp) < MIN_SPEAKERS_CI

# aggregate.py
def score_run(run_dir: Path, clips_csv: Path, out_dir: Path) -> None: ...   # utterance, speaker, error_pairs
def stats_run(out_dir: Path) -> None: ...                                   # region_summary, pairwise_vs_baseline

# transcribe/base.py
class TranscribeError(Exception): ...
class HttpError(TranscribeError):
    def __init__(self, status: int, body: str = "", retry_after: float | None = None): ...
class AuthOrQuotaError(HttpError): ...        # 401/402/403: abort whole run
class ReadTimeout(TranscribeError): ...       # request was sent; booked, NOT retried
class ConnectError(TranscribeError): ...      # never sent; retried, never booked
class MalformedResponse(TranscribeError): ...
class Transcriber(Protocol):
    name: str
    def transcribe(self, audio_path: Path, params: Mapping[str, object]) -> dict: ...
def validate_response(raw: Mapping) -> None: ...   # MalformedResponse unless raw["text"] is a str. Runner calls it for BOTH backends.
def wire_params(params: Mapping[str, object]) -> dict[str, str]: ...   # bool -> "true"/"false", else str(v). Used by POST and cache key.

# transcribe/fake.py
class FakeTranscriber:      # ignores params except tag_audio_events; all lookups keyed by audio file stem (== clip_id)
    name = "fake"
    def __init__(self, references: Mapping[str, str], region_of: Mapping[str, str], error_rates: Mapping[str, float],
                 failures: Mapping[str, Sequence[str]] | None = None, seed: int = SEED) -> None: ...
    def transcribe(self, audio_path, params) -> dict: ...
    @classmethod
    def from_clips(cls, clips_csv: Path, fake_toml: Path, repo_root: Path = Path(".")) -> "FakeTranscriber": ...

# transcribe/elevenlabs.py
class ElevenLabsTranscriber:
    name = "elevenlabs"; URL = "https://api.elevenlabs.io/v1/speech-to-text"
    def __init__(self, api_key: str, connect_timeout_s=10, read_timeout_s=120, session=None) -> None: ...
    def transcribe(self, audio_path, params) -> dict: ...   # ONE POST, no retry, no booking

# transcribe/cache.py
def cache_key(audio_sha256: str, wire: Mapping[str, str]) -> str: ...  # sha256(audio_sha256 + "\n" + json.dumps(wire, sort_keys=True, separators=(",", ":")))
class Cache:
    def __init__(self, root: Path, backend: str) -> None: ...
    def get(self, key: str) -> dict | None: ...
    def put(self, key: str, audio_sha256: str, wire: Mapping[str, str], response: Mapping) -> None: ...

# transcribe/ledger.py   (single process only; no file lock)
def charge_credits(audio_seconds: float, cfg: StudyConfig) -> int:
    # integer math: ms = round(audio_seconds*1000); -(-ms * cfg.credits_per_min * cfg.ledger_factor_pct // 6_000_000)
@dataclass(frozen=True)
class Booking: run_id: str; clip_id: str; cache_key: str; attempt: int; audio_seconds: float; credits: int; outcome: str  # ok|timeout|malformed
class Ledger:
    def __init__(self, path: Path, cfg: StudyConfig) -> None: ...
    def spent(self) -> int: ...          # cfg.credits_already_used + booked rows with ts_utc >= ledger_period_start
    def remaining(self) -> int: ...      # cap - spent - in-flight reservations
    def reserve(self, credits: int) -> bool: ...                       # False if insufficient
    def settle(self, reservation: int, booking: Booking | None) -> None:  # ONE lock: release reservation, append+fsync booking if any

# transcribe/runner.py
def call_with_retry(fn: Callable[[], T], *, max_retries: int, sleep: Callable[[float], None] = time.sleep) -> T: ...
@dataclass(frozen=True)
class RunOptions: run_id: str; backend: str; max_audio_minutes: float | None; workers: int; refresh: bool
def run_transcription(clips, opts, cfg, transcriber, ledger: Ledger | None, cache: Cache,
                      sleep=time.sleep) -> int: ...   # exit code. ledger=None legal for fake only; real + None raises.
```

## 4. Data contract (works for any recorder)

```
recordings/speakers.csv
recordings/<speaker_id>/<speaker_id>__read__<passage_id>.wav
recordings/<speaker_id>/<speaker_id>__spont__spont.wav        # passage_id for spont is the literal "spont"
references/read/<passage_id>.txt       # shared by all speakers
references/spont/<speaker_id>.txt      # human transcript of that speaker's spontaneous clip
```

- Audio: PCM16 WAV, mono, >=16 kHz. Anything else is a validation error, and the message includes `ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav`.
- `speaker_id` and `passage_id` match `ID_RE`. Own speaker convention `<region_id>_<nn>` (e.g. `scouse_01`). `clip_id = <speaker_id>__<task>__<passage_id>`. Split it only with `parse_clip_id`.
- Pilot durations: read 40 s +/-5, spont 20 s +/-5. Out of range is a warning. `select pilot` errors if total > 8.0 min.
- Pilot read passage: `comma_excerpt1` (see S0). Spontaneous prompt: "describe your journey to work/school this morning".
- Reference style guide (`references/README.md`): write what was said, in words. No digits. Standard spelling where a dictionary word exists, else the conventional dialect spelling (`wee nowt aye cannae`). No bracket markers of any kind (`[unclear]` hides errors; re-transcribe or re-record instead). Fillers optional.
- Spontaneous references are transcribed from scratch (`ref_method=human_scratch`). If drafted from Scribe output (`human_corrected_from_scribe`), WER is biased low. That must be flagged in `speaker_scores.csv` via `ref_method`.

**`recordings/speakers.csv`**: `speaker_id,region,town,age_band,gender,self_described_accent,lived_in_region_to_age,device,environment,ref_method,notes`
- `region` must be in `regions.csv`. `gender` is `f|m|nb|na`. `age_band` is `18-29|30-44|45-59|60+`. `ref_method` (for the spont clip) is `human_scratch|human_corrected_from_scribe`. Read clips always get `scripted`.
- `lived_in_region_to_age` < 16 is a warning.

**`manifests/clips.csv`** (from `build-manifest`): `clip_id,speaker_id,region,task,passage_id,audio_path,audio_sha256,duration_s,sample_rate_hz,channels,reference_path,ref_method,gender,age_band`. `task` is `read|spont`. Stage files (`pilot.csv`, `smoke.csv`) have the same columns.

**`manifests/validation_report.csv`**: `level,code,path,message`.
- Errors: `E_SPEAKER_UNKNOWN`, `E_SPEAKER_NOAUDIO`, `E_REGION_UNKNOWN`, `E_AUDIO_FORMAT`, `E_AUDIO_TOO_SHORT` (<0.1 s), `E_REF_MISSING`, `E_REF_EMPTY_AFTER_NORM`, `E_ID_BAD`, `E_DUP_CLIP`, `E_FILENAME_MISMATCH`.
- Warnings: `W_DURATION`, `W_LIVED_TO_AGE`, `W_REF_DIGITS`, `W_REF_BRACKET`, `W_ONE_TASK_ONLY`.
- `build-manifest` exits 2 if there is any error (or any warning with `--strict`). It writes `clips.csv` only when there are no errors.

**Stage selection** (`select_stage`, deterministic, sorted by `speaker_id`; it has no input except `clips.csv`):
- `pilot`: per region in `PILOT_REGIONS`, the first 2 speakers that have both a read and a spont clip, so 12 clips. Regions outside `PILOT_REGIONS` are ignored. Error if a pilot region has fewer than 2 such speakers. Error if total duration > `PILOT_CAP_MIN` (8.0 min).
- `smoke`: recompute the pilot selection internally and take its first row (sorted by `clip_id`) with `region=ssbe` and `task=read`. It is a pilot subset, so the cache is reused by the pilot.
- Default `--out` is `<dir of clips.csv>/<stage>.csv`.

## 5. Transcription behaviour

**Params** come from `config/study.toml [params]` (native types). `wire_params()` turns them into strings (`"true"`/`"false"`). The same dict is used for the multipart POST and the cache key. `temperature` is absent.

**Real call.** One `requests.post(URL, headers={"xi-api-key": key}, data=wire, files={"file": (name, fh, "audio/wav")}, timeout=(10, 120))`.
- The key is read from env `ELEVENLABS_API_KEY`, else from `.env.local` via a 6-line `KEY=value` parser. Never read `.env` or other `.env*` files. This happens only for the real backend. A missing key exits 2. Never log the key.
- Exceptions: `requests.ReadTimeout` → `ReadTimeout`. `requests.ConnectTimeout` and `ConnectionError` → `ConnectError`. Check ConnectTimeout first, because it also subclasses `Timeout`.
- Status: 200 ok. 401/402/403 → `AuthOrQuotaError`. 429 and 5xx → `HttpError`. Other 4xx → `HttpError`. A non-JSON body → `MalformedResponse`.
- The runner then calls `validate_response` (needs `text` as str) for both backends.

**Retries** (`call_with_retry`, about 15 lines, no tenacity):
```
for k in range(max_retries + 1):
    try: return fn()
    except (HttpError with status 429 or >=500, ConnectError) as e:
        if k == max_retries: raise
        sleep(max(getattr(e, "retry_after", None) or 0, min(30, 2 * 2**k) + random.Random(k).uniform(0, 1)))
```
- `max_retries=3`, so 4 attempts. The fake backend uses the same wrapper. Tests pass `sleep=lambda s: None`.
- NOT retried: `ReadTimeout`, `MalformedResponse`, `AuthOrQuotaError`, other 4xx. They fail the clip immediately (`AuthOrQuotaError` aborts the run).

**Ledger** (real backend only; the fake never touches it):
- Charge per clip = `charge_credits(duration_s)` = `ceil(sec/60 x 330 x 1.05)` in integer math. A reservation of that size is made **per HTTP attempt**. If `reserve()` is False the clip becomes `skipped_budget` and is not sent.
- After the attempt: `settle(reservation, booking_or_None)`.
- Booked: 200 → `ok`; `ReadTimeout` → `timeout` (the request was sent and may be billed); `MalformedResponse` → `malformed`. Not booked: `ConnectError`, 429/5xx, other 4xx, 401/402/403. So a clip is booked at most once.
- `ledger/ledger.csv`: `ts_utc,run_id,clip_id,cache_key,attempt,audio_seconds,credits,outcome`.
- Before S8, reconcile `ukstt ledger show` against the ElevenLabs dashboard and set `credits_already_used`.

**Real gate** (checked before any network I/O; exit 2 or 3):
1. `--backend elevenlabs` given explicitly (default is fake).
2. `--max-audio-minutes N` given.
3. Pre-flight over the clips that are not cached and not done (`todo`): `sum(duration_s) <= N*60`.
4. Pre-flight: `sum(charge_credits(c.duration_s) for c in todo) <= ledger.remaining()`, else exit 3 with needed vs remaining.
5. API key present.
6. `--workers` is clamped to `min(workers, 8)`. The real default is 4.

**Run state and resume.**
- `runs/<run_id>/run_manifest.json`: `run_id, created_utc, backend, params (wire), clips_file_sha256, normalise_csv_sha256`.
- Re-running an existing `run_id` resumes. It exits 2 if `params` or `clips_file_sha256` differ. `score` exits 2 if `normalise_csv_sha256` differs from the current `config/normalise.csv`, unless `--accept-normalise-change` is given (which rewrites the hash).
- `transcribe_log.csv` is append-only: `ts_utc,clip_id,cache_key,backend,status,attempts,http_status,latency_s,audio_seconds,credits,error`. `status` is `ok|cached|failed|skipped_budget`. The last row per `clip_id` is the state. A clip is done if its raw file exists and its last status is `ok` or `cached`.
- `raw/<clip_id>.json` is the verbatim response (including `words[]`), written atomically. On a cache hit, write it from the cache response, then log `cached`.
- Cache entries: `{cache_key, backend, audio_sha256, params, created_utc, response}`. The cache is split by backend. Malformed responses are never cached.
- `--refresh` skips the cache read, re-sends the same request and overwrites the cache entry. For a different draw, change `seed` in `[params]`.
- `ThreadPoolExecutor`. The log and the ledger are lock-protected. Outputs are ordered by `clip_id`.
- Exit codes: 0 ok; 2 usage, gate or validation; 3 budget (pre-flight failure, or any `skipped_budget` after the other clips finish); 4 some clips failed (resume to retry); 5 `AuthOrQuotaError` (stop submitting, let in-flight clips finish). When several apply, return the highest.

**FakeTranscriber.**
- Returns `{"language_code":"eng","language_probability":1.0,"text":…,"words":[{"text","start","end","type":"word"}…]}`. Word-type items only.
- Hypothesis = the reference with a per-word draw at `error_rates[region]`. The draw is substitute, delete or insert (1/3 each), from `random.Random(f"{seed}:{clip_id}")`. Substituted and inserted words come from a fixed list of letters-only nonsense words, never equal to the original. The text is capitalised and ends with a full stop.
- `config/fake.toml [error_rates]`: ssbe 0.03, scouse 0.12, geordie 0.12, welsh 0.08, lancashire 0.08, yorkshire 0.08, scottish 0.14, ni 0.10, irish 0.07.
- `failures`: dict `clip_id -> list`, one entry consumed per attempt: `"429"` (HttpError(429, retry_after=1)), `"500"`, `"503"`, `"connect"` (ConnectError), `"timeout"` (ReadTimeout), `"empty"` (`{"text":"","words":[],…}`, valid, scored D=N), `"malformed"` (`{"oops":1}`, rejected by `validate_response`).

## 6. Normalisation

`normalise(text) -> list[str]`, applied identically to reference and hypothesis. **Hypothesis = `raw["text"]` only.** Fixed order:

1. NFKC. Map `’ ‘ ʼ ′` and the backtick to `'`; `“ ”` to `"`. Map en and em dashes, NBSP and zero-width characters to a space.
2. Lowercase.
3. Replace bracketed spans `\[[^\]]*\]`, `\([^)]*\)` and `<[^>]*>` with a space.
4. Replace `(?<!\w)'cause\b` with ` because `.
5. `expand_numbers`. Processing order: `£n` → `n pounds`; `n%` → `n per cent`; thousands commas (`(?<=\d),(?=\d{3}(?!\d))` removed); decimals (`3.5` → `three point five`, digit by digit after the point); ordinals `1st..31st` via a table; integers 0..999,999,999 as British cardinals with "and". **Years are not special-cased** (`1984` → `one thousand nine hundred and eighty four`). Leading-zero strings (`007`) and digit-letter mixes (`5pm`, `1990s`) are left untouched. `£5.50` becomes "five point five zero pounds" (known noise). Digit tokens in hypotheses are known noise, tracked by `n_digit_tokens_hyp`. A speaker saying "one hundred five" scores errors against "one hundred and five"; this is inherent.
6. Replace `-`, `_` and `/` with a space.
7. Replace every character that is not a letter, digit, whitespace or an apostrophe between two letters with a space. Leading and trailing apostrophes (quote marks, `dogs'`) are dropped. Known noise: `u.s.` → `u s`. `7:30` → `seven thirty` falls out of rule 5 followed by this rule.
8. Split on whitespace.
9. Map tokens through `config/normalise.csv` rows with class `register|orthography|spelling`; re-split the output.
10. Drop tokens that are `filler` rows.
11. Drop empty tokens and return the list.

**`config/normalise.csv`** (`from,to,class`; `to` is empty for fillers):
- `register`: `gonna→going to`, `wanna→want to`, `gotta→got to`, `kinda→kind of`, `sorta→sort of`, `cos→because`.
- `orthography`: `ok→okay`, `alright→all right`, `percent→per cent`.
- `spelling`: US→UK starter rows (`color→colour`, `favorite→favourite`, `center→centre`, `realize→realise`, `gray→grey`). The coder adds the US spellings that occur in the passage text and in the pilot Scribe output. The list is closed.
- `filler`: `um umm uh uhm er erm hm hmm mm mmm mhm huh`. `huh` is there so that `uh-huh` becomes empty. Never fillers: `ah` (Scots), `eh`, `aye`, `like`, `yeah`.
- Dialect words (`wee nowt aye ye youse cannae dinnae yous …`) are never added.
- The file's SHA256 is stored in `run_manifest.json` (see §5).

## 7. Scoring rules

- **Alignment.** Levenshtein DP with unit costs, reference tokens on the rows. Backtrace from `(n, m)`: if `i==0` emit I; if `j==0` emit D; otherwise take the first that applies: (1) match if `ref[i-1]==hyp[j-1]` and `d[i][j]==d[i-1][j-1]`; (2) substitution if `d[i][j]==d[i-1][j-1]+1`; (3) deletion if `d[i][j]==d[i-1][j]+1`; (4) insertion. Reverse the ops afterwards.
- `WER = (S+D+I)/N`, **never clipped**. An empty hypothesis with N>0 gives D=N, WER=1.0.
- **N=0.** `wer` is empty (NA). `build-manifest` already rejects own references with zero words (`E_REF_EMPTY_AFTER_NORM`). Scoring raises `ValueError` if `n_ref==0` for any clip, so there is no `ref_empty` status.
- **CER is not computed in the pilot.**
- **Failed, missing or skipped clips** get `status=failed|missing|skipped_budget` in `utterance_scores.csv`. They are excluded from WER and counted in `n_excluded`. They are never silently dropped.
- **Aggregation.** Micro average (sum of errors / sum of words), never the mean of per-clip WERs. The unit in all statistics is the speaker.
- **Error pairs.** From alignment ops: `sub` (ref→hyp), `del` (ref→empty), `ins` (empty→hyp). Sorted by `-count, ref_word, hyp_word` (row order is the rank).
- `n_digit_tokens_hyp` is counted on the raw hypothesis text before rule 5.

## 8. Statistics (pilot)

- **Strata:** `task` in {read, spont}. There is no pooled "all" stratum.
- **Speaker counts.** `SpeakerCounts(errors, n_ref)` is summed over the speaker's scored clips in the stratum. Region WER = Σerrors/Σn_ref over speakers.
- **95% bootstrap CI** (alpha = `ALPHA` = 0.05), only if n_speakers >= `MIN_SPEAKERS_CI` (5). Below that, `bootstrap_ci` returns `None` and the CSV cells are empty. Every pilot region therefore has `low_n=true` and no CI. A bootstrap over 2 speakers is not an interval estimate.
  - `rng = random.Random(f"{SEED}:{task}|{region}")`. Draw `B=10000` resamples of the speakers with replacement. Take the pooled WER of each, sort ascending, return `percentile_interval(reps)` = `(reps[250], reps[9749])`.
- **Pairwise vs baseline** (pilot): `diff = wer_region − wer_ssbe`. No p-values, no CIs. The permutation test, Holm correction and difference CI are deferred to the full study (they cannot be informative at 2 vs 2 speakers: the minimum possible p is 1/3).
- Gender and age are carried in `speaker_scores.csv` only. There is no adjustment.

## 9. Real-API budget (credits; `ceil(sec/60 x 330 x 1.05)` = 346.5 per minute, per clip with rounding up)

| Item | Audio | Credits |
|---|---|---|
| Free cap | 28.9 min on the ledger basis (30 min raw) | 10,000 |
| 40 s clip / 20 s clip | | 231 / 116 |
| Smoke (a pilot clip; cached for the pilot, 0 extra) | about 0.7 min | 231 |
| Pilot nominal (6 x 231 + 6 x 116) | 6.0 min | 2,082 |
| Pilot cap (`PILOT_CAP_MIN`) | 8.0 min | 2,772, plus up to 12 for per-clip rounding = **2,784** |
| Reserve after a pilot at the cap | about 20.8 min | about 7,216 |

- Smoke plus pilot together never exceed 2,784 credits of ledger delta.
- A booked read timeout on a 40 s clip costs 231 credits (2.3% of the cap) and is not retried.
- Dollar figures are UNVERIFIED (X1) and are not used.
- A full study (about 7.5 h) is 148,500 raw credits and cannot run on a free key.

## 10. CLI (`python -m ukstt …` is equivalent; global `--config`)

```
ukstt --version
ukstt make-dummy-data --out dummy [--speakers-per-region 2] [--read-s 40] [--spont-s 20] [--seed 20261102]
ukstt build-manifest [--recordings recordings] [--speakers <recordings>/speakers.csv] [--references references]
      [--regions config/regions.csv] [--out manifests/clips.csv] [--report manifests/validation_report.csv] [--strict]
ukstt select --clips manifests/clips.csv --stage {smoke|pilot} [--out <clips dir>/<stage>.csv]
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-fake-001 [--backend fake|elevenlabs]
      [--max-audio-minutes N] [--workers N] [--refresh] [--fake-config config/fake.toml]
ukstt score --run-id pilot-fake-001 --clips manifests/pilot.csv [--out results/<run_id>] [--accept-normalise-change]
ukstt stats --run-id pilot-fake-001 [--out results/<run_id>]
ukstt ledger show        # spent, remaining credits and minutes, last 10 bookings
```

Real runs, in order:
```
ukstt transcribe --clips manifests/smoke.csv --run-id smoke-real-001 --backend elevenlabs --max-audio-minutes 1
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-real-001 --backend elevenlabs --max-audio-minutes 8
```

`make-dummy-data --out dummy` writes `dummy/recordings/{speakers.csv,<speaker>/*.wav}` and `dummy/references/…` (passage id `dummy_passage`, about 100 words; spont refs about 50 words). Noise WAVs are seeded from `sha256(clip_id)[:8]`, so no two clips are byte-identical. Dummy runs use the same dirs as real ones, with ids prefixed `dummy-`.

Output CSVs in `results/<run_id>/` (floats via `fmt_float`, booleans `true/false`, NA = empty cell):
- `utterance_scores.csv`: `run_id,clip_id,speaker_id,region,task,status,n_ref,n_hyp,hits,subs,dels,ins,wer,n_digit_tokens_hyp,ref_method`
- `speaker_scores.csv`: `region,task,speaker_id,gender,age_band,ref_method,n_clips,n_ref,subs,dels,ins,errors,wer`
- `region_summary.csv`: `task,region,n_speakers,n_clips,n_excluded,n_ref,subs,dels,ins,wer,ci_lo,ci_hi,low_n`
- `pairwise_vs_baseline.csv`: `task,region,n_spk_region,n_spk_base,wer_region,wer_base,diff,low_n`
- `error_pairs.csv`: `task,region,type,ref_word,hyp_word,count`

## 11. Tests (pytest; no real network)

`tests/conftest.py`: an autouse fixture makes `socket.socket.connect` raise. `responses` mocks HTTP. Use `tmp_path` for all I/O. Build configs with `dataclasses.replace(cfg, runs_dir=…, cache_dir=…, ledger_path=…, results_dir=…)`.

- `test_version.py`: `ukstt.__version__ == "0.1.0"`.
- `test_normalise.py`: one case per rule, then the full pipeline.
  - `"Don’t—stop!"` → `["don't","stop"]`.
  - `"It's £5, 1,000 and 3.5%"` → `["it's","five","pounds","one","thousand","and","three","point","five","per","cent"]`.
  - `"Um, the colour (laughs) [unclear] well-known"` → `["the","colour","well","known"]`.
  - `"'cause"` → `["because"]`; `"yes,no"` → `["yes","no"]`; `"7:30"` → `["seven","thirty"]`; `"uh-huh"` → `[]`.
  - `"gonna"` → `["going","to"]`; `nowt`, `wee`, `aye`, `ah` unchanged. `"1984"` → cardinal words. `"007"` and `"5pm"` untouched.
  - Idempotence: `normalise(" ".join(normalise(x))) == normalise(x)`.
- `test_numbers.py`: 0, 13, 21 (`twenty one`), 100, 105, 1001, 999999, 1,000,000.
- `test_score.py`: hand cases.
  - identical → 0; `the cat sat` vs `the dog sat` → S=1, WER 1/3; `the cat sat on the mat` vs `the cat sat` → D=3, WER 0.5; `hello` vs `hello there you` → I=2, WER 2.0; `a b c` vs empty → D=3, WER 1.0.
  - N=0 raises `ValueError` at the scoring layer. `align([], …)` gives `wer is None`.
  - Tie-breaks: `a b` vs `b a` → S=2; `a b c` vs `b c d` → D=1, I=1.
  - Seeded random property: S+D+I = errors, H+S+D = N, H+S+I = n_hyp, and errors equal an independent plain-Python edit distance.
- `test_stats.py`:
  - n<5 → `None`. Five identical speakers → lo == hi.
  - Controlled `percentile_interval(list(range(10000)))` → `(250, 9749)`.
  - Determinism: the same key gives the same CI, a different key gives a different one.
  - Pooled WER of two speakers (1/10, 3/10) = 0.2.
- `test_manifest.py`:
  - `parse_clip_id` accepts a valid id and rejects 2 or 4 parts. `ID_RE` rejects `a__b`, `a_`, `_a`, and accepts `scouse_01`.
  - Dummy data → 0 errors; `select pilot` gives 12 rows and 6.0 min; smoke is an ssbe read clip.
  - Negative cases, one per error code: wrong sample rate, stereo, missing ref, unknown region, duplicate clip, empty-after-norm ref, bad filename. Pilot over 8.0 min → error.
- `test_cache.py`: key stable across dict order; changes with params or audio; fake and elevenlabs dirs are separate; `wire_params` turns bools into lowercase strings.
- `test_fake.py`: determinism; each failure token behaves as listed; the error rate is recovered on a large sample.
- `test_runner.py` (fake backend, `sleep` stubbed):
  - 429, 429, ok → ok in 3 attempts.
  - 500 x4 → failed, exit 4.
  - Resume after a simulated crash redoes only the missing clip.
  - Cache hit → `cached`, no transcriber call, raw file written.
  - 8 workers equal 1 worker in output; `workers>8` is clamped.
  - Run-manifest mismatch → exit 2.
  - `AuthOrQuotaError` → exit 5, nothing further submitted.
  - A `malformed` response is rejected by `validate_response`; `empty` is scored D=N.
- `test_elevenlabs.py` (`responses`):
  - The multipart body carries every param (booleans lowercase), has the `xi-api-key` header, and has no `temperature`.
  - 200 books once. ReadTimeout books once and is not retried (clip failed, exit 4). ConnectTimeout is retried and never booked.
  - 429 then 200 books once.
  - 401 → exit 5, nothing booked.
  - Malformed 200 → booked, not cached, not retried.
  - Gates (zero HTTP calls in each): no `--max-audio-minutes` → exit 2; missing key → exit 2; insufficient ledger → exit 3.
  - The key never appears in logs or the manifest.
- `test_ledger.py`: `charge_credits(40)==231`, `(20)==116`, `(60)==347`; `settle` concurrency stress with 10 threads (spent + remaining stays consistent); persistence on restart; the period-start filter; `credits_already_used` offset.
- `test_e2e_dummy.py`: dummy set of 10 speakers/region, 100-word read refs (clip seconds small). Run select → transcribe (fake) → score → stats. Assert that two runs give byte-identical CSVs, that each region's read WER is within 0.03 of its configured fake rate, and that CIs are present (n≥5).

## 12. Build order with acceptance checks (AUTO = scripted, MANUAL = human)

- **S0 Scaffold and passage.**
  - Create pyproject, `.env.sample`, `.gitignore`, config skeletons, `__main__.py`, `tests/test_version.py`.
  - Verify every pin with `pip index versions`.
  - **Passage task:** write `references/read/comma_excerpt1.txt` = the first ~100 words of "Comma Gets a Cure", copied from the source by the recorders' coordinator (the plan does not reproduce the text). Internal use only; keep it out of any published output. Fallback if the user objects: `references/read/rainbow1.txt` (first paragraph of the Rainbow Passage, public domain), passage id `rainbow1`. Print the chosen file for the recorders.
  - AUTO: `pip install -e .[dev]` in a fresh venv; `pytest -q` passes; `ukstt --version` prints `0.1.0`; `python -m ukstt --version` works; `git check-ignore .env .env.local` succeeds and `.env.sample` is not ignored; the passage file has 90–110 words and no digits (`wc -w`, grep).
  - MANUAL: the passage file is the real excerpt (not invented).
- **S1 Normalise and score.** `numbers`, `normalise`, `score`, `normalise.csv`. AUTO: `test_normalise`, `test_numbers`, `test_score` pass.
- **S2 Stats.** AUTO: `test_stats` passes.
- **S3 Manifests, dummy data and select.** AUTO: `ukstt make-dummy-data --out dummy`; `ukstt build-manifest --recordings dummy/recordings --references dummy/references --out dummy/manifests/clips.csv --report dummy/manifests/validation_report.csv` exits 0; `ukstt select --clips dummy/manifests/clips.csv --stage pilot` gives 12 rows with 6.0 min; `test_manifest` passes.
- **S4 Fake, cache and runner** (`ledger=None` legal for fake only; real with None raises). AUTO: `test_cache`, `test_fake`, `test_runner` pass; `ukstt transcribe --clips dummy/manifests/pilot.csv --run-id dummy-pilot-001` gives 12 `ok` rows, and a second invocation makes 0 transcriber calls.
- **S5 End to end on dummy.** `aggregate.py`, CLI score and stats. AUTO: `test_e2e_dummy` passes; `results/dummy-pilot-001/` has all five CSVs; every pilot `low_n` is `true` and CIs are empty.
- **S6 Ledger, ElevenLabs and gate.** AUTO: `test_ledger` and `test_elevenlabs` pass; `ukstt transcribe --backend elevenlabs --clips dummy/manifests/smoke.csv --run-id x` with no `--max-audio-minutes` exits 2 with zero network calls; `ukstt ledger show` works on an empty ledger. MANUAL: reconcile `credits_already_used` with the ElevenLabs dashboard.
- **S7 Real smoke (attended; key in `.env.local`; needs real recordings).** MANUAL/AUTO: HTTP 200; `raw/*.json` has `text` and `words[]`; the ledger shows 231 credits for a 40 s clip; the log status is `ok`. If 401/402/403: stop and report that the free key cannot call STT. No retry loop.
- **S8 Real pilot (needs real recordings meeting §4).**
  - AUTO: 12/12 clips `ok` or `cached`; cumulative ledger delta since S7 (smoke + pilot) <= 2,784; `score` and `stats` write all five CSVs; every row has `low_n=true`.
  - MANUAL: ssbe read WER below 0.25 (soft; investigate if not); hand-inspect 3 clips' alignments.
- **S9 Approval gate for the full study.** No code. Give the user the pilot tables, the §9 numbers and a per-region speaker and minutes estimate. Proceed only on an explicit yes with a plan that has enough credits.

S1–S5 need no recordings. S7 and S8 are blocked until someone records.

## Appendix: optional phase 2 — SLR83 spot check (NOT in the pilot build order, CLI, stages or tests)

Do this only if the user asks. It tells you nothing about regional claims (no baseline group, one speaker per label, read speech only).
- **VERIFIED:** SLR83 is CC BY-SA 4.0, read speech only, with self-identified labels Irish, Midlands, Northern, Scottish, Southern, Welsh. It has no Scouse, Geordie, Lancashire, Yorkshire or NI labels. "Southern" is not SSBE. "Northern" is never pooled into fine regions. The Irish label is male only.
- **Sketch:** add `slr83.py` and `slr83 fetch|inspect|build`, a `spot` stage, `source` and `region_scope` columns, and `slr83_*` coarse region ids.
- **Speaker ID rule is UNCONFIRMED** (`'_'.join(file_id.split('_')[:2])`). `inspect` must confirm it. If it fails, `build` aborts with exit 2 and does not guess.
- **Selection:** sort speakers by `speaker_id`. Take whole lines in `line_id` order, joined with 0.3 s gaps. Stop at the first prefix with duration in [18, 22] s. If a line overshoots 22 s, go to the next speaker. WAV params must match across lines; there is no resampler.
- **Budget:** 6 clips of up to 22 s = about 696–800 credits; use `--max-audio-minutes 2.5`. Descriptive WER only, no baseline tests.
