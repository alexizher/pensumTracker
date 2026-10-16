import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from main import app

BACKEND = Path(__file__).resolve().parents[2]
URL = "/api/login/stream"


def _preflight(client: TestClient, origin: str) -> dict[str, str]:
    response = client.options(
        URL,
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    return dict(response.headers)


def test_preflight_origen_permitido():
    with TestClient(app) as client:
        headers = _preflight(client, "http://localhost:5173")
    assert headers["access-control-allow-origin"] == "http://localhost:5173"


def test_preflight_origen_no_permitido():
    with TestClient(app) as client:
        headers = _preflight(client, "https://otro.example")
    assert "access-control-allow-origin" not in headers


_SCRIPT = """
import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
result = {}
for origin in ("https://a.example", "https://b.example"):
    response = client.options(
        "/api/login/stream",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    result[origin] = response.headers.get("access-control-allow-origin")
print(json.dumps(result))
"""


def test_allowed_origins_desde_el_entorno():
    env = {**os.environ, "ALLOWED_ORIGINS": "https://a.example,https://b.example"}
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result == {
        "https://a.example": "https://a.example",
        "https://b.example": "https://b.example",
    }
