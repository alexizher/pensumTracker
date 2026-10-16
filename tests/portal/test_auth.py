from collections.abc import Callable

from pydantic import SecretStr

from app.portal.auth import login, validate
from app.portal.credentials import PortalCredentials
from app.portal.session import PortalSession
from tests.fakes.portal import HISTORIA, SSO, FakePortal


def creds(username: str, password: str) -> PortalCredentials:
    return PortalCredentials(username, SecretStr(password))


def test_login_ok(fake_portal: FakePortal):
    session = PortalSession()
    assert login(session, creds("usuario", "clave")) is True
    assert session.udeasecure == "hash-ayudame2.udea.edu.co"


def test_login_falla_si_validar_rechaza(fake_portal_factory: Callable[..., FakePortal]):
    fake_portal_factory(validar_ok=False)
    assert login(PortalSession(), creds("usuario", "clave")) is False


def test_login_falla_si_sso_no_200(fake_portal: FakePortal):
    fake_portal.override("POST", SSO, body="", status=500)
    assert login(PortalSession(), creds("usuario", "clave")) is False


def test_validate_detecta_sesion_caida(fake_portal: FakePortal):
    session = PortalSession()
    assert login(session, creds("usuario", "clave")) is True
    fake_portal.override("GET", f"{HISTORIA}?app=consultar", body="No hay usuario conectado")
    assert validate(session) is False
