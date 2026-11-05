SEED = 20261102
B = 10_000
ALPHA = 0.05
MIN_SPEAKERS_CI = 5
BASELINE = "southern"
MAX_WORKERS = 8
PILOT_CAP_MIN = 10.0
DEMO_CAP_MIN = 3.0
CREDITS_PER_MIN = 330  # only for the 'to send' message of the real backend; unverified, not enforced
PILOT_REGIONS = ("southern", "midlands", "northern", "scottish", "welsh", "irish")
ID_RE = r"^[a-z0-9_]{1,64}$"  # filename-safe check for clip_id and speaker_id; ids are opaque and never parsed

# Defaults for config/study.toml; load_config fills any missing key from these.
DEFAULT_PARAMS = {
    "model_id": "scribe_v2",
    "language_code": "eng",
    "tag_audio_events": False,
    "timestamps_granularity": "word",
    "diarize": False,
    "no_verbatim": False,
    "seed": SEED,
    "file_format": "other",
}
DEFAULT_HTTP = {
    "max_retries": 3,
    "connect_timeout_s": 10.0,
    "read_timeout_s": 120.0,
    "default_workers": 4,
}
DEFAULT_PATHS = {"runs_dir": "runs", "results_dir": "results"}
