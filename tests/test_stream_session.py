import json
import logging
from collections.abc import Generator, Iterator
from typing import cast

import anyio
import pytest
import requests
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.stream import ClosingStreamingResponse
from app.portal.credentials import (
    LoginPerRequest,
    PortalCredentials,
    get_session_provider,
)
from app.portal.session import PortalSession
from main import app
from routers.academic_router import _stream_record
from scraper.portal_scraper import PortalScraper
from tests.fakes.portal import AYUDAME2, CURSUM, FakePortal, fixture, validar_url

URL = "/api/login/stream"
BODY = {"username": "usuario", "password": "clave", "pensum_version": 0}


class RecordingProvider:
    def __init__(self) -> None:
        self.sessions: list[PortalSession] = []

    def open(self, credentials: PortalCredentials) -> PortalSession:
        session = LoginPerRequest().open(credentials)
        self.sessions.append(session)
        return session


@pytest.fixture
def provider() -> Iterator[RecordingProvider]:
    recording = RecordingProvider()
    app.dependency_overrides[get_session_provider] = lambda: recording
    yield recording
    app.dependency_overrides.pop(get_session_provider, None)


def test_stream_cierra_la_sesion(fake_portal: FakePortal, provider: RecordingProvider):
    with TestClient(app) as client:
        response = client.post(URL, json=BODY)
    stages = [json.loads(line)["stage"] for line in response.text.splitlines() if line.strip()]
    assert stages[-1] == "record"
    (session,) = provider.sessions
    assert session.closed is True
    assert session.credentials is None


def test_generador_cerrado_a_medias_cierra_la_sesion(fake_portal: FakePortal):
    credentials = PortalCredentials("usuario", SecretStr("clave"))
    session = LoginPerRequest().open(credentials)
    stream = cast(Generator[str], _stream_record(PortalScraper(session), 0, "test"))
    next(stream)
    assert session.closed is False
    stream.close()
    assert session.closed is True
    assert session.credentials is None


def test_reauth_tardio_usa_la_clave_de_la_sesion(fake_portal: FakePortal):
    pensum = f"{AYUDAME2}/php_pensum_estudiante/?app=consultar"
    calls = {"n": 0}

    def callback(request: requests.PreparedRequest) -> tuple[int, dict[str, str], str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return 200, {}, "<html>php_relogin</html>"
        return 200, {}, fixture("pensum_oficial.html")

    fake_portal._add("GET", pensum, callback=callback, content_type="text/html; charset=utf-8")
    with TestClient(app) as client:
        response = client.post(URL, json=BODY)
    stages = [json.loads(line)["stage"] for line in response.text.splitlines() if line.strip()]
    assert stages[-1] == "record"
    validar = [
        c for c in fake_portal.rsps.calls if c.request.url == validar_url("ayudame2.udea.edu.co")
    ]
    assert len(validar) == 2
    assert all(c.request.body == "clave=clave" for c in validar)


def _scope() -> dict:
    return {"type": "http", "asgi": {"version": "3.0"}, "method": "POST", "headers": []}


async def _receive_forever():
    await anyio.sleep_forever()
    return {}


def _response(session: PortalSession) -> ClosingStreamingResponse:
    scraper = PortalScraper(session)
    return ClosingStreamingResponse(
        _stream_record(scraper, 0, "test"),
        media_type="application/x-ndjson",
        on_close=scraper.logout,
    )


def test_corte_del_cliente_tras_el_primer_chunk_cierra_la_sesion(fake_portal: FakePortal):
    # No discrimina sin on_close: el generador se cierra por GC y la sesión se
    # cierra igual. Quienes prueban on_close son los tests de http.disconnect y
    # de respuesta sin iterar.
    session = LoginPerRequest().open(PortalCredentials("usuario", SecretStr("clave")))
    sent: list[str] = []

    async def send(message):
        sent.append(message["type"])
        if message["type"] == "http.response.body":
            raise OSError("cliente desconectado")

    async def run():
        await _response(session)(_scope(), _receive_forever, send)

    with pytest.raises(OSError):
        anyio.run(run)
    assert "http.response.body" in sent
    assert session.closed is True
    assert session.credentials is None


def test_desconexion_por_receive_cierra_la_sesion(fake_portal: FakePortal):
    session = LoginPerRequest().open(PortalCredentials("usuario", SecretStr("clave")))

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        pass

    async def run():
        await _response(session)(_scope(), receive, send)

    anyio.run(run)
    assert session.closed is True
    assert session.credentials is None


def test_respuesta_sin_iterar_cierra_la_sesion(fake_portal: FakePortal):
    session = LoginPerRequest().open(PortalCredentials("usuario", SecretStr("clave")))

    async def send(message):
        raise OSError("cliente desconectado")

    async def run():
        await _response(session)(_scope(), _receive_forever, send)

    with pytest.raises(OSError):
        anyio.run(run)
    assert session.closed is True
    assert session.credentials is None


def test_login_no_stream_cierra_la_sesion(fake_portal: FakePortal, provider: RecordingProvider):
    with TestClient(app) as client:
        response = client.post("/api/login", json=BODY)
    assert response.status_code == 200
    (session,) = provider.sessions
    assert session.closed is True
    assert session.credentials is None


def test_academic_record_cierra_la_sesion(fake_portal: FakePortal, monkeypatch):
    original = PortalSession.from_cookies.__func__  # type: ignore[attr-defined]
    sessions: list[PortalSession] = []

    def spy(cls, cookies):
        session = original(cls, cookies)
        sessions.append(session)
        return session

    monkeypatch.setattr(PortalSession, "from_cookies", classmethod(spy))
    body = {"cookies": {"user_name": "u"}, "pensum_version": 0}
    with TestClient(app) as client:
        response = client.post("/api/academic-record", json=body)
    assert response.status_code == 200
    (session,) = sessions
    assert session.closed is True


def test_error_de_red_en_stream_conserva_la_causa(fake_portal: FakePortal, caplog):
    fake_portal.override("GET", f"{CURSUM}/pensum/506/5", body=requests.ReadTimeout())
    with caplog.at_level(logging.WARNING, logger="routers.academic_router"):
        with TestClient(app) as client:
            client.post(URL, json=BODY)
    records = [r for r in caplog.records if "durante el streaming" in r.getMessage()]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert "ReadTimeout" in caplog.text
