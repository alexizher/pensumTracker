import json
from collections.abc import Callable

import requests
from fastapi.testclient import TestClient

from main import app
from tests.characterization.snapshot import assert_matches_snapshot
from tests.fakes.portal import CURSUM, SSO, FakePortal, fixture

URL = "/api/login/stream"
BODY = {"username": "usuario", "password": "clave", "pensum_version": 0}

PortalFactory = Callable[..., FakePortal]


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _events(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _stages(events: list[dict]) -> list[str]:
    return [e["stage"] for e in events]


def _json_snapshot(response) -> str:
    return json.dumps(
        {"status": response.status_code, "body": response.text},
        ensure_ascii=False,
        indent=2,
    )


def _stream(body: dict | None = None):
    return _client().post(URL, json=body or BODY)


def _subject(event: dict, code: str | int) -> dict:
    """Materia con ese código en un evento pensum o record."""
    return next(x for x in event["data"]["subjects"] if x["code"] == str(code))


def _subject_by_name(event: dict, name: str) -> dict:
    return next(x for x in event["data"]["subjects"] if x["name"] == name)


def test_programa_unico(fake_portal_factory: PortalFactory):
    fake_portal_factory()
    response = _stream()
    events = _events(response.text)
    assert _stages(events) == [
        "student_info",
        "program_info",
        "pensum",
        "pensum",
        "program_info",
        "record",
    ]
    record = events[-1]
    alias = _subject(record, 2517450)
    assert alias["cursada"] is True
    assert alias["nota"] is None
    assert _subject(record, 2000300)["status"] == "in_progress"
    assert _subject(record, 2000500)["status"] == "locked"
    assert events[4]["data"]["total_credits"] != 30
    assert_matches_snapshot("programa_unico.ndjson", response.text)


def test_varios_programas(fake_portal_factory: PortalFactory):
    fake_portal_factory(multi_program=True)
    response = _stream()
    events = _events(response.text)
    infos = [e for e in events if e["stage"] == "program_info"]
    assert len(infos) == 1
    assert infos[0]["data"]["pensum_version"] == 3
    assert infos[0]["data"]["enrolled_version"] == 3
    assert infos[0]["data"]["total_credits"] == 30
    electiva = _subject_by_name(events[-1], "ELECTIVA VIEJA A")
    assert electiva["cursada"] is True
    assert electiva["nota"] == 3.8
    assert_matches_snapshot("varios_programas.ndjson", response.text)


def test_version_pedida(fake_portal_factory: PortalFactory):
    fake_portal_factory()
    response = _stream({**BODY, "pensum_version": 5})
    infos = [e for e in _events(response.text) if e["stage"] == "program_info"]
    assert infos[0]["data"]["pensum_version"] == 5
    assert_matches_snapshot("version_pedida.ndjson", response.text)


def test_login_fallido(fake_portal_factory: PortalFactory):
    fake_portal_factory(validar_ok=False)
    response = _stream()
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas o sesión no establecida"
    assert_matches_snapshot("login_fallido.json", _json_snapshot(response))


def test_login_timeout(fake_portal: FakePortal):
    fake_portal.override("POST", SSO, body=requests.ConnectTimeout())
    response = _stream()
    assert response.status_code == 500
    assert_matches_snapshot("login_timeout.json", _json_snapshot(response))


def test_cursum_sin_json(fake_portal: FakePortal):
    fake_portal.override("GET", f"{CURSUM}/programas", body="<html>error</html>")
    response = _stream()
    events = _events(response.text)
    assert events[-1] == {
        "stage": "error",
        "status": 502,
        "detail": "El portal de la UdeA no devolvió una respuesta válida",
    }
    assert_matches_snapshot("cursum_sin_json.ndjson", response.text)


def test_timeout_en_stream(fake_portal: FakePortal):
    fake_portal.override("GET", f"{CURSUM}/pensum/506/5", body=requests.ReadTimeout())
    response = _stream()
    events = _events(response.text)
    assert _stages(events) == ["student_info", "program_info", "error"]
    assert events[-1]["status"] == 500
    assert events[-1]["detail"] == "Error inesperado al obtener el pensum"
    assert_matches_snapshot("timeout_en_stream.ndjson", response.text)


def test_clave_faltante(fake_portal: FakePortal):
    items = json.loads(fixture("cursum_pensum_506.json"))
    del items[0]["creditos"]
    fake_portal.override("GET", f"{CURSUM}/pensum/506/5", json=items)
    response = _stream()
    events = _events(response.text)
    assert events[-1]["stage"] == "error"
    assert events[-1]["status"] == 500
    assert_matches_snapshot("clave_faltante.ndjson", response.text)
