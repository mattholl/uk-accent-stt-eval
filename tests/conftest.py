import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any real connection attempt fails loudly; HTTP is mocked with `responses`."""
    def blocked(self, *args, **kwargs):
        raise RuntimeError("network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def clipset(tmp_path):
    """Six tiny clips (one per region, 20-word references): returns (clips_csv, rows)."""
    from ukstt.audio import write_test_wav
    from ukstt.constants import PILOT_REGIONS
    from ukstt.csvio import write_csv

    rows = []
    for i, region in enumerate(PILOT_REGIONS):
        clip_id = f"{region}_01_01"
        audio, ref = tmp_path / "audio" / f"{clip_id}.wav", tmp_path / "refs" / f"{clip_id}.txt"
        write_test_wav(audio, 0.5, seed=i)
        ref.parent.mkdir(exist_ok=True)
        ref.write_text(" ".join(f"word{j}" for j in range(20)) + "\n")
        rows.append({"clip_id": clip_id, "set": "pilot", "speaker_id": f"{region}_01", "region": region,
                     "task": "read", "audio_path": str(audio), "reference_path": str(ref), "source": "t",
                     "notes": "", "duration_s": "0.5"})
    path = tmp_path / "clips.csv"
    write_csv(path, rows, list(rows[0]))
    return path, rows
