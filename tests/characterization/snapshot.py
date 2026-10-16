import os
from pathlib import Path

SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"


def assert_matches_snapshot(name: str, text: str) -> None:
    path = SNAPSHOTS / name
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    if not path.exists():
        raise AssertionError(f"Falta el snapshot {name}; correr con UPDATE_SNAPSHOTS=1")
    assert text == path.read_text(encoding="utf-8")
