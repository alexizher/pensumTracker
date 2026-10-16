import json
from collections.abc import Generator, Iterator
from typing import cast

import pytest
import requests
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.portal.credentials import (
    LoginPerRequest,
    PortalCredentials,
    get_session_provider,
)
from app.portal.session import PortalSession
from main import app
from routers.academic_router import _stream_record
from scraper.portal_scraper import PortalScraper
from tests.fakes.portal import AYUDAME2, FakePortal, fixture, validar_url

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


def test_stream_abandonado_cierra_la_sesion(fake_portal: FakePortal, provider: RecordingProvider):
    # El TestClient de esta versión consume el cuerpo entero aunque se salga antes, así que
    # este test no prueba el abandono. Lo prueba test_generador_cerrado_a_medias_cierra_la_sesion.
    with TestClient(app) as client:
        with client.stream("POST", URL, json=BODY) as response:
            next(response.iter_lines())
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
