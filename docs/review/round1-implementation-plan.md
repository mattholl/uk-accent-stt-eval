# Implementation plan: uk-accent-stt-eval

Status: draft for coder. Tags: **DECIDED** = user decision, **VERIFIED** = checked fact, **PROPOSED** = plan author's choice, changeable. Package name `ukstt`. Python `>=3.11` (`tomllib`). The sandbox has 3.14.9; other versions are untested.

## 1. Decision table

| # | Topic | Value | Tag |
|---|---|---|---|
| D1 | Baseline | Standard Southern British English (`ssbe`) | DECIDED |
| D2 | Regions | ssbe, scouse, geordie, welsh, lancashire, yorkshire, scottish, ni (Northern Ireland), irish (Republic) | DECIDED |
| D3 | Speech type | Read and spontaneous, analysed as separate strata | DECIDED |
| D4 | Ethics/consent | No sign-off. Pseudonymous speaker IDs are kept anyway. | DECIDED |
| D5 | Language | `language_code=eng` fixed. No auto-detect, no language-ID metrics. | DECIDED |
| D6 | Output | Internal report: CSV tables only, no plots or prose | DECIDED |
| D7 | API key | Free ElevenLabs key only: 10,000 credits/month, about 330 credits per audio minute | DECIDED |
| D8 | Dev approach | Default backend is `fake`. The real API is gated. | DECIDED (develop against a dummy API) |
| V1 | SLR83 | CC BY-SA 4.0, read speech only, labels Irish/Midlands/Northern/Scottish/Southern/Welsh (self-identified) | VERIFIED |
| V2 | SLR83 limits | No Scouse/Geordie/Lancs/Yorks/NI labels. "Southern" is not SSBE. "Northern" is never pooled into fine regions. | VERIFIED |
| P1 | Real-API budget | Smoke 1 min (reuses a pilot clip, so it costs 0 extra), pilot 18 min, SLR83 spot 2 min, reserve. See §9 for credit arithmetic. | PROPOSED |
| P2 | Pilot design | 9 regions x 2 speakers x (40 s read + 20 s spont) = 18.0 min. Validates the pipeline only, not regional claims. | PROPOSED |
| P3 | Full study | About 10 speakers/region, about 7.5 h. Needs a paid plan and explicit user approval. Not built or run in v1. | PROPOSED |
| P4 | Who records | UNANSWERED. The drop-folder contract (§5) works for any recorder. | PROPOSED |
| P5 | Scribe params | `model_id=scribe_v2`, `language_code=eng`, `tag_audio_events=false`, `timestamps_granularity=word`, `diarize=false`, `no_verbatim=false`, `seed=20261102`, `temperature` unset, `file_format=other`, no keyterms or other surcharged options | PROPOSED |
| P6 | Fillers | Kept in the verbatim transcript, stripped from both sides by a fixed list (`config/fillers.txt`). It is frozen before any real result is scored (§7). | PROPOSED |
| P7 | Audio | No resampling in the package. Input must be PCM16 mono WAV >=16 kHz. This replaces methodology's "derive 16 kHz copy". | PROPOSED |
| P8 | Stats | Speaker-level bootstrap B=10000, seed 20261102; permutation test; Holm | PROPOSED |
| P9 | Dependencies | stdlib for math, WAV and CSV. No numpy/scipy. | PROPOSED |
| P10 | Register contractions | `gonna/wanna/gotta/kinda/sorta/cos` are mapped to long forms on both sides. Dialect words are never mapped. | PROPOSED |

## 2. Region taxonomy and dataset-label mapping

`config/regions.csv`. Columns: `region_id,display_name,country,grew_up_area,slr83_label,is_baseline`.

| region_id | display_name | country | grew_up_area (own-data eligibility) | slr83_label | is_baseline |
|---|---|---|---|---|---|
| ssbe | Standard Southern British | England | South-East England, self-described RP/SSBE | (none) | true |
| scouse | Scouse | England | Liverpool/Merseyside | (none) | false |
| geordie | Geordie | England | Tyneside (Newcastle/Gateshead) | (none) | false |
| welsh | Welsh English | Wales | Wales; English-first speakers | Welsh English | false |
| lancashire | Lancashire | England | Lancashire (not Merseyside or Greater Manchester) | (none) | false |
| yorkshire | Yorkshire | England | Yorkshire | (none) | false |
| scottish | Scottish English | Scotland | Scotland; record the town | Scottish English | false |
| ni | Northern Irish | Northern Ireland | the six counties | (none) | false |
| irish | Irish English | Ireland | Republic of Ireland | Irish English | false |

SLR83-only groups. They are not in `regions.csv` and are written to the clip manifest as `region` = `slr83_midlands`, `slr83_northern` and `slr83_southern`, with `region_scope=coarse`:
- Midlands English → `slr83_midlands`.
- Northern English → `slr83_northern`. It is never pooled into lancashire, yorkshire or geordie.
- Southern English → `slr83_southern`. It is never used as the baseline.

Rules:
- The mapped SLR83 labels Welsh, Scottish and Irish become `welsh`, `scottish` and `irish` with `region_scope=fine`. Labels are self-identified, so they are only approximately those regions.
- `source` (`own` | `slr83`) is always a grouping key. Own and SLR83 results are never pooled in hypothesis tests. SLR83 gets descriptive WER with CIs and no baseline tests, because it has no SSBE group.
- SLR83 Irish is male only. SLR83 spot-check clips are therefore male only for every label (controls gender).

## 3. Repository layout

```
uk-accent-stt-eval/
  pyproject.toml            # name=ukstt, console script ukstt=ukstt.cli:main
  requirements.txt  requirements-dev.txt  .env.example (ELEVENLABS_API_KEY=***
  .gitignore                # .env* (except .env.example), cache/, runs/, ledger/, data/raw/, recordings/**/*.wav, results/
  config/
    study.toml  regions.csv  fillers.txt  equivalences.csv  spelling_us_uk.csv  fake.toml
  references/read/<passage_id>.txt       references/spont/<speaker_id>.txt
  recordings/speakers.csv                recordings/<speaker_id>/<clip_id>.wav
  manifests/                             # clips.csv, validation_report.csv, smoke.csv, pilot.csv, spot.csv, full.csv
  data/raw/slr83/                        # line_index_all.csv + zips (gitignored)
  data/slr83/{speakers.csv,clips/<clip_id>.wav,references/<speaker_id>.txt}
  cache/<backend>/<key[:2]>/<key>.json
  ledger/ledger.csv                      # real-API bookings only
  runs/<run_id>/{run_manifest.json,transcribe_log.csv,raw/<clip_id>.json}
  results/<run_id>/*.csv
  src/ukstt/
    __init__.py (__version__="0.1.0")  constants.py  config.py  csvio.py  audio.py
    manifest.py  dummy.py  slr83.py
    numbers.py  normalise.py  score.py  stats.py  aggregate.py
    transcribe/{__init__.py,base.py,fake.py,elevenlabs.py,cache.py,ledger.py,runner.py}
    cli.py
  tests/  (see §12)
```

### Signatures (all Python 3.11, type-annotated)

```python
# constants.py
SEED: int = 20261102; B: int = 10_000; BASELINE: str = "ssbe"
CREDITS_PER_MIN: int = 330; LEDGER_FACTOR: float = 1.05; MAX_WORKERS: int = 8
ID_RE = r"^[a-z0-9][a-z0-9_]{1,47}$"   # ids must not contain "__"

# config.py
@dataclass(frozen=True)
class StudyConfig: model_id:str; params:dict[str,object]; monthly_credit_cap:int; credits_per_min:int
    ledger_factor:float; ledger_period_start:str; max_retries:int; connect_timeout_s:float; read_timeout_s:float
    default_workers:int; fake_config_path:str
def load_config(path: Path = Path("config/study.toml")) -> StudyConfig: ...

# csvio.py  (UTF-8, LF, csv module, newline='')
def read_csv(path: Path) -> list[dict[str, str]]: ...
def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None: ...  # atomic tmp+os.replace
def fmt_float(x: float | None) -> str: ...   # '' for None/NaN else f"{x:.6f}"

# audio.py
@dataclass(frozen=True)
class WavInfo: sample_rate_hz:int; channels:int; sampwidth_bytes:int; n_frames:int; duration_s:float
def probe_wav(path: Path) -> WavInfo: ...            # wave.Error -> ValueError
def sha256_file(path: Path) -> str: ...
def concat_wavs(paths: Sequence[Path], out: Path, gap_s: float = 0.3) -> float: ...  # same params required, returns duration
def write_test_wav(path: Path, seconds: float, sample_rate_hz: int = 16000, seed: int = 0) -> None: ...  # low-amplitude noise

# manifest.py
@dataclass(frozen=True)
class Issue: level:str; code:str; path:str; message:str      # level in error|warning
def load_regions(path: Path) -> dict[str, dict[str, str]]: ...
def build_manifest(recordings_dir:Path, speakers_csv:Path, references_dir:Path, out_csv:Path,
                   report_csv:Path, regions_csv:Path, strict:bool=False) -> list[Issue]: ...
def select_stage(clips_csv:Path, stage:str, out_csv:Path, config:StudyConfig) -> list[dict[str,str]]: ...  # stage in smoke|pilot|spot|full

# dummy.py
def make_dummy_data(out_dir:Path, seed:int=SEED, speakers_per_region:int=2) -> None: ...  # WAVs, speakers.csv, references

# slr83.py
@dataclass(frozen=True)
class LineRow: line_id:str; file_id:str; transcription:str
def parse_line_index(text:str) -> tuple[list[LineRow], list[str]]: ...   # rows, malformed lines; split(', ', 2)
def speaker_of(file_id:str) -> str: ...      # '_'.join(file_id.split('_')[:2])  (UNCONFIRMED, see §13)
def build_spot_clips(raw_dir:Path, out_dir:Path, labels:Sequence[str], target_s:float=20.0) -> list[dict[str,str]]: ...

# numbers.py
def int_to_words(n:int) -> str: ...           # british: "one hundred and five"
def expand_numbers(text:str) -> str: ...      # rule 4

# normalise.py
def normalise(text:str, *, fillers:frozenset[str], equivalences:Mapping[str,str], us_uk:Mapping[str,str]) -> list[str]: ...
def load_normaliser_resources(config_dir:Path=Path("config")) -> tuple[frozenset[str], dict[str,str], dict[str,str]]: ...
def normalise_default(text:str) -> list[str]: ...    # loads resources once (lru_cache)

# score.py
@dataclass(frozen=True)
class Alignment: n_ref:int; n_hyp:int; hits:int; subs:int; dels:int; ins:int
    ops:tuple[tuple[str,str|None,str|None],...]    # ('H'|'S'|'D'|'I', ref_word, hyp_word)
    @property
    def errors(self)->int: ...
    @property
    def wer(self)->float|None: ...                 # None iff n_ref==0
def align(ref:Sequence[str], hyp:Sequence[str]) -> Alignment: ...
def char_distance(ref:Sequence[str], hyp:Sequence[str]) -> tuple[int,int]: ...   # (edit distance, n_ref_chars) on " ".join
def extract_hypothesis(raw:Mapping[str,object]) -> tuple[str,str]: ...           # (text, hyp_source in 'words'|'text')

# stats.py
@dataclass(frozen=True)
class SpeakerCounts: speaker_id:str; errors:int; n_ref:int
def pooled_wer(sp:Sequence[SpeakerCounts]) -> float: ...
def bootstrap_ci(sp:Sequence[SpeakerCounts], key:str, B:int=B, seed:int=SEED) -> tuple[float,float]|None: ...
def bootstrap_diff_ci(a:Sequence[SpeakerCounts], b:Sequence[SpeakerCounts], key:str, B:int=B, seed:int=SEED) -> tuple[float,float]|None: ...
def permutation_test(a:Sequence[SpeakerCounts], b:Sequence[SpeakerCounts], key:str, B:int=B, seed:int=SEED, exact_max:int=50_000) -> tuple[float,str,int]: ...  # (p, 'exact'|'monte_carlo', n_perm)
def holm(pvals:Sequence[float]) -> list[float]: ...

# aggregate.py
def score_run(run_dir:Path, clips_csv:Path, out_dir:Path) -> None: ...        # utterance/speaker/error_pairs
def stats_run(out_dir:Path) -> None: ...                                     # region_summary, pairwise_vs_baseline

# transcribe/base.py
class Transcriber(Protocol):
    name: str
    def transcribe(self, audio_path:Path, params:Mapping[str,object]) -> dict: ...   # raw Scribe-shaped JSON
class TranscribeError(Exception): ...
class HttpError(TranscribeError): status:int; retry_after:float|None; body:str
class TimeoutError_(TranscribeError): ...        # request timed out (booked)
class MalformedResponse(TranscribeError): ...
class AuthOrQuotaError(HttpError): ...           # 401/402/403: abort whole run

# transcribe/fake.py
class FakeTranscriber:
    name = "fake"
    def __init__(self, references:Mapping[str,str], region_of:Mapping[str,str], error_rates:Mapping[str,float],
                 failures:Mapping[str,Sequence[str]]|None=None, seed:int=SEED) -> None: ...
        # references/region_of keyed by audio sha256; failures keyed by audio file stem, consumed one entry per attempt
        # entries: "429","500","503","timeout","empty","malformed"
    def transcribe(self, audio_path:Path, params:Mapping[str,object]) -> dict: ...
    @classmethod
    def from_clips(cls, clips_csv:Path, references_root:Path, fake_toml:Path) -> "FakeTranscriber": ...

# transcribe/elevenlabs.py
class ElevenLabsTranscriber:
    name = "elevenlabs"
    URL = "https://api.elevenlabs.io/v1/speech-to-text"
    def __init__(self, api_key:str, connect_timeout_s:float=10, read_timeout_s:float=120, session:requests.Session|None=None) -> None: ...
    def transcribe(self, audio_path:Path, params:Mapping[str,object]) -> dict: ...  # ONE POST, no retry here

# transcribe/cache.py
def cache_key(audio_sha256:str, params:Mapping[str,object]) -> str: ...  # sha256(audio_sha256+"\n"+json.dumps(params,sort_keys=True,separators=(",",":")))
class Cache:
    def __init__(self, root:Path, backend:str) -> None: ...
    def get(self, key:str) -> dict|None: ...
    def put(self, key:str, audio_sha256:str, params:Mapping[str,object], response:Mapping[str,object]) -> None: ...

# transcribe/ledger.py
def charge_credits(audio_seconds:float, cfg:StudyConfig) -> int: ...   # ceil(audio_seconds/60*330*1.05)
class Ledger:
    def __init__(self, path:Path, cfg:StudyConfig) -> None: ...
    def spent(self) -> int: ...
    def remaining(self) -> int: ...                       # cap - spent - in-flight reservations
    def reserve(self, credits:int) -> bool: ...           # thread-safe; False if insufficient
    def release(self, credits:int) -> None: ...
    def book(self, run_id:str, clip_id:str, cache_key:str, audio_seconds:float, credits:int, outcome:str, attempt:int) -> None: ...  # append+fsync

# transcribe/runner.py
@dataclass(frozen=True)
class RunOptions: run_id:str; backend:str; max_audio_minutes:float|None; workers:int; refresh:bool
def run_transcription(clips:Sequence[dict[str,str]], opts:RunOptions, cfg:StudyConfig, transcriber:Transcriber,
                      ledger:Ledger|None, cache:Cache, runs_root:Path, sleep:Callable[[float],None]=time.sleep) -> int: ...  # exit code
```

## 4. Pinned dependencies

`requirements.txt`: `requests==2.34.2`, `tenacity==9.2.1`, `python-dotenv==1.2.4`.
`requirements-dev.txt`: `-r requirements.txt`, `pytest==9.2.0`, `responses==0.26.3`, `jiwer==4.0.0` (cross-check tests only, skipped if absent).
The `pyproject.toml` runtime deps repeat the same pins. numpy and scipy are not used.

## 5. Data contract: works whoever records

**Drop folder** (the recorder only has to satisfy this):

```
recordings/speakers.csv
recordings/<speaker_id>/<speaker_id>__read__<passage_id>.wav
recordings/<speaker_id>/<speaker_id>__spont__spont.wav
references/read/<passage_id>.txt        # one per passage, shared by all speakers
references/spont/<speaker_id>.txt       # human transcript of that speaker's spontaneous clip
```

- Audio: PCM16 WAV, mono, >=16 kHz. Anything else is a validation **error**, and the message includes `ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav`.
- IDs match `ID_RE`. Own `speaker_id` convention: `<region_id>_<nn>` (e.g. `scouse_01`). `clip_id = <speaker_id>__<task>__<passage_id>` (double underscore separator).
- Pilot durations: read 40 s +/-5 s, spont 20 s +/-5 s. Out of range is a **warning**.
- PROPOSED read passage for the pilot: `comma_excerpt1`, the first about 100 words of "Comma Gets a Cure". Fallback: first paragraph of the Rainbow Passage. The licence of Comma is unchecked (§13). Spontaneous prompt: "describe your journey to work/school this morning", about 20 s.
- Reference style guide, written in `references/README.md`:
  - Write what was said, in words.
  - Spell numbers out. No digits.
  - Use standard spelling where a dictionary word exists. Otherwise use the conventional dialect spelling (`wee`, `nowt`, `aye`, `cannae`).
  - No brackets for speech. `[unclear]` and `[laughs]` are allowed and are stripped by rule 2.
  - Fillers are optional.
- Spontaneous references: transcribe from scratch (`ref_method=human_scratch`). If drafted from Scribe output (`human_corrected_from_scribe`), WER is biased low, and that is flagged in every results table.

**`recordings/speakers.csv`** (also `data/slr83/speakers.csv`):
`speaker_id,source,region,region_scope,town,age_band,gender,self_described_accent,lived_in_region_to_age,device,environment,ref_method,notes`
- `source` is `own` or `slr83`.
- `region_scope` is `fine` or `coarse`.
- `gender` is `f|m|nb|na`.
- `age_band` is `18-29|30-44|45-59|60+`.
- `ref_method` is `scripted|human_scratch|human_corrected_from_scribe`.
- For `own`, `region` must be in `regions.csv`.
- For own speakers, the speaker's grew-up area must satisfy `grew_up_area`, and `lived_in_region_to_age` should be >=16 (warning if lower).

**`manifests/clips.csv`** (built by `ukstt build-manifest`; every row has one reference):
`clip_id,speaker_id,source,region,region_scope,task,passage_id,audio_path,audio_sha256,duration_s,sample_rate_hz,channels,reference_path,ref_method,gender,age_band`
- `task` is `read` or `spont`.
- Paths are relative, POSIX, to the repo root.
- Stage files (`smoke|pilot|spot|full.csv`) have the same columns plus `stage`.

**`manifests/validation_report.csv`**: `level,code,path,message`. Error codes:
- `E_SPEAKER_UNKNOWN` (audio folder has no row in speakers.csv)
- `E_SPEAKER_NOAUDIO`
- `E_REGION_UNKNOWN`
- `E_AUDIO_FORMAT`
- `E_AUDIO_TOO_SHORT` (<0.1 s)
- `E_REF_MISSING`
- `E_REF_EMPTY_AFTER_NORM` (zero words after normalisation)
- `E_ID_BAD`
- `E_DUP_CLIP`
- `E_FILENAME_MISMATCH`

Warnings: `W_DURATION`, `W_LIVED_TO_AGE`, `W_REF_DIGITS`, `W_ONE_TASK_ONLY`.
`build-manifest` exits 2 if any error exists (or any warning under `--strict`). It writes the manifest only when there are no errors.

**Stage selection** (`select`, deterministic, sorted by `speaker_id`):
- `pilot`: own source only. Per `regions.csv` region, the first 2 speakers that have both a read and a spont clip. That is 36 clips. Error if any region has fewer than 2 speakers. Error if total duration > 18.0 min x 1.05.
- `smoke`: the first `ssbe` `read` clip of `pilot.csv` (about 40 s). It is a subset of the pilot, so the cache is reused.
- `spot`: SLR83 clips, 6 (one per label).
- `full`: all own clips. It refuses to run on the real backend unless the ledger covers it (it cannot on a free key).

**SLR83 clips** (`slr83 build`):
- `speaker_id=slr83_<wef_12484>`.
- `clip_id=slr83_<spk>__read__slr83_lines`.
- Source labels come from the zip name (male zips only).
- Speaker choice per label: sort by (-n_lines, speaker_id). Take the first speaker for whom adding whole lines in `line_id` order reaches 18–22 s. Lines are concatenated with 0.3 s gaps.
- `reference = " ".join(transcriptions)`.
- The WAV params of all lines must match, else error. There is no resampling.

## 6. Transcription behaviour (exact rules)

**Params** (`config/study.toml [params]`; sent as multipart form fields; booleans as `"true"`/`"false"`; `temperature` absent):
`model_id=scribe_v2, language_code=eng, tag_audio_events=false, timestamps_granularity=word, diarize=false, no_verbatim=false, seed=20261102, file_format=other`

**Real call.** One `requests.post(URL, headers={"xi-api-key": key}, data=params, files={"file": (name, fh, "audio/wav")}, timeout=(10, 120))`.
- Never log the key. The manifest and logs contain no secrets.
- The key is read from env `ELEVENLABS_API_KEY`, falling back to `.env.local` via python-dotenv. This happens only when the backend is elevenlabs.
- A missing key exits 2.
- Parse JSON.
- Raise `MalformedResponse` if the body is not JSON or has no `text` key.
- Status mapping:
  - 200 → ok.
  - 401/402/403 → `AuthOrQuotaError` (abort the run, book nothing).
  - 429/5xx → `HttpError` (retryable, not booked).
  - Other 4xx (400, 422) → `HttpError` (not retryable, not booked).

**Retries** (tenacity, wrapping the single-attempt call in `runner.py`):
- Retry on `HttpError` with status 429 or >=500, on `requests.ConnectionError`, and on `TimeoutError_`.
- `stop_after_attempt(1 + cfg.max_retries)` with `max_retries=3` for real (4 attempts total).
- `wait_exponential_jitter(initial=2, max=30)`.
- Honour `Retry-After` when present (use the larger).
- Sleep is injectable; tests pass `lambda s: None`.
- The fake backend uses the same wrapper.
- `MalformedResponse` is not retried (the call may have been charged). It is booked as outcome `malformed`, the clip is marked `failed`, and the response is not cached.

**Ledger** (real backend only; the fake never touches it):
- Charge = `ceil(audio_seconds/60 * 330 * 1.05)` credits.
- Booked when the response is 200, or when the outcome is a timeout (conservative), or when the response is malformed. Never booked for 429/5xx/4xx.
- Ledger cap = `monthly_credit_cap` (10000) counted from `ledger_period_start`.
- Each attempt: `reserve()` first. If it returns False, the clip gets status `skipped_budget` and is not sent.
- After the attempt: `book()` and `release()`.
- `ledger/ledger.csv` columns: `ts_utc,run_id,clip_id,cache_key,backend,attempt,audio_seconds,credits,outcome` (outcome is `ok|timeout|malformed`).

**Real gate** (checked before any network I/O; refuse with exit 2 or 3):
1. `--backend elevenlabs` is explicitly given (the default is fake).
2. `--max-audio-minutes N` is given.
3. Pre-flight: sum of `duration_s` over clips that are not cached and not already done must be <= N x 60.
4. Pre-flight: `charge_credits(that sum)` must be <= `ledger.remaining()`. If not, exit 3 and print needed vs remaining.
5. API key present.
6. `--workers` is clamped to `min(workers, 8)` (the 8-concurrency free-tier limit). Real default is 4.

**Run state and resume.**
- `runs/<run_id>/run_manifest.json` keys:
  `run_id, created_utc, backend, model_id, params, package_version, python_version, pins, git_commit, seed, clips_file, clips_file_sha256, max_audio_minutes, n_clips, ledger_remaining_at_start`.
- Re-running an existing `run_id` resumes. It aborts with exit 2 if `params` or `clips_file_sha256` differ (use a new `run_id`).
- `transcribe_log.csv` is append-only. Columns: `ts_utc,clip_id,cache_key,backend,status,attempts,http_status,latency_s,audio_seconds,credits,error`. `status` is `ok|cached|failed|skipped_budget`.
- The last row per `clip_id` is the state. A clip is done if its raw file exists and its last status is `ok` or `cached`.
- `raw/<clip_id>.json` holds the API response verbatim (`json.dump` with `ensure_ascii=False`). It is written atomically.
- Cache files wrap `{cache_key, backend, audio_sha256, params, created_utc, response}`. The cache is split by backend, so fake output never serves a real request.
- `--refresh` skips the cache read (for variance repeats) and overwrites the cache entry.
- Workers use `ThreadPoolExecutor`. The log and ledger are lock-protected. Final outputs are ordered by `clip_id`.
- Exit codes: 0 ok; 2 usage/gate/validation; 3 budget; 4 some clips failed (resume to retry); 5 `AuthOrQuotaError` abort. On exit 5 the run stops cleanly, in-flight clips finish, and nothing further is submitted.

**FakeTranscriber output.**
- Scribe-shaped: `{"language_code":"eng","language_probability":1.0,"text":..., "words":[{"text","start","end","type"}...],"transcription_id":"fake-<key12>"}`.
- `words[]` alternates `word` and `spacing` items. `audio_event` items appear only if `tag_audio_events` is true.
- The hypothesis is the reference with a per-word error draw at `error_rates[region]`. The draw is substitute, delete or insert (one third each), from `random.Random(f"{seed}:{audio_sha256}")`.
- Text is capitalised and punctuated, so normalisation is exercised.
- `config/fake.toml`: `[error_rates]` with per-region rates, e.g. ssbe 0.03, scouse 0.12, geordie 0.12, welsh 0.08, lancashire 0.08, yorkshire 0.08, scottish 0.14, ni 0.10, irish 0.07.
- Failure injection per `failures` (list per file stem, consumed per attempt):
  - `429`: raise `HttpError(429, retry_after=1)`.
  - `500` and `503`: raise `HttpError`.
  - `timeout`: raise `TimeoutError_`.
  - `empty`: return `{"text":"","words":[],"language_code":"eng","language_probability":1.0}`.
  - `malformed`: return `{"oops":1}`, which the runner turns into `MalformedResponse` via validation.

## 7. Normalisation (11 ordered rules, applied to reference AND hypothesis)

`normalise(text) -> list[str]`. The order is fixed:
1. Unicode NFKC. Curly quotes `’‘` → `'`, `“”` → `"`. En and em dashes, NBSP and zero-width characters → space.
2. Remove bracketed spans: `\[[^\]]*\]`, `\([^)]*\)`, `<[^>]*>` (covers annotations and audio events). Replace with a space.
3. Lowercase (`str.lower()`).
4. `expand_numbers`:
   - `£n` → `n pounds`, `n%` → `n per cent`.
   - Remove thousands commas (`1,000` → `1000`).
   - Decimals `3.5` → `three point five`.
   - Ordinals `1st..31st` → words via a table.
   - Integers 0..999,999,999 → British words with "and" (`105` → `one hundred and five`).
   - A 4-digit integer in 1100–1999 or 2010–2099 is read as year pairs (`1984` → `nineteen eighty four`). 2000–2009 are read as cardinals.
   - Anything else is left as-is.
5. Replace `-`, `_` and `/` with a space.
6. Strip punctuation. Keep only Unicode letters, digits, whitespace and apostrophes that sit between two letters. All other characters are removed.
7. Split on whitespace into tokens.
8. Equivalences from `config/equivalences.csv` (columns `from,to,class`). Applied to tokens, with the output re-split into tokens.
   - `register`: `gonna → going to`, `wanna → want to`, `gotta → got to`, `kinda → kind of`, `sorta → sort of`, `cos → because`, `'cause → because`.
   - `orthography`: `ok → okay`, `alright → all right`, `percent → per cent`.
   - Dialect words are never added (wee, nowt, aye, ye, youse, cannae, dinnae, yous, etc.).
9. US→UK spelling map from `config/spelling_us_uk.csv` (columns `us,uk`), a closed list (color→colour, etc.).
10. Drop tokens in `config/fillers.txt`: `um umm uh uhm er erm hm hmm mm mmm mhm`. Not included, because they are dialect or content words: `ah` (Scots "I"), `eh`, `aye`, `like`, `you know`, `yeah`. The list and the equivalences file are frozen (git tag `norm-frozen`) before any real transcripts are scored.
11. Drop empty tokens and return the list.

Hypothesis extraction (`extract_hypothesis`):
- Use the words in `words[]` where `type=="word"`, joined by a space. `hyp_source="words"`.
- If `words` is missing or empty and `text` is non-empty, use `text`. `hyp_source="text"`.
- Then normalise.

## 8. Scoring and edge-case rules

- **Alignment.** Levenshtein DP with unit costs, reference tokens on rows. Backtrace from `(n,m)` with fixed priority at each cell:
  1. match, if `ref[i-1]==hyp[j-1]` and `d[i][j]==d[i-1][j-1]`;
  2. substitution, if `d[i][j]==d[i-1][j-1]+1`;
  3. deletion, if `d[i][j]==d[i-1][j]+1`;
  4. else insertion.

  Ops are reversed after the walk. The S/D/I split is therefore deterministic.
- `WER = (S+D+I)/N` and is **never clipped** (insertions can push it above 1.0).
- **Empty hypothesis, N>0.** `D=N`, `WER=1.0`. The clip is counted.
- **Empty reference (N=0).**
  - `wer` is empty (NA).
  - For own data, `build-manifest` errors on `E_REF_EMPTY_AFTER_NORM`.
  - If it still reaches scoring, the clip is written to `utterance_scores.csv` with `status=ref_empty` and excluded from all aggregates.
  - A zero-word reference with an empty hypothesis is also NA and excluded.
- **CER.** Edit distance on `" ".join(tokens)` characters. `n_ref_chars=0` gives NA. It is not clipped.
- **Failed or missing clips.** `status=failed|missing|skipped_budget` rows are listed in `utterance_scores.csv`, are excluded from WER, and are counted as `n_excluded` in `region_summary.csv`. They are never silently dropped.
- **Aggregation.** Micro-average (sum errors / sum words), never the mean of per-utterance WERs. The speaker is the unit in all stats.
- **Error pairs.** Taken from alignment ops: `sub` (ref→hyp), `del` (ref→empty) and `ins` (empty→hyp). Sorted by `-count, ref_word, hyp_word`.
- **Diagnostics.** `n_digit_tokens_hyp` is counted in `utterance_scores.csv`. Unusual values hint at a numbers-handling issue.

## 9. Real-API budget arithmetic

The ledger charges `credits = ceil(sec/60 x 330 x 1.05)`, which is 346.5 per audio minute.

| Item | Audio | Credits |
|---|---|---|
| Cap (free plan) | 28.9 min usable | 10,000 |
| Smoke (a pilot clip; reused by the pilot, so 0 extra) | about 0.67 min | about 231 |
| Pilot (36 clips) | 18.0 min | 6,237 |
| SLR83 spot (6 x 20 s) | 2.0 min | 693 |
| Pilot + spot | 20.0 min | 6,930 |
| Reserve left | about 8.9 min | about 3,070 |

The user's "about 30 min" is raw billing. The 1.05 safety factor trims it to about 28.9 min. A full study of about 7.5 h is 148,500 raw credits and cannot run on a free key.

## 10. Statistics spec

- **Strata.** (source, task) with task in {read, spont}. A pooled "all" row is secondary and labelled so.
- **Unit.** Speaker. `SpeakerCounts(errors, n_ref)` is summed over the speaker's clips in the stratum, excluding NA clips.
- **Region WER.** `sum(errors)/sum(n_ref)` over speakers.
- **Bootstrap CI.**
  - `rng = random.Random(f"{SEED}:{key}")`, where `key` is a string such as `own|read|scouse`.
  - Draw `B=10000` resamples of the n speakers with replacement.
  - Compute the pooled WER of each resample and sort ascending.
  - `lo = reps[250]`, `hi = reps[9749]` (0-based).
  - CI is `None` (NA) when n_speakers < 2.
  - For all CIs, a resample whose total words is 0 cannot occur (speakers with n_ref=0 are excluded).
- **Difference CI.** Resample each group independently (`key` includes both region names) and take `WER_region - WER_ssbe` per replicate. Same index rule.
- **Permutation test** (two-sided, statistic `|diff of pooled WERs|`).
  - Pool the n1+n2 speakers and reassign group labels.
  - **Exact** if `C(n1+n2, n1) <= 50000`: enumerate with `itertools.combinations`; `p = #(|d| >= |obs| - 1e-12) / total` (the observed split is included).
  - Otherwise **Monte Carlo** with `B=10000` random relabellings and `p = (1 + #(|d| >= |obs| - 1e-12)) / (1 + B)`.
  - With 2 vs 2 speakers the minimum possible p is 2/6 = 0.333, so the pilot can never show significance.
- **Holm.** Per family = (source=own, task) with m = 8 comparisons (each non-baseline region vs ssbe). Sort the p-values ascending. `adj_(i) = min(1, (m - i + 1) x p_(i))` (1-based i), then take the running maximum, then restore the original order.
- **Flags.** `low_n=true` when n_speakers < 5 (every pilot region is flagged).
- **SLR83.** Descriptive WER and CI per label. No baseline tests (there is no SSBE group). Own vs SLR83 for the same region is shown side by side in the tables, not tested.
- **Gender and age.** Reported as counts per region in `region_summary.csv` (`n_f, n_m, n_other`). No adjustment is made.

## 11. CLI (exact commands; `python -m ukstt ...` is equivalent)

```
ukstt --version
ukstt make-dummy-data --out dummy --seed 20261102 [--speakers-per-region 2]
ukstt build-manifest --recordings recordings --speakers recordings/speakers.csv --references references \
      --regions config/regions.csv --out manifests/clips.csv --report manifests/validation_report.csv [--strict]
ukstt select --clips manifests/clips.csv --stage {smoke|pilot|spot|full} --out manifests/pilot.csv
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-fake-001 [--backend fake|elevenlabs] \
      [--max-audio-minutes N] [--workers N] [--refresh] [--fake-config config/fake.toml]
ukstt score --run-id pilot-fake-001 --clips manifests/pilot.csv [--out results/pilot-fake-001]
ukstt stats --run-id pilot-fake-001
ukstt ledger show                                  # spent, remaining credits and minutes, last 10 bookings
ukstt slr83 fetch --labels irish,midlands,northern,scottish,southern,welsh --yes   # optional helper; prints size first
ukstt slr83 inspect                                # speaker-ID rule check (see §13)
ukstt slr83 build --raw data/raw/slr83 --out data/slr83 --labels irish,midlands,northern,scottish,southern,welsh --target-s 20
```

Real runs:

```
ukstt transcribe --clips manifests/smoke.csv --run-id smoke-real-001 --backend elevenlabs --max-audio-minutes 1
ukstt transcribe --clips manifests/pilot.csv --run-id pilot-real-001 --backend elevenlabs --max-audio-minutes 18
ukstt transcribe --clips manifests/spot.csv  --run-id spot-real-001  --backend elevenlabs --max-audio-minutes 2
```

Output CSVs written to `results/<run_id>/` (floats via `fmt_float`, bools `true/false`, NA is an empty cell):
- `utterance_scores.csv`: `run_id,clip_id,speaker_id,source,region,task,status,n_ref,n_hyp,hits,subs,dels,ins,wer,n_ref_chars,char_dist,cer,hyp_source,language_code,language_probability,n_digit_tokens_hyp,ref_method`
- `speaker_scores.csv`: `source,region,task,speaker_id,gender,age_band,n_clips,n_ref,subs,dels,ins,errors,wer`
- `region_summary.csv`: `source,task,region,region_scope,n_speakers,n_clips,n_excluded,n_ref,subs,dels,ins,wer,ci_lo,ci_hi,sub_rate,del_rate,ins_rate,cer,low_n,n_f,n_m,n_other,B,seed`
- `pairwise_vs_baseline.csv`: `source,task,region,baseline,n_spk_region,n_spk_base,wer_region,wer_base,diff,diff_ci_lo,diff_ci_hi,p_perm,perm_method,n_perm,p_holm,family_size`
- `error_pairs.csv`: `source,task,region,type,ref_word,hyp_word,count,rank`
- `run_info.csv`: `key,value` (run_id, backend, params JSON, normaliser hash, config hashes).

## 12. Tests to write (pytest; no real network)

`tests/conftest.py`: an autouse fixture blocks `socket.socket.connect`, so a test that tries a real request fails. `responses` mocks HTTP; `tmp_path` is used for all I/O.

- **test_normalise.py**: one case per rule 1–10, then the full ordered pipeline.
  - `"Don’t—stop!"` → `["don't","stop"]`
  - `"It's £5, 1,000 and 3.5%"` → `its five pounds one thousand and three point five per cent`-style tokens, hand-written
  - `"Um, the colour (laughs) [unclear] well-known"` → `["the","colour","well","known"]`
  - `"gonna"` → `["going","to"]`; `"nowt"`/`"wee"`/`"aye"`/`"ah"` unchanged.
  - Year rule: 1984 → `nineteen eighty four`; 2005 → `two thousand and five`.
  - Idempotence: `normalise(" ".join(normalise(x))) == normalise(x)`.
- **test_numbers.py**: 0, 13, 21, 100, 105, 1001, 999999, 1,000,000.
- **test_score.py** (hand-computed):
  - `the cat sat` vs `the cat sat` → 0.
  - vs `the dog sat` → S=1, WER 1/3.
  - `the cat sat on the mat` vs `the cat sat` → D=3, WER 0.5.
  - `hello` vs `hello there you` → I=2, WER 2.0 (>1, unclipped).
  - `a b c` vs empty hypothesis → D=3, WER 1.0.
  - N=0 cases: empty/empty and empty/`x` → wer None, excluded from aggregates.
  - Tie-break: `a b` vs `b a` → S=2, D=0, I=0.
  - Tie-break: `a b c` vs `b c d` → D=1, I=1, S=0.
  - Property: total errors equal the edit distance, S+D+I=errors, H+S+D=N, H+S+I=n_hyp, over random sequences (seeded).
  - jiwer cross-check on 200 seeded random pairs: total distance and WER match (`pytest.importorskip("jiwer")`). The S/D/I split is not compared (tie-breaking differs).
  - CER hand case: `abc` vs `abd` → 1/3.
- **test_extract.py**: words type filter, `audio_event` ignored, fallback to `text` with bracket strip, empty response.
- **test_stats.py**:
  - Bootstrap on a single value (degenerate) → CI lo=hi.
  - n<2 → None.
  - Two speakers (1/10 and 3/10): all replicates lie in {0.1, 0.2, 0.3}; percentile indices are 250 and 9749 (assert via a spy list).
  - Determinism: same seed and key give the same CI. A different `key` gives a different draw sequence.
  - Permutation: A=(0/10,0/10), B=(5/10,5/10) → exact, p=2/6, n_perm=6.
  - A Monte Carlo case with n large (e.g. 12 vs 12) selects `monte_carlo` and p ≥ 1/(B+1).
  - Holm on [0.01,0.04,0.03] → [0.03,0.06,0.06]. Also an all-1.0 case and m=1.
- **test_manifest.py**: dummy data → build-manifest has 0 errors, 36 pilot clips, 18.0 min. Negative cases: wrong sample rate, stereo, missing reference, unknown region, duplicate clip, empty-after-norm ref, bad filename.
- **test_cache.py**: key stable across dict order; changes with params or audio; fake and elevenlabs cache dirs are separate.
- **test_fake.py**: determinism; every failure token produces the listed behaviour; error rate recovery.
- **test_runner.py** (fake backend, sleep stubbed):
  - 429→429→ok succeeds in 3 attempts.
  - 5xx x4 → status failed, exit 4.
  - Resume after a simulated crash (delete the last log row and raw file) completes only the missing clip.
  - Cache hit → status cached, no transcriber call.
  - Concurrency: 8 workers give the same outputs as 1 worker, and the `workers>8` clamp is applied.
  - Run-manifest mismatch on resume → exit 2.
  - `AuthOrQuotaError` → exit 5, no further submissions.
- **test_elevenlabs.py** (`responses`):
  - Multipart body carries all params (booleans lowercase), `xi-api-key` header present, `temperature` absent.
  - 200 books once. Timeout books and retries.
  - 429 then 200 books once, 429 never booked.
  - 401 → exit 5, nothing booked.
  - Malformed 200 → booked, not cached, not retried.
  - Gate refusals: no `--max-audio-minutes` → exit 2; missing key → exit 2; insufficient ledger → exit 3; zero HTTP calls in each case.
  - The key never appears in log or manifest output.
- **test_ledger.py**: `charge_credits(60)==347` (ceil of 346.5), thread-safe reserve with a 10-thread stress, restart persistence, period start filter.
- **test_slr83.py** (fixtures: a 3-line `line_index_all.csv`, tiny generated zips): `split(', ',2)` handles commas inside the transcription; malformed lines are reported; `speaker_of('wef_12484_0123')=='wef_12484'`; concatenation gap and duration; deterministic speaker choice.
- **test_e2e_dummy.py** (the S5 pipeline acceptance): the whole dummy pilot (18 speakers) through select → transcribe(fake) → score → stats. Assert outputs are byte-identical across two runs and the recovered region WERs are within 0.03 of the configured fake rates (pooled over a larger dummy set with 10 speakers/region).

## 13. Build order (pilot-first) with acceptance checks

- **S0 Scaffold.** Create pyproject, pins, `.gitignore` (including `.env*` rules), config skeletons and `ukstt --version`. *Accept:* `pip install -e .[dev]` in a fresh venv; `pytest -q` passes (collects 0 or placeholder tests); `ukstt --version` prints 0.1.0; `git check-ignore .env.local` succeeds.
- **S1 Normalise + score (pure).** `numbers.py`, `normalise.py`, `score.py`, resource files. *Accept:* `test_normalise`, `test_numbers`, `test_score`, `test_extract` pass, including the jiwer cross-check.
- **S2 Stats.** `stats.py`. *Accept:* `test_stats` passes with the hand-computed cases above (p=2/6, Holm [0.03,0.06,0.06], indices 250/9749).
- **S3 Manifests + dummy data.** `csvio`, `audio`, `manifest`, `dummy`, `select`. *Accept:* `ukstt make-dummy-data --out dummy` then `build-manifest` on it gives 0 errors; `select --stage pilot` gives 36 rows totalling 18.0 min; the negative-case tests produce each error code.
- **S4 Fake + cache + runner.** `transcribe/{base,fake,cache,runner}`, ledger stubbed off. *Accept:* `test_cache`, `test_fake`, `test_runner` pass; a run of `ukstt transcribe --clips manifests/pilot.csv --run-id pilot-fake-001` over the dummy pilot gives 36 `ok` rows and a second invocation gives 0 new calls.
- **S5 End-to-end dry run on dummy.** `aggregate.py`, CLI score/stats. *Accept:* `test_e2e_dummy` passes; `results/pilot-fake-001/` has all six CSVs; no real network used; outputs reproduce byte-identically.
- **S6 Ledger + ElevenLabs + gate.** *Accept:* `test_ledger` and `test_elevenlabs` pass; `ukstt transcribe --backend elevenlabs --clips manifests/smoke.csv --run-id x` (no `--max-audio-minutes`) exits 2 with zero network calls; `ukstt ledger show` works on an empty ledger. Freeze normaliser resources here (tag `norm-frozen`).
- **S7 Real smoke test (user attended; key in `.env.local`).** Run the smoke command above. *Accept:* HTTP 200; `raw/…json` contains `words[]` with `type`; the ledger shows about 231 credits; `transcribe_log.csv` has status `ok`. If 401/402/403: stop and report that the free key cannot call STT (this resolves the open question), with no retry loop.
- **S8 Real pilot (requires real recordings meeting §5).** Run the pilot command. *Accept:* 36/36 clips `ok` or `cached` (the smoke clip is a cache hit); ledger delta <= 6,237 credits; `score` and `stats` produce all CSVs; sanity check: ssbe read WER < 0.25 (soft, investigate otherwise); hand-inspect 3 clips' alignments; `pairwise_vs_baseline.csv` has `low_n=true` everywhere and no `p_holm < 0.05` possible.
- **S9 SLR83 build and spot check.** Fixture-tested first, then `slr83 inspect` and `slr83 build` on real zips, then the real spot run. *Accept:* `slr83 inspect` confirms the speaker-ID rule (each speaker maps to exactly one label across zips, and the per-label speaker counts are plausible). `spot.csv` has 6 rows of 18–22 s. Real run uses <= 2 min audio. `region_summary.csv` has 6 SLR83 rows with source=slr83.
- **S10 Approval gate for the full study.** Produce no code. Hand the user the pilot tables, the §9 numbers, and the per-region speaker-count and minutes estimate for approval. Do not proceed without an explicit yes and a plan with enough credits.

Sequence note: S1–S5 can be done with no recordings. S8 is blocked until someone supplies recordings.
