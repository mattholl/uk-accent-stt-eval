# Implementation plan: uk-accent-stt-eval

Status: round 3 (consistency pass after the dataset pivot), ready for the coder. Nothing else needs to be asked: every open item is either decided here or explicitly optional (the demo set). Tags: **DECIDED** = user decision, **VERIFIED** = checked fact, **PROPOSED** = plan author's choice, changeable. Package `ukstt`. `requires-python = ">=3.11"`. Developed on 3.14.9. Avoid 3.12+ syntax (no `type` statements, no PEP 695 generics).

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
| D7 | Key | Free ElevenLabs key: 10,000 credits/month. Measured on this account: about 61 credits per audio minute (the pricing page's 330/min was 5x too high), so about 2.7 h/month | DECIDED |
| D8 | Dev approach | Default backend is `fake`. The real API is gated. | DECIDED |
| P1 | Pilot | Dataset `ylacombe/english_dialects` (Hugging Face copy of OpenSLR SLR83, CC BY-SA 4.0, read speech only). Male subsets only (Irish exists only as male). The 36-clip pilot was 2 speakers per label x 3 clips (3.2 min, about 200 credits). The study set used for results is **840 clips, 47 speakers, 85.6 min of audio (82.4 min sent), about 5,030 credits** (`large-001`): 10 to 11 speakers in Southern, Northern, Scottish and Welsh, 3 each in Irish and Midlands. Already fetched by `scripts/fetch_english_dialects_samples.py`. | DECIDED |
| P2 | Pilot cap | Pilot refused if total duration > 10.0 min (allows a larger second fetch later). | PROPOSED |
| P12 | Scope cuts | No credit ledger, no response cache, no concurrency stress tests. Add one only if real use shows a need (decided with the user 2026-11-03). Kept: retry/backoff, concurrency, property tests, notebook. | DECIDED |
| P3 | Full study | About 10 speakers/region, about 7.5 h = about 27,500 credits at the measured rate. Needs a paid plan and user approval. Not built or run. | PROPOSED |
| P4 | Data | Two sets. `pilot`: the dataset clips above. `demo`: a few informal clips found online by the project owner, for listening and general interest: no standard text, no statistics, reference optional, `source` records provenance. | PROPOSED |
| P5 | Scribe params | `model_id=scribe_v2, language_code=eng, tag_audio_events=false, timestamps_granularity=word, diarize=false, no_verbatim=false, seed=20261102, file_format=other`. `temperature` unset, no keyterms or surcharged options. | PROPOSED |
| P6 | Fillers | Kept in the verbatim transcript, stripped from both sides by the `filler` rows in `config/normalise.csv` | PROPOSED |
| P7 | Audio | No resampling. Input must be PCM16 mono WAV >=16 kHz. | PROPOSED |
| P8 | Stats (pilot) | Pooled WER, per-region diff to baseline, speaker bootstrap 95% CI only when n_speakers >= 5. Permutation, Holm and difference CIs are deferred to the full study. | PROPOSED |
| P9 | Dependencies | Runtime: `requests` only. Stdlib for math, WAV, CSV. No numpy/scipy/tenacity/dotenv. Optional extra `[notebook]`: pandas, matplotlib, jupyter, nbformat (pins verified in S0). | PROPOSED |
| P10 | Register contractions | `gonna wanna gotta kinda sorta cos 'cause` are mapped to long forms on both sides. Dialect words are never mapped. | PROPOSED |
| P11 | Audio on disk | Audio is never deleted or moved by the tool. `audio_path` in the manifest points at the local file (demo samples under `recordings/`, dataset clips under `data/audio/`, both gitignored). The notebook plays clips with `IPython.display.Audio`. | PROPOSED |
| X1 | Dollar cost | Any dollar figure (e.g. the $0.22/h API pay-as-you-go price) is **UNVERIFIED** as a credit conversion and is used in no decision. | NOTE |

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
  .gitignore         # exists: .env, /.env.local, /data/ /results/ /dummy/ /recordings/ /runs/. S0 appends: .venv/ __pycache__/ *.egg-info/ .pytest_cache/ .ipynb_checkpoints/. `.env.sample` stays tracked.
  config/            # study.toml regions.csv normalise.csv fake.toml   (full contents in §3a)
  scripts/           # fetch_english_dialects_samples.py (exists; writes data/audio, references, manifests/clips_in.csv). Not part of the package, no tests.
  references/        # <clip_id>.txt  human reference transcript, one per clip (optional for demo clips)
  recordings/        # own demo samples: <clip_id>.wav (gitignored)     data/audio/  dataset clips (gitignored)
  manifests/         # clips_in.csv (importer output, pilot)  demo_in.csv (hand-written, optional)  clips.csv validation_report.csv pilot.csv smoke.csv demo.csv
  runs/<run_id>/{run_manifest.json,clips.csv,transcribe_log.csv,raw/}   results/<run_id>/…
  src/ukstt/
    __init__.py (__version__="0.1.0")  __main__.py (calls cli.main)  constants.py  config.py  csvio.py  audio.py
    manifest.py  dummy.py  numwords.py  normalise.py  score.py  stats.py  aggregate.py  cli.py
    transcribe/{__init__.py, base.py, fake.py, elevenlabs.py, runner.py}
  notebooks/results.ipynb   # pandas + matplotlib; reads results/<run_id>/*.csv, clips.csv, runs/<run_id>/raw/*.json
  tests/
```

Pins are placeholders until S0 verifies each with `pip index versions <pkg>`; bump any that do not exist. Suggested: `requests==2.34.2`, `pytest==9.2.0`, `responses==0.26.3`.

### 3a. Config files (exact contents; S0 creates them)

`config/study.toml` (`load_config` fills any missing key from the `constants.py` default and rejects unknown keys):
```toml
[params]            # native types; sent via wire_params()
model_id = "scribe_v2"
language_code = "eng"
tag_audio_events = false
timestamps_granularity = "word"
diarize = false
no_verbatim = false
seed = 20261102
file_format = "other"

[http]
max_retries = 3
connect_timeout_s = 10
read_timeout_s = 120
default_workers = 4

[paths]
runs_dir = "runs"
results_dir = "results"
```

`config/regions.csv`: the six rows of §2, in that order, header `region_id,display_name,slr83_label,is_baseline`, `is_baseline` as `true`/`false`. The display names are the §2 table text (use the short form `Northern English (coarse)` for northern).

`config/fake.toml`:
```toml
[error_rates]
southern = 0.03
midlands = 0.06
northern = 0.08
scottish = 0.14
welsh = 0.08
irish = 0.07
unknown = 0.10      # demo clips
```

`config/normalise.csv`: header `from,to,class`, then exactly the rows listed in §6 (the coder may add US spellings, see §6). Filler rows have an empty `to`.

### Signatures (type-annotated)

```python
# constants.py
SEED = 20261102; B = 10_000; ALPHA = 0.05; MIN_SPEAKERS_CI = 5; BASELINE = "southern"
MAX_WORKERS = 8; PILOT_CAP_MIN = 10.0; DEMO_CAP_MIN = 3.0; PILOT_REGIONS = ("southern", "midlands", "northern", "scottish", "welsh", "irish")
ID_RE = r"^[a-z0-9_]{1,64}$"   # filename-safe check for clip_id and speaker_id; ids are opaque strings and are never parsed or split

# config.py  (study.toml -> frozen dataclass)
@dataclass(frozen=True)
class StudyConfig:
    params: dict[str, object]            # native types; sent via wire_params()

    max_retries: int                     # 3
    connect_timeout_s: float; read_timeout_s: float   # 10, 120
    default_workers: int                 # 4
    runs_dir: Path; results_dir: Path
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
def build_manifest(clips_in_csvs: Sequence[Path], regions_csv: Path, out_csv: Path, report_csv: Path, strict: bool = False) -> list[Issue]: ...   # inputs are concatenated in the order given
def select_stage(clips_csv: Path, stage: str, out_csv: Path) -> list[dict[str, str]]: ...   # stage: smoke|pilot|demo

# dummy.py
def make_dummy_data(out_dir: Path, clips_per_region: int = 4, speakers_per_region: int = 2, seconds: float = 20, words: int = 50, seed: int = SEED) -> None: ...

# numwords.py   (not `numbers.py`: that name shadows the stdlib module)
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
class ReadTimeout(TranscribeError): ...       # request was sent (it may already be billed); NOT retried
class ConnectError(TranscribeError): ...      # never sent; retried
class MalformedResponse(TranscribeError): ...
class Transcriber(Protocol):
    name: str
    def transcribe(self, audio_path: Path, params: Mapping[str, object]) -> dict: ...
def validate_response(raw: Mapping) -> None: ...   # MalformedResponse unless raw["text"] is a str. Runner calls it for BOTH backends.
def wire_params(params: Mapping[str, object]) -> dict[str, str]: ...   # bool -> "true"/"false", else str(v). Used by the POST and stored in run_manifest.json.

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
    def transcribe(self, audio_path, params) -> dict: ...   # ONE POST, no retry

# transcribe/runner.py
def call_with_retry(fn: Callable[[], T], *, max_retries: int, sleep: Callable[[float], None] = time.sleep) -> T: ...
@dataclass(frozen=True)
class RunOptions: run_id: str; backend: str; max_audio_minutes: float | None; workers: int; force: bool
def run_transcription(clips, opts, cfg, transcriber, sleep=time.sleep) -> int: ...   # exit code
```

## 4. Data contract (source-agnostic)

How clips get here (clips found online, an open dataset, a future recording drive) is decided in [data-sources.md](data-sources.md). Whatever the source, the code only sees one input file and local audio.

**`manifests/clips_in.csv`** (written by the fetch script) and the optional hand-written **`manifests/demo_in.csv`** (same columns; the fetch script never touches it, so re-fetching cannot erase demo rows). `build-manifest --in` is repeatable; the default is `manifests/clips_in.csv` plus `manifests/demo_in.csv` if that file exists. Readers accept CRLF line endings (the fetch script writes CRLF); `csvio.read_csv` opens with `newline=''` and the `csv` module handles both. Columns:
`clip_id,set,speaker_id,region,task,audio_path,reference_path,source,notes`
- `clip_id`: unique, matches `ID_RE` (`^[a-z0-9_]{1,64}$`). It is an opaque label. Nothing parses it.
- `set`: `pilot` or `demo`.
- `speaker_id`: matches `ID_RE`. Unknown speaker? Use the `clip_id` (then each clip counts as its own speaker, and `low_n` stays true).
- `region`: a `region_id` from `config/regions.csv`. **Demo clips only** may use the literal `unknown` (an informal sample has no verified label); `unknown` on a pilot clip is `E_REGION_UNKNOWN`.
- `task`: `read`, `spont` or `unknown`. Pilot clips must be `read` or `spont` (`E_TASK_BAD` otherwise). Demo clips may be `unknown`.
- `audio_path`: local file, relative to the repo root.
- `reference_path`: local `.txt` with the human transcript. **Optional for `demo` clips**: the clip is transcribed and shown, but not scored (`status=no_reference`). Required for `pilot` clips.
- `source`: free text (dataset name, `own`). `notes`: free text.

**Audio:** PCM16 WAV, mono, >=16 kHz. Anything else is a validation error whose message includes `ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav`. No resampling in the package. Audio files stay where they are, are never copied away or deleted, and can be played back by the notebook.

**References.** For demo clips write what was said, in words, no digits. Dataset references are used exactly as fetched: capitalised, unpunctuated, mostly spelled-out numbers, but 3 of the 36 fetched references contain digits (`C2c`, `1930`, `5th`, `950`); they raise `W_REF_DIGITS` (a warning, not an error) and the normaliser handles them (§6). Dialect spellings (`wee`, `nowt`, `aye`, `cannae`) stay as the dataset has them. No tool rewrites a dataset's reference beyond the normaliser (§6). If a reference was drafted from Scribe output, set `notes=ref_from_scribe` and treat that clip's WER as biased low.

**`manifests/clips.csv`** (from `ukstt build-manifest`): the `clips_in.csv` columns plus `audio_sha256,duration_s,sample_rate_hz,channels`.

**`manifests/validation_report.csv`**: `level,code,path,message`.
- Errors: `E_REGION_UNKNOWN`, `E_TASK_BAD`, `E_AUDIO_MISSING`, `E_AUDIO_FORMAT`, `E_AUDIO_TOO_SHORT` (<0.1 s), `E_REF_MISSING` (pilot only), `E_REF_EMPTY_AFTER_NORM`, `E_ID_BAD`, `E_DUP_CLIP`, `E_SET_BAD`.
- Warnings: `W_REF_DIGITS`, `W_REF_BRACKET`, `W_DURATION` (clip > 60 s), `W_SINGLE_CLIP_SPEAKER`.
- `build-manifest` exits 2 if there is any error (or any warning with `--strict`) and writes `clips.csv` only when there are no errors. The report is always written. The 3 digit-bearing dataset references make `--strict` fail on the real pilot, so never use `--strict` there.

**Stage selection** (`select_stage`, deterministic, sorted by `clip_id`; its only input is `clips.csv`):
- `pilot`: every row with `set=pilot` and `region` in `PILOT_REGIONS`. Error if the total duration exceeds `PILOT_CAP_MIN` (10.0 min). Error if any pilot region has no clips.
- `demo`: every row with `set=demo`. Cap check against `DEMO_CAP_MIN = 3.0` (add to `constants.py`), counted separately. Error if there are no demo rows.
- `smoke`: the first row of `pilot` (sorted by `clip_id`) with `region=southern`. It is also in the pilot, so the pilot run sends it a second time (a few seconds of audio; accepted, there is no cache).
- Default `--out` is `<dir of clips.csv>/<stage>.csv`.

## 5. Transcription behaviour

**Params** come from `config/study.toml [params]` (native types). `wire_params()` turns them into strings (`"true"`/`"false"`) for the multipart POST. `temperature` is absent.

**Real call.** One `requests.post(URL, headers={"xi-api-key": key}, data=wire, files={"file": (name, fh, "audio/wav")}, timeout=(10, 120))`.
- The key is read from env `ELEVENLABS_API_KEY`, else from `.env.local` via a 6-line parser for lines `ELEVENLABS_API_KEY=value` (optional `export ` prefix, optional surrounding quotes, `#` comment lines skipped; other variable names ignored). If the variable is absent the error names `ELEVENLABS_API_KEY` and the file, never a value. Never read `.env` or other `.env*` files. This happens only for the real backend. A missing key exits 2. Never log the key.
- Exceptions: `requests.ReadTimeout` → `ReadTimeout`. `requests.ConnectTimeout` and `ConnectionError` → `ConnectError`. Check ConnectTimeout first, because it also subclasses `Timeout`.
- Status: 200 ok. 401/402/403 → `AuthOrQuotaError`. 429 and 5xx → `HttpError`. Other 4xx → `HttpError`. A non-JSON body → `MalformedResponse`.
- The runner then calls `validate_response` (needs `text` as str) for both backends.

**Retries** (`call_with_retry`, about 15 lines, no tenacity):
```
for k in range(max_retries + 1):
    try: return fn()
    except (HttpError with status 429 or >=500, ConnectError) as e:
        if k == max_retries: raise
        sleep(max(getattr(e, "retry_after", None) or 0, min(30, 2 * 2**k) + random.random()))
```
- `max_retries=3`, so 4 attempts. The fake backend uses the same wrapper. Tests pass `sleep=lambda s: None`.
- NOT retried: `ReadTimeout`, `MalformedResponse`, `AuthOrQuotaError`, other 4xx. They fail the clip immediately (`AuthOrQuotaError` aborts the run).

**Real gate** (checked before any network I/O; exit 2 on failure):
1. `--backend elevenlabs` given explicitly (default is fake).
2. `--max-audio-minutes N` given, and the total duration of the clips about to be sent is at most `N*60`. This is the only spend guard; there is no credit ledger. Check the ElevenLabs dashboard for what is left of the month.
3. API key present.
4. `--workers` is clamped to `min(workers, 8)`. The real default is 4.

**Run state and resume.**
- `runs/<run_id>/run_manifest.json`: `run_id, created_utc, backend, params (wire), clips_file_sha256, normalise_csv_sha256`. `transcribe` also copies the clips file it was given to `runs/<run_id>/clips.csv` (a snapshot; `score` and the notebook read this copy, so they work for dummy and real runs alike).
- Re-running an existing `run_id` resumes: a clip whose `raw/<clip_id>.json` already exists is not sent again (log status `skipped`). `--force` sends every clip again and overwrites the raw files. It exits 2 if `params` or `clips_file_sha256` differ from the manifest. `score` exits 2 if `normalise_csv_sha256` differs from the current `config/normalise.csv`, unless `--accept-normalise-change` is given (which rewrites the hash).
- `transcribe_log.csv` is append-only: `ts_utc,clip_id,backend,status,attempts,http_status,latency_s,audio_seconds,error`. `status` is `ok|skipped|failed`.
- `raw/<clip_id>.json` is the verbatim response (including `words[]`), written atomically (temp file then `os.replace`). Malformed responses are never written.
- `ThreadPoolExecutor`. Log writes are lock-protected. Outputs are ordered by `clip_id`.
- Exit codes: 0 ok; 2 usage, gate or validation; 4 some clips failed (resume to retry); 5 `AuthOrQuotaError` (stop submitting, let in-flight clips finish). When several apply, return the highest.

**FakeTranscriber.**
- Returns `{"language_code":"eng","language_probability":1.0,"text":…,"words":[{"text","start","end","type":"word"}…]}`. Word-type items only.
- A clip with no reference (demo) gets the fixed hypothesis `This is a fake transcript.` (rate and region are ignored). Otherwise the hypothesis = the reference with a per-word draw at `error_rates[region]`. The draw is substitute, delete or insert (1/3 each), from `random.Random(f"{seed}:{clip_id}")`. Substituted and inserted words come from a fixed list of letters-only nonsense words, never equal to the original. The text is capitalised and ends with a full stop.
- `config/fake.toml [error_rates]` (§3a): made-up values for testing only. `from_clips` reads each clip's reference text via `reference_path` (resolved against `repo_root`), the region from the row, and `unknown` for demo rows.
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
- **N=0.** `align` returns `wer=None` (library level, tested). `wer` is empty (NA) in a CSV cell only for `failed`, `missing`, `skipped_budget` and `no_reference` rows. `build-manifest` already rejects own references with zero words (`E_REF_EMPTY_AFTER_NORM`). Scoring raises `ValueError` if `n_ref==0` for any clip, so there is no `ref_empty` status.
- **CER is not computed in the pilot.**
- **Demo clips (`set=demo`)** with a reference get an `ok` row in `utterance_scores.csv` (their own WER, for the notebook) but are never written to `speaker_scores.csv` or any later table. `stats` therefore only ever sees pilot clips. Demo clips without a reference get `no_reference`.
- **Failed, missing or unreferenced clips** get `status=failed|missing|no_reference` in `utterance_scores.csv`. They are excluded from WER and counted in `n_excluded`. They are never silently dropped. `no_reference` clips (demo clips without a transcript) are transcribed and visible in the notebook but never scored.
- **Aggregation.** Micro average (sum of errors / sum of words), never the mean of per-clip WERs. The unit in all statistics is the speaker.
- **Error pairs.** From alignment ops: `sub` (ref→hyp), `del` (ref→empty), `ins` (empty→hyp). Sorted by `-count, ref_word, hyp_word` (row order is the rank).
- `n_digit_tokens_hyp` = the number of whitespace-separated tokens of the raw hypothesis text (before rule 1) that contain at least one character for which `str.isdigit()` is true.

## 8. Statistics (pilot)

- **Strata:** every `task` value present among scored pilot clips (`read`, `spont`; the current pilot has only `read`). There is no pooled "all" stratum. `region_summary.csv` has one row per (task, region) with at least one pilot clip.
- **Speaker counts.** `SpeakerCounts(errors, n_ref)` is summed over the speaker's scored clips in the stratum. Region WER = Σerrors/Σn_ref over speakers.
- **95% bootstrap CI** (alpha = `ALPHA` = 0.05), only if n_speakers >= `MIN_SPEAKERS_CI` (5). Below that, `bootstrap_ci` returns `None` and the CSV cells are empty. Every pilot region therefore has `low_n=true` and no CI. A bootstrap over 2 speakers is not an interval estimate.
  - `rng = random.Random(f"{SEED}:{task}|{region}")`. Draw `B=10000` resamples of the speakers with replacement. Take the pooled WER of each, sort ascending, return `percentile_interval(reps)` = `(reps[250], reps[9749])`.
- **Pairwise vs baseline** (pilot): one row per (task, non-baseline region); `diff = wer_region − wer_southern`; `wer_base` and `diff` are empty if the baseline has no scored speaker in that task. No p-values, no CIs. The permutation test, Holm correction and difference CI are deferred to the full study (they cannot be informative at 2 vs 2 speakers: the minimum possible p is 1/3).
- Speaker metadata beyond `speaker_id` and `region` is not used. There is no adjustment for gender, age or recording quality.

## 9. Budget (information only, nothing enforces it)

The free plan gives 10,000 credits a month. Measured on this account: about 61 credits per audio minute (the pricing page's 330/min was 5x too high), so about 2.7 hours of audio. Nothing in the code counts credits. The only guard is `--max-audio-minutes`; the ElevenLabs dashboard shows what is left.

| Run | Audio | Credits at 61/min |
|---|---|---|
| Smoke (one clip) | under 10 s | under 10 |
| Pilot (36 clips, 192 s) | 3.2 min | about 200 |
| Study set (`large-001`, 840 clips) | 82.4 min sent | about 5,030 |
| Demo set (your samples, cap 3.0 min) | under 3 min | under 190 |
| Re-running a finished run with `--force` | same as the run | same as the run |

- A full study (about 7.5 h) is about 27,500 credits and cannot run on a free key.
- Dollar figures are UNVERIFIED (X1) and are not used.
- If real use shows the free tier is a problem, add a cache or a ledger then. Not before.

## 10. CLI (`python -m ukstt …` is equivalent; global `--config`)

```
ukstt --version
ukstt make-dummy-data --out dummy [--clips-per-region 4] [--speakers-per-region 2] [--seconds 20] [--seed 20261102]
ukstt build-manifest [--in manifests/clips_in.csv --in manifests/demo_in.csv ...] [--regions config/regions.csv] [--out manifests/clips.csv]
      [--report manifests/validation_report.csv] [--strict]
ukstt select --clips manifests/clips.csv --stage {smoke|pilot|demo} [--out <clips dir>/<stage>.csv] [--cap-minutes X]   # X: pilot only
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-fake-001 [--backend fake|elevenlabs]
      [--max-audio-minutes N] [--workers N] [--force] [--fake-config config/fake.toml]
ukstt score --run-id pilot-fake-001 --clips manifests/pilot.csv [--out results/<run_id>] [--accept-normalise-change]
ukstt stats --run-id pilot-fake-001 [--out results/<run_id>]
```

Real runs, in order (first `ukstt build-manifest` with no flags, then `ukstt select --clips manifests/clips.csv --stage smoke`, and the same for `pilot` and, if `manifests/demo_in.csv` exists, `demo`):
```
ukstt transcribe --clips manifests/smoke.csv --run-id smoke-real-001 --backend elevenlabs --max-audio-minutes 1
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-real-001 --backend elevenlabs --max-audio-minutes 10
ukstt transcribe --clips manifests/demo.csv --run-id demo-real-001 --backend elevenlabs --max-audio-minutes 3      # only if the user supplied demo samples
ukstt score --run-id pilot-real-001 --clips manifests/pilot.csv && ukstt stats --run-id pilot-real-001
```

`make-dummy-data --out dummy` writes `dummy/manifests/clips_in.csv`, `dummy/recordings/*.wav` and `dummy/references/*.txt` for the six pilot regions (`clips_per_region` clips each, spread over `speakers_per_region` speakers, `set=pilot`, `task=read`, speaker ids `<region>_<nn>`, clip ids `<speaker_id>_<nn>`, each clip `seconds` long with a reference of `words` words drawn seeded from a fixed 50-word letters-only vocabulary), plus 3 extra `set=demo` clips `demo_01..03` (`region=unknown`, `task=unknown`, speaker = clip id, 5 s, no reference). Noise WAVs are seeded from `sha256(clip_id)[:8]`, so no two clips are byte-identical. Dummy runs use the same dirs as real ones, with ids prefixed `dummy-`. Run dummy commands with `--in dummy/manifests/clips_in.csv --out dummy/manifests/clips.csv`.

Output CSVs in `results/<run_id>/` (floats via `fmt_float`, booleans `true/false`, NA = empty cell):
- `utterance_scores.csv`: `run_id,clip_id,set,speaker_id,region,task,status,n_ref,n_hyp,hits,subs,dels,ins,wer,n_digit_tokens_hyp,source`
- `speaker_scores.csv`: `region,task,speaker_id,n_clips,n_ref,subs,dels,ins,errors,wer`
- `region_summary.csv`: `task,region,n_speakers,n_clips,n_excluded,n_ref,subs,dels,ins,wer,ci_lo,ci_hi,low_n`
- `pairwise_vs_baseline.csv`: `task,region,n_spk_region,n_spk_base,wer_region,wer_base,diff,low_n`
- `error_pairs.csv`: `task,region,type,ref_word,hyp_word,count`

## 11. Tests (pytest; no real network)

`tests/conftest.py`: an autouse fixture makes `socket.socket.connect` raise. `responses` mocks HTTP. Use `tmp_path` for all I/O. Build configs with `dataclasses.replace(cfg, runs_dir=…, results_dir=…)`.

- `test_version.py`: `ukstt.__version__ == "0.1.0"`.
- `test_normalise.py`: one case per rule, then the full pipeline.
  - `"Don’t—stop!"` → `["don't","stop"]`.
  - `"It's £5, 1,000 and 3.5%"` → `["it's","five","pounds","one","thousand","and","three","point","five","per","cent"]`.
  - `"Um, the colour (laughs) [unclear] well-known"` → `["the","colour","well","known"]`.
  - `"'cause"` → `["because"]`; `"yes,no"` → `["yes","no"]`; `"7:30"` → `["seven","thirty"]`; `"uh-huh"` → `[]`.
  - `"gonna"` → `["going","to"]`; `nowt`, `wee`, `aye`, `ah` unchanged. `"1984"` → cardinal words. `"007"` and `"5pm"` untouched.
  - Idempotence: `normalise(" ".join(normalise(x))) == normalise(x)`.
- `test_numwords.py` (module `ukstt.numwords`): 0, 13, 21 (`twenty one`), 100, 105, 1001, 999999, 1,000,000.
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
  - Demo clips (`region=unknown`) without a reference build fine and score as `no_reference`; a demo clip with a reference is scored in `utterance_scores` only and never reaches `speaker_scores`; a pilot clip without a reference is `E_REF_MISSING`; `region=unknown` or `task=unknown` on a pilot clip is an error.
  - Negative cases, one per error code: wrong sample rate, stereo, missing audio file, missing ref (pilot), unknown region, duplicate clip_id, empty-after-norm ref, bad id, bad `set`. A pilot region with no clips → error; pilot over 10.0 min → error.
- `test_fake.py`: determinism; each failure token behaves as listed; the error rate is recovered on a large sample.
- `test_runner.py` (fake backend, `sleep` stubbed):
  - 429, 429, ok → ok in 3 attempts.
  - 500 x4 → failed, exit 4.
  - Resume after a simulated crash redoes only the missing clip.
  - An existing `raw/<clip_id>.json` → the clip is `skipped`, no transcriber call; `--force` sends it again.
  - 8 workers equal 1 worker in output; `workers>8` is clamped.
  - Run-manifest mismatch → exit 2.
  - `AuthOrQuotaError` → exit 5, nothing further submitted.
  - A `malformed` response is rejected by `validate_response`; `empty` is scored D=N.
- `test_elevenlabs.py` (`responses`):
  - The multipart body carries every param (booleans lowercase), has the `xi-api-key` header, and has no `temperature`.
  - 200 → ok. ReadTimeout is not retried (clip failed, exit 4). ConnectTimeout is retried.
  - 429 then 200 → ok on the second attempt.
  - `wire_params` turns bools into lowercase strings.
  - 401 → exit 5.
  - Malformed 200 → clip failed, not retried, no raw file.
  - Gates (zero HTTP calls in each): no `--max-audio-minutes` → exit 2; missing key → exit 2; clips longer in total than the cap → exit 2.
  - The key never appears in logs or the manifest.
- `test_e2e_dummy.py`: dummy set with `speakers_per_region=10`, `clips_per_region=20`, `words=100`, `seconds=4` (6 x 20 x 4 s = 8 min, under the 10.0 min pilot cap). Run select → transcribe (fake) → score → stats. Assert that two runs give byte-identical CSVs, that each region's read WER is within 0.03 of its configured fake rate, and that CIs are present (n≥5).

## 12. Build order with acceptance checks (AUTO = scripted, MANUAL = human)

- **S0 Scaffold.**
  - Create pyproject, `.env.sample`, `.gitignore`, config skeletons, `__main__.py`, `tests/test_version.py`.
  - Verify every pin (runtime, dev and `[notebook]`) with `pip index versions`.
  - AUTO: `pip install -e .[dev]` in a fresh venv; `pytest -q` passes; `ukstt --version` prints `0.1.0`; `python -m ukstt --version` works; `git check-ignore .env .env.local` succeeds and `.env.sample` is not ignored.
- **S1 Normalise and score.** `numwords`, `normalise`, `score`, `normalise.csv`. AUTO: `test_normalise`, `test_numwords`, `test_score` pass.
- **S2 Stats.** AUTO: `test_stats` passes.
- **S3 Manifests, dummy data and select.** AUTO: `ukstt make-dummy-data --out dummy`; `ukstt build-manifest --in dummy/manifests/clips_in.csv --out dummy/manifests/clips.csv --report dummy/manifests/validation_report.csv` exits 0; `ukstt select --clips dummy/manifests/clips.csv --stage pilot` returns the pilot clips under 10.0 min; `test_manifest` passes.
- **S4 Fake and runner.** AUTO: `test_fake` and `test_runner` pass; `ukstt transcribe --clips dummy/manifests/pilot.csv --run-id dummy-pilot-001` gives one `ok` row per pilot clip, and a second invocation sends nothing (all `skipped`).
- **S5 End to end on dummy.** `aggregate.py`, CLI score and stats. AUTO: `test_e2e_dummy` passes; `results/dummy-pilot-001/` has all five CSVs; with 2 speakers per region every pilot `low_n` is `true` and CIs are empty.
- **S5b Notebook.** `notebooks/results.ipynb`, built with `nbformat` and committed with outputs cleared. First cell sets `RUN_ID` (default `dummy-pilot-001`). Cells: (1) load `results/<RUN_ID>/*.csv` and `runs/<RUN_ID>/clips.csv` with pandas; (2) bar chart of WER by region, one panel per `task`, `ci_lo`/`ci_hi` error bars where present, bars hatched when `low_n`; (3) stacked substitution/deletion/insertion rates per region; (4) strip plot of speaker WER per region; (5) top error pairs per region as a table; (6) a clip browser: for each clip in `runs/<RUN_ID>/clips.csv` show `IPython.display.Audio(audio_path)`, the reference, and the hypothesis (`runs/<RUN_ID>/raw/<clip_id>.json["text"]`) side by side with differing words highlighted. Demo clips appear in (6) even without a reference. AUTO: `jupyter nbconvert --to notebook --execute notebooks/results.ipynb` succeeds on the dummy run. MANUAL: you open it and the charts and players look right.
- **S6 ElevenLabs and gate.** AUTO: `test_elevenlabs` passes; `ukstt transcribe --backend elevenlabs --clips dummy/manifests/smoke.csv --run-id x` with no `--max-audio-minutes` exits 2 with zero network calls.
- **S7 Real smoke (attended; key in `.env.local`).** MANUAL/AUTO: HTTP 200; `raw/*.json` has `text` and `words[]`; the log status is `ok`. If 401/402/403: stop and report that the key is rejected or the free key cannot call STT. No retry loop.
- **S8 Real pilot, then demo only if `manifests/demo_in.csv` exists (the dataset clips are already in `data/audio/`; the demo set is optional, so skip it silently when absent).**
  - AUTO: every pilot clip `ok` (or `skipped` on a resume); `score` and `stats` write all five CSVs; every row has `low_n=true` unless a region has >=5 speakers. Demo clips are scored as `no_reference` unless you supplied transcripts.
  - MANUAL: open the notebook on `pilot-real-001` and `demo-real-001`; listen to 3 clips and check the alignments; southern WER above 0.25 means investigate (soft).
- **S9 Approval gate for the full study.** No code. Give the user the pilot tables, the §9 numbers and a per-region speaker and minutes estimate. Proceed only on an explicit yes, on a paid plan.

### Batch 1 review rulings (R1–R9, decided after the first reviewer and tester pass; they override the text above)

- **R1 (`stats.bootstrap_ci`).** Drop speakers with `n_ref == 0` before the `MIN_SPEAKERS_CI` check; raise `ValueError` for any speaker with `n_ref < 0` or `errors < 0`. Sort speakers by `speaker_id` before resampling so the input order cannot change the interval. Add a test with zero-word speakers.
- **R2 (`normalise.load_normalise_csv`).** Open with `utf-8-sig`. Raise `ValueError` (message names the file and line) for: header not exactly `from,to,class`; no data rows; a row with the wrong number of columns; an unknown class; a `from` that is not already in normalised single-token form (`normalise(from, {}, frozenset())` must equal `[from]`); a duplicate `from`; a `to` whose tokens are not clean (must survive normalise unchanged), are a filler, or are themselves a `from` key (no chains or loops). Tests for each.
- **R3 (`config.load_config`).** Range checks: `max_retries >= 0`, `default_workers >= 1`, `connect_timeout_s` and `read_timeout_s` finite and > 0, `credits`-style keys are gone (P12), seed 0..2147483647. Prefix every `ValueError` with the config path.
- **R4 (`numwords._NUMBER`).** A number must not touch a letter, digit or `.`-joined digit on either side, and `_` counts as a separator: use `(?<![^\W_])` before and `(?![^\W_])` after (no `(?<![0-9]\.)` lookbehind: `3.5.2` stays `three point five.two`). A number with a leading zero and decimals (`01.8`) speaks its decimals (`01 point eight`) so that a second pass changes nothing. Known, accepted idempotence gaps: a decimal followed by an ordinal suffix (`6.6nd`) and a ten-digit-plus number with decimals; they never occur in read sentences. Cap digit strings at 9 digits (longer runs are left untouched, no `int()` on them). Give `_PERCENT` a `(?<![0-9,.])` lookbehind so it is not quadratic. After `.lower()` apply NFKC again. Add the tester's counterexamples (`.5`, `0_1`, `1_000`, `x.5`, `"1"*4301`, `İstanbul`) as tests, and a seeded fuzz test of the idempotence property over digits, `.`, `_`, letters and spaces.
- **R5 (`numbers.py` renamed).** The module is `ukstt/numwords.py` and its tests `tests/test_numwords.py`.
- **R6 (packaging).** `pyproject.toml` has a `[build-system]` table (setuptools), the `[notebook]` extras are pinned to versions verified with `pip index versions` (the reviewer found `pandas==3.1.0`, `matplotlib==3.11.2`, `jupyter==1.1.1`, `nbformat==5.11.1`; re-verify), and the `pythonpath = ["src"]` pytest setting is removed once the package is installed editable in `.venv`.
- **R7 (cli).** Delete the stub `add_subcommands` and the unused `common` parent until S3 adds the first subcommand. Export `DEFAULT_CONFIG` from `config.py` once.
- **R8 (tests).** Add `test_shipped_tables_agree_with_constants` (`regions.csv` ids equal `PILOT_REGIONS` in order; the single baseline row is `BASELINE`; `fake.toml` keys equal `PILOT_REGIONS + ("unknown",)`). Add the guard check to `conftest.py` and use `pytest.raises(SystemExit)` in `test_version.py`.
- **R9 (known limitations, record in methodology.md, not code).** Years are read as cardinals (`1930` → "one thousand nine hundred and thirty"), `re-mastered` splits into two tokens, `£2.5m` and `£2.5 million` are not handled, and `&` is dropped.

S1–S5b need no audio and no key. S7 and S8 need the dataset clips (already fetched) and your key in `.env.local`.

## Appendix: pilot dataset notes (VERIFIED 2026-11-03)

- **Source:** `ylacombe/english_dialects` on Hugging Face, a copy of OpenSLR SLR83 (Google). License `cc-by-sa-4.0` (HF tags and card). Attribution and share-alike apply if clips are redistributed. 17,877 rows, 8.98 GB in total; we use the datasets-server rows API for a few clips, not the full download.
- **Fields:** `line_id`, `audio`, `text`, `speaker_id` (int). Transcripts are capitalised, with no punctuation, and numbers are mostly spelled out; 3 of the 36 fetched references contain digits (checked 2026-11-03). Read sentences only.
- **Subsets (config names):** `irish_male` 450 rows, `midlands_female` 246, `midlands_male` 450, `northern_female` 750, `northern_male` 2,097, `scottish_female` 894, `scottish_male` 1,649, `southern_female` 4,161, `southern_male` 4,331, `welsh_female` 1,199, `welsh_male` 1,650. There is no `irish_female`.
- **Speaker IDs repeat across subsets** (for example 2484, 3397 and 4310 appear in Irish, Midlands, Northern, Scottish and Welsh; 12484 in both Welsh subsets). These are almost certainly different people: the number is only unique within a subset. The importer keys a speaker as `<region>_<speaker_id>` (e.g. `scottish_4310`) so nothing collides. Because the pilot uses male subsets only, the key is unique per speaker. A female subset sharing an ID with a male one would need a gender in the key; not needed now.
- **Audio:** WAV, 48 kHz, mono, 16-bit (the 36 fetched clips). Passes the PCM16 mono >=16 kHz rule with no conversion.
- **Fetched sample (`scripts/fetch_english_dialects_samples.py`):** male subsets, 2 speakers per label (most-seen in 8 sampled windows), up to 3 clips each of at most 12 s: 36 clips, 192 s (3.2 min), 6 clips and about 32 s per label. The script writes `data/audio/<clip_id>.wav`, `references/<clip_id>.txt` and `manifests/clips_in.csv`, with `clip_id = <region>_<speaker_id>_<line_id lowercase>`. It retries on HTTP 429 and 5xx (the server rate-limits).
- **Known limits:** read speech only, so no spontaneous stratum; dialect labels are self-identified and coarse; a handful of speakers per label in the sample; sentences were chosen to elicit accent differences (place names, airlines, personal names), which may be harder than ordinary speech; the dataset is public and may be in the model's training data.

## Batch 2 review fixes (S3), decided 2026-11-04
- **R10 (user errors never leak a traceback).** Every `cmd_*` catches `(OSError, ValueError, csv.Error, KeyError)` and prints `error: ...` to stderr with exit 2. `select_stage` checks that `clips.csv` has the columns `clip_id,set,region,duration_s` (ValueError otherwise) and computes the cap minutes BEFORE writing any file. `build_manifest` checks that `regions.csv` has `region_id`. `make_dummy_data` requires finite `seconds > 0`.
- **R11 (truncated WAV).** `probe_wav` raises `ValueError` ("truncated") if `file_size < n_frames * sampwidth * channels`, so a header lying about its length is `E_AUDIO_FORMAT`.
- **R12 (empty input).** `build-manifest` exits 2 if an input CSV has no header columns or no data rows in total (all inputs together), and never overwrites `clips.csv` in that case.
- **R13 (stale output).** When `build-manifest` finds errors it deletes an existing `--out` file so `select` cannot use stale data.
- **R14 (demo warning).** `W_SINGLE_CLIP_SPEAKER` is not raised for `set=demo` clips (each demo clip is its own speaker by design).
- **R15 (small helpers).** One `total_minutes(rows)` in `manifest.py` replaces the three copies. The `build-manifest` summary does not count `unknown` as a region.
- **R16 (tests).** Add the two missing tests: the default `--in` list (with and without `manifests/demo_in.csv`, using `monkeypatch.chdir(tmp_path)`) and the `set == "pilot"` filter in `select_stage` (a southern demo clip whose id sorts first must not appear in `pilot` or `smoke`). Add tests for R10-R14. Make the suite faster: build the default dummy set once per session (session-scoped fixture, copied or read-only) or use short `seconds` in tests; target under 4 s.
- **R17 (accepted, not coded).** The same `speaker_id` under two regions is not detected: ids are opaque, and the fetch script already writes region-prefixed ids (`scottish_4310`). Non-UTF-8 reference bytes are decoded with replacement. `clips.csv` paths are cwd-relative (run from the repo root). Tests need the repo root as cwd.
- Plan text fix: `E_REF_MISSING` applies to a non-empty `reference_path` whose file does not exist for both sets; an empty `reference_path` is an error for pilot only. With `--strict`, warnings are promoted to errors, so `clips.csv` is not written.

## Batch 3 review fixes (S4, S6), decided 2026-11-04
- **R18 (Ctrl-C stops spending).** On `KeyboardInterrupt` (or any BaseException in the pool loop) set `stop`, call `pool.shutdown(wait=True, cancel_futures=True)`, re-raise. Queued clips are not sent.
- **R19 (`Retry-After`).** Accept the header only if it parses to a finite float `>= 0`; use `min(value, 60)`. Anything else (garbage, HTTP-date, negative, nan, inf) is ignored and the normal backoff applies. The cap lives in `call_with_retry` so both backends and the fake `429` token obey it.
- **R20 (missing audio never half-runs).** Before any send, every clip to be sent must have an existing audio file, else exit 2 `error: audio file not found: <path>`. `work()` also treats `OSError` as a clip failure (status `failed`, exit 4) and the raw JSON is written with `ensure_ascii=True` so a lone surrogate cannot crash the write.
- **R21 (gate hardening).** Refuse (exit 2) if `transcriber.name != opts.backend`; `--max-audio-minutes` must be finite and `> 0`. Test: resume a fake run with `--backend elevenlabs` and a cap exits 2 with zero HTTP calls.
- **R22 (small).** `RUN_ID_RE` is applied with `fullmatch`. `requests.post(..., allow_redirects=False)` (a 3xx is an `HttpError`). The error body stored in the log has the API key replaced by `***`. The log header is written when the file is missing or empty. Delete the `__repr__` override and the redundant `startswith("#")` test in `load_api_key`; reword the "Nothing was sent" docstring (a connection reset after upload may be retried and billed twice; accepted). Test that `Retry-After` is honoured (the sleep value is asserted) and that `inf` and `1e9` are capped/ignored.
- **R23 (accepted, not coded).** Corrupt-but-existing raw JSON counts as done on resume (use `--force`); no lock against two simultaneous runs of the same run id; clip ids are trusted from `build-manifest`; a partial log line after SIGKILL is tolerated; default workers stays 4 (the free-tier concurrency limit is unverified; if 429s appear, use `--workers 2`).
- **Note for S5.** A real response's `words[]` also holds `type: "spacing"` (and `audio_event`) items. Score from `raw["text"]` only; the fake returns word items only.

## Batch 4 review fixes (S5, S5b), decided 2026-11-04
- **R24 (score input checks).** `score_run` raises `ValueError(f"{clip_id}: bad raw file {path}: ...")` (exit 2 via main) when a raw JSON is corrupt, is not an object, or has no string `text`; and `ValueError("duplicate clip_id ...")` for duplicates in the clips file. `stats` before `score` says `error: run score first (no utterance_scores.csv in <dir>)`.
- **R25 (score side effects).** `cmd_score` writes the new normalise hash (`--accept-normalise-change`) only AFTER `score_run` succeeds, and deletes any old `region_summary.csv` and `pairwise_vs_baseline.csv` in the output dir before scoring (they belong to the previous scoring; run `stats` again). `--run-id` must match the runner's `RUN_ID_RE` (fullmatch) in `score` and `stats`.
- **R26 (ordering).** `speaker_scores.csv` and `error_pairs.csv` list regions in `PILOT_REGIONS` order like `region_summary.csv` (then any other value alphabetically).
- **R27 (tests).** The speaker micro-average test must be able to fail on mean-of-clips (clips with different WERs inside one speaker: e.g. 3/6 and 1/4, micro 0.4, mean 0.375). Add an assertion that a region's CI equals `bootstrap_ci(speakers, "read|<region>")` so the seed key is pinned.
- **R28 (notebook).** Do not `fillna(0)` the error bars (low_n bars have none); drop the unused `pairwise` load; the clip browser shows a text note instead of crashing when an audio file is missing, and says that the words shown are normalised.
- Accepted, not coded: a clip whose log's latest row failed but whose raw file exists is scored from the raw file; `score` and `stats` need the repo root as cwd; an empty clips file scores 0 clips.

## Larger runs inside the free tier (R29), decided 2026-11-05
- **R29a (`select --cap-minutes X`).** Optional, pilot stage only (other stages: exit 2); must be finite and `> 0`. It replaces `PILOT_CAP_MIN` (10) for that call; the default is unchanged. The refusal message for the default cap ends `; raise it with --cap-minutes X`.
- **R29b (`to send` line).** After the gate passes and before the first request, `transcribe` prints `to send: N clips, M.MM min (about C credits at 330 credits/min, unverified; check the dashboard)` for the real backend and `to send (fake): N clips, M.MM min` for the fake one. N and M count the clips that will actually be sent (finished raw files are skipped unless `--force`). `CREDITS_PER_MIN = 330` in `constants.py` is used for this message only: no ledger, no enforcement, the cap is still `--max-audio-minutes`.
- **R29c (fetch script).** `scripts/fetch_english_dialects_samples.py` gains `--list` (rows, speakers, rows per speaker per config; whole subset scanned in pages of 100, cached in `data/hf_speakers.json`, no audio), `--speakers N` (at most N per label, most rows first, ties by id), `--clips-per-label N` (round-robin over those speakers; stderr warning when a label cannot reach N) alongside the old per-speaker `--clips`, `--genders male|female|both` (default male), `--out CSV` (default `manifests/clips_in.csv`), `--exclude-from CSV` (repeatable). A config (`<label>_<gender>`) is one label. Female speaker key is `f<number>` (`midlands_f3397`), male keys are unchanged, so existing ids still hold. Clips are taken in dataset order within a speaker (the 36 existing clips came from 8 sampled windows, so a re-run may pick other clips). Existing WAVs are not downloaded again; each WAV is checked (PCM16 mono >= 16 kHz).
- **R29d (tests).** `tests/test_fetch_script.py` loads the script with `importlib` and replaces its `get` function (no network): allocation, caps and warnings, `--exclude-from`, female keys, the cache, and a manifest that passes `ukstt build-manifest`. Further tests for `--cap-minutes` (`test_cli.py`) and the `to send` line (`test_runner.py`). 414 tests.
