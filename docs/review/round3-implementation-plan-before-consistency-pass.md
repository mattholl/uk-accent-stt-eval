# Implementation plan: uk-accent-stt-eval

Status: round 2, ready for the coder. Tags: **DECIDED** = user decision, **VERIFIED** = checked fact, **PROPOSED** = plan author's choice, changeable. Package `ukstt`. `requires-python = ">=3.11"`. Developed on 3.14.9. Avoid 3.12+ syntax (no `type` statements, no PEP 695 generics).

**Conventions.** Run everything from the repo root. All paths are relative to the current directory. Manifest paths are repo-root-relative POSIX. Every subcommand accepts a global `--config PATH` (default `config/study.toml`). `ukstt` with no subcommand prints usage and exits 2.

## 1. Decisions

| # | Topic | Value | Tag |
|---|---|---|---|
| D1 | Baseline | `southern` = self-identified **Southern English** from the dataset. It is NOT Standard Southern British (SSBE); the dataset has no SSBE label. | DECIDED (user: "doesn't matter") |
| D2 | Regions | The six dialect labels of the pilot dataset: `irish`, `midlands`, `northern`, `scottish`, `southern`, `welsh`. Yorkshire, Scouse, Geordie, Lancashire and Northern Ireland are NOT separate labels in this dataset (Yorkshire speakers, if any, are inside `northern`, and Northern Irish inside `irish` at best; the dataset gives no town, so this is unverified). | DECIDED |
| D3 | Speech type | `task` column = `read`, `spont` or `unknown`. Analysed as separate strata when a source provides it. No recording protocol, no standard text. | DECIDED |
| D4 | Ethics | No sign-off. Pseudonymous speaker IDs are kept anyway. | DECIDED |
| D5 | Language | `language_code=eng` fixed. No auto-detect. | DECIDED |
| D6 | Output | CSV tables plus a pandas/matplotlib notebook (`notebooks/results.ipynb`) with graphs and audio players | DECIDED |
| D7 | Key | Free ElevenLabs key: 10,000 credits/month, about 330 credits per audio minute (pricing page), so about 30 min/month | DECIDED |
| D8 | Dev approach | Default backend is `fake`. The real API is gated. | DECIDED |
| P1 | Pilot | Dataset `ylacombe/english_dialects` (Hugging Face copy of OpenSLR SLR83, CC BY-SA 4.0, read speech only). Male subsets only (Irish exists only as male), 2 speakers per label x 3 clips = **36 clips, 3.2 min, about 1,150 credits**. Already fetched by `scripts/fetch_english_dialects_samples.py`. Validates the pipeline only, not regional claims. | DECIDED |
| P2 | Pilot cap | Pilot refused if total duration > 10.0 min (allows a larger second fetch later). | PROPOSED |
| P3 | Full study | About 10 speakers/region, about 7.5 h = 148,500 credits. Needs a paid plan and user approval. Not built or run. | PROPOSED |
| P4 | Data | Two sets. `pilot`: the dataset clips above. `demo`: the few informal samples the user already has, for listening and general interest: no standard text, no statistics, reference optional. | PROPOSED |
| P5 | Scribe params | `model_id=scribe_v2, language_code=eng, tag_audio_events=false, timestamps_granularity=word, diarize=false, no_verbatim=false, seed=20261102, file_format=other`. `temperature` unset, no keyterms or surcharged options. | PROPOSED |
| P6 | Fillers | Kept in the verbatim transcript, stripped from both sides by the `filler` rows in `config/normalise.csv` | PROPOSED |
| P7 | Audio | No resampling. Input must be PCM16 mono WAV >=16 kHz. | PROPOSED |
| P8 | Stats (pilot) | Pooled WER, per-region diff to baseline, speaker bootstrap 95% CI only when n_speakers >= 5. Permutation, Holm and difference CIs are deferred to the full study. | PROPOSED |
| P9 | Dependencies | Runtime: `requests` only. Stdlib for math, WAV, CSV. No numpy/scipy/tenacity/dotenv. Optional extra `[notebook]`: pandas, matplotlib, jupyter, nbformat (pins verified in S0). | PROPOSED |
| P10 | Register contractions | `gonna wanna gotta kinda sorta cos 'cause` are mapped to long forms on both sides. Dialect words are never mapped. | PROPOSED |
| P11 | Audio on disk | Audio is never deleted or moved by the tool. `audio_path` in the manifest points at the local file (own samples under `recordings/`, dataset clips under `data/audio/`, both gitignored). The notebook plays clips with `IPython.display.Audio`. | PROPOSED |
| X1 | Dollar cost | Any dollar figure (e.g. the $0.22/h API pay-as-you-go price) is **UNVERIFIED** as a credit conversion and is used in no decision. Credits are the only unit. | NOTE |

## 2. Regions

`config/regions.csv`: `region_id,display_name,slr83_label,is_baseline`

| region_id | display_name | slr83_label | is_baseline |
|---|---|---|---|
| southern | Southern English (self-identified) | southern | true |
| midlands | Midlands English | midlands | false |
| northern | Northern English (coarse: northern England in general; Yorkshire, Lancashire, Geordie and Scouse speakers cannot be separated, and the dataset gives no town) | northern | false |
| scottish | Scottish English | scottish | false |
| welsh | Welsh English | welsh | false |
| irish | Irish English | irish | false |

Labels are self-identified by the speakers. "Northern" is never split into finer regions. The finer regions you asked for (Scouse, Geordie, Lancashire, Yorkshire, Northern Ireland, SSBE baseline) have no source yet and are not in `regions.csv`; adding one means adding a row and a data source.

## 3. Repository layout

```
uk-accent-stt-eval/
  pyproject.toml     # name=ukstt; [project].dependencies=[requests==…]; [project.optional-dependencies].dev=[pytest==…, responses==…]
                     # [project.optional-dependencies].notebook=[pandas==…, matplotlib==…, jupyter==…, nbformat==…]
                     # [project.scripts] ukstt="ukstt.cli:main"; [tool.setuptools.packages.find] where=["src"]
  .env.sample        # ELEVENLABS_API_KEY=*** value)
  .gitignore         # .env* except .env.sample; cache/ runs/ ledger/ results/ dummy/ recordings/**/*.wav
  config/            # study.toml regions.csv normalise.csv fake.toml
  references/        # <clip_id>.txt  human reference transcript, one per clip (optional for demo clips)
  recordings/        # own demo samples: <clip_id>.wav (gitignored)     data/audio/  dataset clips (gitignored)
  manifests/         # clips_in.csv (hand-written or importer output)  clips.csv validation_report.csv pilot.csv smoke.csv
  cache/<backend>/<key[:2]>/<key>.json   ledger/ledger.csv   runs/<run_id>/…   results/<run_id>/…
  src/ukstt/
    __init__.py (__version__="0.1.0")  __main__.py (calls cli.main)  constants.py  config.py  csvio.py  audio.py
    manifest.py  dummy.py  numbers.py  normalise.py  score.py  stats.py  aggregate.py  cli.py
    transcribe/{__init__.py, base.py, fake.py, elevenlabs.py, cache.py, ledger.py, runner.py}
  notebooks/results.ipynb   # pandas + matplotlib; reads results/<run_id>/*.csv, clips.csv, runs/<run_id>/raw/*.json
  tests/
```

Pins are placeholders until S0 verifies each with `pip index versions <pkg>`; bump any that do not exist. Suggested: `requests==2.34.2`, `pytest==9.2.0`, `responses==0.26.3`.

### Signatures (type-annotated)

```python
# constants.py
SEED = 20261102; B = 10_000; ALPHA = 0.05; MIN_SPEAKERS_CI = 5; BASELINE = "southern"
CREDITS_PER_MIN = 330; LEDGER_FACTOR_PCT = 105; MAX_WORKERS = 8; PILOT_CAP_MIN = 10.0; PILOT_REGIONS = ("southern", "midlands", "northern", "scottish", "welsh", "irish")
ID_RE = r"^[a-z0-9_]{1,64}$"   # filename-safe check for clip_id and speaker_id; ids are opaque strings and are never parsed or split

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
def build_manifest(clips_in_csv: Path, regions_csv: Path, out_csv: Path, report_csv: Path, strict: bool = False) -> list[Issue]: ...
def select_stage(clips_csv: Path, stage: str, out_csv: Path) -> list[dict[str, str]]: ...   # stage: smoke|pilot

# dummy.py
def make_dummy_data(out_dir: Path, clips_per_region: int = 4, speakers_per_region: int = 2, seconds: float = 20, words: int = 50, seed: int = SEED) -> None: ...

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

## 4. Data contract (source-agnostic)

How clips get here (own samples, an open dataset, a future recording drive) is decided in [data-sources.md](data-sources.md). Whatever the source, the code only sees one input file and local audio.

**`manifests/clips_in.csv`** (written by hand or by a per-dataset importer; the only file a human must produce):
`clip_id,set,speaker_id,region,task,audio_path,reference_path,source,notes`
- `clip_id`: unique, matches `ID_RE` (`^[a-z0-9_]{1,64}$`). It is an opaque label. Nothing parses it.
- `set`: `pilot` or `demo`.
- `speaker_id`: matches `ID_RE`. Unknown speaker? Use the `clip_id` (then each clip counts as its own speaker, and `low_n` stays true).
- `region`: a `region_id` from `config/regions.csv`.
- `task`: `read`, `spont` or `unknown`.
- `audio_path`: local file, relative to the repo root.
- `reference_path`: local `.txt` with the human transcript. **Optional for `demo` clips**: the clip is transcribed and shown, but not scored (`status=no_reference`). Required for `pilot` clips.
- `source`: free text (dataset name, `own`). `notes`: free text.

**Audio:** PCM16 WAV, mono, >=16 kHz. Anything else is a validation error whose message includes `ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav`. No resampling in the package. Audio files stay where they are, are never copied away or deleted, and can be played back by the notebook.

**References.** Write what was said, in words, no digits. Dialect spellings (`wee`, `nowt`, `aye`, `cannae`) stay as the dataset has them. No tool rewrites a dataset's reference beyond the normaliser (§6). If a reference was drafted from Scribe output, set `notes=ref_from_scribe` and treat that clip's WER as biased low.

**`manifests/clips.csv`** (from `ukstt build-manifest`): the `clips_in.csv` columns plus `audio_sha256,duration_s,sample_rate_hz,channels`.

**`manifests/validation_report.csv`**: `level,code,path,message`.
- Errors: `E_REGION_UNKNOWN`, `E_AUDIO_MISSING`, `E_AUDIO_FORMAT`, `E_AUDIO_TOO_SHORT` (<0.1 s), `E_REF_MISSING` (pilot only), `E_REF_EMPTY_AFTER_NORM`, `E_ID_BAD`, `E_DUP_CLIP`, `E_SET_BAD`.
- Warnings: `W_REF_DIGITS`, `W_REF_BRACKET`, `W_DURATION` (clip > 60 s), `W_SINGLE_CLIP_SPEAKER`.
- `build-manifest` exits 2 if there is any error (or any warning with `--strict`) and writes `clips.csv` only when there are no errors.

**Stage selection** (`select_stage`, deterministic, sorted by `clip_id`; its only input is `clips.csv`):
- `pilot`: every row with `set=pilot` and `region` in `PILOT_REGIONS`. Error if the total duration exceeds `PILOT_CAP_MIN` (10.0 min). Error if any pilot region has no clips.
- `demo`: every row with `set=demo`. Same cap check, counted separately.
- `smoke`: the first row of `pilot` (sorted by `clip_id`) with `region=southern`. It is a pilot subset, so the cache is reused by the pilot.
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
- `config/fake.toml [error_rates]`: southern 0.03, midlands 0.06, northern 0.08, scottish 0.14, welsh 0.08, irish 0.07 (made-up values for testing only).
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
- `spelling`: US→UK starter rows (`color→colour`, `favorite→favourite`, `center→centre`, `realize→realise`, `gray→grey`). The coder adds the US spellings that occur in the pilot references and in the pilot Scribe output. The list is closed.
- `filler`: `um umm uh uhm er erm hm hmm mm mmm mhm huh`. `huh` is there so that `uh-huh` becomes empty. Never fillers: `ah` (Scots), `eh`, `aye`, `like`, `yeah`.
- Dialect words (`wee nowt aye ye youse cannae dinnae yous …`) are never added.
- The file's SHA256 is stored in `run_manifest.json` (see §5).

## 7. Scoring rules

- **Alignment.** Levenshtein DP with unit costs, reference tokens on the rows. Backtrace from `(n, m)`: if `i==0` emit I; if `j==0` emit D; otherwise take the first that applies: (1) match if `ref[i-1]==hyp[j-1]` and `d[i][j]==d[i-1][j-1]`; (2) substitution if `d[i][j]==d[i-1][j-1]+1`; (3) deletion if `d[i][j]==d[i-1][j]+1`; (4) insertion. Reverse the ops afterwards.
- `WER = (S+D+I)/N`, **never clipped**. An empty hypothesis with N>0 gives D=N, WER=1.0.
- **N=0.** `wer` is empty (NA). `build-manifest` already rejects own references with zero words (`E_REF_EMPTY_AFTER_NORM`). Scoring raises `ValueError` if `n_ref==0` for any clip, so there is no `ref_empty` status.
- **CER is not computed in the pilot.**
- **Failed, missing, skipped or unreferenced clips** get `status=failed|missing|skipped_budget|no_reference` in `utterance_scores.csv`. They are excluded from WER and counted in `n_excluded`. They are never silently dropped. `no_reference` clips (demo clips without a transcript) are transcribed and visible in the notebook but never scored.
- **Aggregation.** Micro average (sum of errors / sum of words), never the mean of per-clip WERs. The unit in all statistics is the speaker.
- **Error pairs.** From alignment ops: `sub` (ref→hyp), `del` (ref→empty), `ins` (empty→hyp). Sorted by `-count, ref_word, hyp_word` (row order is the rank).
- `n_digit_tokens_hyp` is counted on the raw hypothesis text before rule 5.

## 8. Statistics (pilot)

- **Strata:** `task` in {read, spont}. There is no pooled "all" stratum.
- **Speaker counts.** `SpeakerCounts(errors, n_ref)` is summed over the speaker's scored clips in the stratum. Region WER = Σerrors/Σn_ref over speakers.
- **95% bootstrap CI** (alpha = `ALPHA` = 0.05), only if n_speakers >= `MIN_SPEAKERS_CI` (5). Below that, `bootstrap_ci` returns `None` and the CSV cells are empty. Every pilot region therefore has `low_n=true` and no CI. A bootstrap over 2 speakers is not an interval estimate.
  - `rng = random.Random(f"{SEED}:{task}|{region}")`. Draw `B=10000` resamples of the speakers with replacement. Take the pooled WER of each, sort ascending, return `percentile_interval(reps)` = `(reps[250], reps[9749])`.
- **Pairwise vs baseline** (pilot): `diff = wer_region − wer_southern`. No p-values, no CIs. The permutation test, Holm correction and difference CI are deferred to the full study (they cannot be informative at 2 vs 2 speakers: the minimum possible p is 1/3).
- Speaker metadata beyond `speaker_id` and `region` is not used. There is no adjustment for gender, age or recording quality.

## 9. Real-API budget (credits; `ceil(sec/60 x 330 x 1.05)` = 346.5 per minute, per clip with rounding up)

| Item | Audio | Credits |
|---|---|---|
| Free cap | 28.9 min on the ledger basis (30 min raw) | 10,000 |
| Smoke (one pilot clip; cached for the pilot, 0 extra) | one clip | at most 116 for 20 s |
| Pilot nominal (4 regions, about 8 min) | 8.0 min | about 2,772 |
| Pilot cap (`PILOT_CAP_MIN`) | 10.0 min | 3,465, plus up to 1 per clip for rounding |
| Demo set (a few short samples) | under 3 min | under 1,040 |
| Reserve after pilot at cap and 3 min demo | about 15 min | about 5,500 |

- The gate checks the sum of per-clip charges against `ledger.remaining()` before any network call, so the table is a guide, not the control.
- A booked read timeout costs one clip's charge and is not retried. Example: 20 s = 116 credits.
- Dollar figures are UNVERIFIED (X1) and are not used.
- A full study (about 7.5 h) is 148,500 raw credits and cannot run on a free key.

## 10. CLI (`python -m ukstt …` is equivalent; global `--config`)

```
ukstt --version
ukstt make-dummy-data --out dummy [--clips-per-region 4] [--speakers-per-region 2] [--seconds 20] [--seed 20261102]
ukstt build-manifest [--in manifests/clips_in.csv] [--regions config/regions.csv] [--out manifests/clips.csv]
      [--report manifests/validation_report.csv] [--strict]
ukstt select --clips manifests/clips.csv --stage {smoke|pilot|demo} [--out <clips dir>/<stage>.csv]
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-fake-001 [--backend fake|elevenlabs]
      [--max-audio-minutes N] [--workers N] [--refresh] [--fake-config config/fake.toml]
ukstt score --run-id pilot-fake-001 --clips manifests/pilot.csv [--out results/<run_id>] [--accept-normalise-change]
ukstt stats --run-id pilot-fake-001 [--out results/<run_id>]
ukstt ledger show        # spent, remaining credits and minutes, last 10 bookings
```

Real runs, in order:
```
ukstt transcribe --clips manifests/smoke.csv --run-id smoke-real-001 --backend elevenlabs --max-audio-minutes 1
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-real-001 --backend elevenlabs --max-audio-minutes 10
ukstt transcribe --clips manifests/demo.csv --run-id demo-real-001 --backend elevenlabs --max-audio-minutes 3
```

`make-dummy-data --out dummy` writes `dummy/manifests/clips_in.csv`, `dummy/recordings/*.wav` and `dummy/references/*.txt` for the six pilot regions (`clips_per_region` clips each, spread over 2 speakers, `set=pilot`, with a few extra `set=demo` clips that have no reference). Noise WAVs are seeded from `sha256(clip_id)[:8]`, so no two clips are byte-identical. Dummy runs use the same dirs as real ones, with ids prefixed `dummy-`. Run dummy commands with `--in dummy/manifests/clips_in.csv --out dummy/manifests/clips.csv`.

Output CSVs in `results/<run_id>/` (floats via `fmt_float`, booleans `true/false`, NA = empty cell):
- `utterance_scores.csv`: `run_id,clip_id,set,speaker_id,region,task,status,n_ref,n_hyp,hits,subs,dels,ins,wer,n_digit_tokens_hyp,source`
- `speaker_scores.csv`: `region,task,speaker_id,n_clips,n_ref,subs,dels,ins,errors,wer`
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
  - `ID_RE` accepts `scottish_4310`, `clip_7`; rejects spaces, uppercase, `/`, empty and 65 characters.
  - Dummy data → 0 errors; `select pilot` returns every pilot-region clip and the total is under 10.0 min; `select demo` returns only `set=demo`; smoke is a southern pilot clip.
  - Demo clips without a reference build fine and score as `no_reference`; a pilot clip without one is `E_REF_MISSING`.
  - Negative cases, one per error code: wrong sample rate, stereo, missing audio file, missing ref (pilot), unknown region, duplicate clip_id, empty-after-norm ref, bad id, bad `set`. A pilot region with no clips → error; pilot over 10.0 min → error.
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
- `test_e2e_dummy.py`: dummy set with `speakers_per_region=10`, `clips_per_region=20`, `words=100` (clip seconds small). Run select → transcribe (fake) → score → stats. Assert that two runs give byte-identical CSVs, that each region's read WER is within 0.03 of its configured fake rate, and that CIs are present (n≥5).

## 12. Build order with acceptance checks (AUTO = scripted, MANUAL = human)

- **S0 Scaffold.**
  - Create pyproject, `.env.sample`, `.gitignore`, config skeletons, `__main__.py`, `tests/test_version.py`.
  - Verify every pin (runtime, dev and `[notebook]`) with `pip index versions`.
  - AUTO: `pip install -e .[dev]` in a fresh venv; `pytest -q` passes; `ukstt --version` prints `0.1.0`; `python -m ukstt --version` works; `git check-ignore .env .env.local` succeeds and `.env.sample` is not ignored.
- **S1 Normalise and score.** `numbers`, `normalise`, `score`, `normalise.csv`. AUTO: `test_normalise`, `test_numbers`, `test_score` pass.
- **S2 Stats.** AUTO: `test_stats` passes.
- **S3 Manifests, dummy data and select.** AUTO: `ukstt make-dummy-data --out dummy`; `ukstt build-manifest --in dummy/manifests/clips_in.csv --out dummy/manifests/clips.csv --report dummy/manifests/validation_report.csv` exits 0; `ukstt select --clips dummy/manifests/clips.csv --stage pilot` returns the pilot clips under 10.0 min; `test_manifest` passes.
- **S4 Fake, cache and runner** (`ledger=None` legal for fake only; real with None raises). AUTO: `test_cache`, `test_fake`, `test_runner` pass; `ukstt transcribe --clips dummy/manifests/pilot.csv --run-id dummy-pilot-001` gives one `ok` row per pilot clip, and a second invocation makes 0 transcriber calls.
- **S5 End to end on dummy.** `aggregate.py`, CLI score and stats. AUTO: `test_e2e_dummy` passes; `results/dummy-pilot-001/` has all five CSVs; with 2 speakers per region every pilot `low_n` is `true` and CIs are empty.
- **S5b Notebook.** `notebooks/results.ipynb`, built with `nbformat` and committed with outputs cleared. First cell sets `RUN_ID` (default `dummy-pilot-001`). Cells: (1) load `results/<RUN_ID>/*.csv` and `manifests/clips.csv` with pandas; (2) bar chart of WER by region, one panel per `task`, `ci_lo`/`ci_hi` error bars where present, bars hatched when `low_n`; (3) stacked substitution/deletion/insertion rates per region; (4) strip plot of speaker WER per region; (5) top error pairs per region as a table; (6) a clip browser: for each clip show `IPython.display.Audio(audio_path)`, the reference, and the hypothesis (`runs/<RUN_ID>/raw/<clip_id>.json["text"]`) side by side with differing words highlighted. Demo clips appear in (6) even without a reference. AUTO: `jupyter nbconvert --to notebook --execute notebooks/results.ipynb` succeeds on the dummy run. MANUAL: you open it and the charts and players look right.
- **S6 Ledger, ElevenLabs and gate.** AUTO: `test_ledger` and `test_elevenlabs` pass; `ukstt transcribe --backend elevenlabs --clips dummy/manifests/smoke.csv --run-id x` with no `--max-audio-minutes` exits 2 with zero network calls; `ukstt ledger show` works on an empty ledger. MANUAL: reconcile `credits_already_used` with the ElevenLabs dashboard.
- **S7 Real smoke (attended; key in `.env.local`; needs the first real clips).** MANUAL/AUTO: HTTP 200; `raw/*.json` has `text` and `words[]`; the ledger charge equals `charge_credits(duration_s)` for the clip; the log status is `ok`. If 401/402/403: stop and report that the free key cannot call STT. No retry loop.
- **S8 Real pilot and demo (needs the dataset clips from data-sources.md and, for demo, your own samples).**
  - AUTO: every pilot clip `ok` or `cached`; cumulative ledger delta since S7 <= the sum of per-clip charges; `score` and `stats` write all five CSVs; every row has `low_n=true` unless a region has >=5 speakers. Demo clips are `ok` with status `no_reference` in scoring.
  - MANUAL: open the notebook on `pilot-real-001` and `demo-real-001`; listen to 3 clips and check the alignments; southern WER above 0.25 means investigate (soft).
- **S9 Approval gate for the full study.** No code. Give the user the pilot tables, the §9 numbers and a per-region speaker and minutes estimate. Proceed only on an explicit yes with a plan that has enough credits.

S1–S5b need no audio and no key. S7 and S8 need the dataset clips (see data-sources.md) and your key in `.env.local`.

## Appendix: pilot dataset notes (VERIFIED 2026-11-03)

- **Source:** `ylacombe/english_dialects` on Hugging Face, a copy of OpenSLR SLR83 (Google). License `cc-by-sa-4.0` (HF tags and card). Attribution and share-alike apply if clips are redistributed. 17,877 rows, 8.98 GB in total; we use the datasets-server rows API for a few clips, not the full download.
- **Fields:** `line_id`, `audio`, `text`, `speaker_id` (int). Transcripts are lowercase-ish with no punctuation, numbers spelled out. Read sentences only.
- **Subsets (config names):** `irish_male` 450 rows, `midlands_female` 246, `midlands_male` 450, `northern_female` 750, `northern_male` 2,097, `scottish_female` 894, `scottish_male` 1,649, `southern_female` 4,161, `southern_male` 4,331, `welsh_female` 1,199, `welsh_male` 1,650. There is no `irish_female`.
- **Speaker IDs repeat across subsets** (for example 2484, 3397 and 4310 appear in Irish, Midlands, Northern, Scottish and Welsh; 12484 in both Welsh subsets). Whether these are the same people is UNKNOWN. The importer therefore keys a speaker as `<region>_<speaker_id>` (e.g. `scottish_4310`) so nothing collides. Speaker counts per region are therefore by this key, and could be inflated or deflated if IDs are reused or shared.
- **Audio:** WAV, 48 kHz, mono, 16-bit (the 36 fetched clips). Passes the PCM16 mono >=16 kHz rule with no conversion.
- **Fetched sample (`scripts/fetch_english_dialects_samples.py`):** male subsets, 2 speakers per label (most-seen in 8 sampled windows), up to 3 clips each of at most 12 s: 36 clips, 192 s (3.2 min), 6 clips and about 32 s per label. The script writes `data/audio/<clip_id>.wav`, `references/<clip_id>.txt` and `manifests/clips_in.csv`, with `clip_id = <region>_<speaker_id>_<line_id lowercase>`. It retries on HTTP 429 and 5xx (the server rate-limits).
- **Known limits:** read speech only, so no spontaneous stratum; dialect labels are self-identified and coarse; a handful of speakers per label in the sample; sentences were chosen to elicit accent differences (place names, airlines, personal names), which may be harder than ordinary speech; the dataset is public and may be in the model's training data.
