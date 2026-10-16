import json
import os
from pathlib import Path
from typing import Protocol

SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"


class ResponseLike(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...


def json_snapshot(response: ResponseLike) -> str:
    """Status y body de una respuesta no streaming, como JSON con salto final."""
    text = json.dumps(
        {"status": response.status_code, "body": response.text},
        ensure_ascii=False,
        indent=2,
    )
    return text + "\n"


def assert_matches_snapshot(name: str, text: str) -> None:
    path = SNAPSHOTS / name
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    if not path.exists():
        raise AssertionError(f"Falta el snapshot {name}; correr con UPDATE_SNAPSHOTS=1")
    assert text == path.read_text(encoding="utf-8"), (
        f"El snapshot {name} cambió. En este refactor no debe cambiar; si el cambio es "
        "intencional, regenerar con UPDATE_SNAPSHOTS=1 y explicarlo en el PR."
    )
