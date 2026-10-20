import pytest
import requests
from pydantic import SecretStr

from app.core.errors import InvalidCredentials, PortalUnavailable
from app.portal.credentials import LoginPerRequest, PortalCredentials
from app.portal.session import PortalSession
from tests.fakes.portal import SSO, FakePortal


def test_repr_no_muestra_la_clave():
    assert "clave-secreta" not in repr(PortalCredentials("u", SecretStr("clave-secreta")))


def test_login_per_request_devuelve_sesion_con_credenciales(fake_portal: FakePortal):
    credentials = PortalCredentials("usuario", SecretStr("clave"))
    session = LoginPerRequest().open(credentials)
    assert session.credentials is credentials
    session.close()


def test_login_per_request_lanza_invalid_credentials(fake_portal_factory):
    fake_portal_factory(validar_ok=False)
    with pytest.raises(InvalidCredentials):
        LoginPerRequest().open(PortalCredentials("usuario", SecretStr("clave")))


def _captura_sesiones(monkeypatch) -> list:
    sessions: list = []

    class Spy(PortalSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            sessions.append(self)

    monkeypatch.setattr("app.portal.credentials.PortalSession", Spy)
    return sessions


def test_open_cierra_la_sesion_si_las_credenciales_son_invalidas(fake_portal_factory, monkeypatch):
    sessions = _captura_sesiones(monkeypatch)
    fake_portal_factory(validar_ok=False)
    with pytest.raises(InvalidCredentials):
        LoginPerRequest().open(PortalCredentials("usuario", SecretStr("clave")))
    (session,) = sessions
    assert session.closed is True


def test_open_cierra_la_sesion_si_el_portal_no_responde(fake_portal, monkeypatch):
    sessions = _captura_sesiones(monkeypatch)
    fake_portal.override("POST", SSO, body=requests.ConnectTimeout())
    with pytest.raises(PortalUnavailable):
        LoginPerRequest().open(PortalCredentials("usuario", SecretStr("clave")))
    (session,) = sessions
    assert session.closed is True


def test_release_cierra_la_sesion(fake_portal: FakePortal):
    provider = LoginPerRequest()
    session = provider.open(PortalCredentials("usuario", SecretStr("clave")))
    provider.release(session)
    assert session.closed is True
    assert session.credentials is None


def test_release_dos_veces_no_falla(fake_portal: FakePortal):
    provider = LoginPerRequest()
    session = provider.open(PortalCredentials("usuario", SecretStr("clave")))
    provider.release(session)
    provider.release(session)
    assert session.closed is True
