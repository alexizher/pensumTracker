from collections.abc import Callable

import responses
from pydantic import SecretStr

from app.core.config import get_settings
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


def test_login_usa_los_hosts_de_settings(monkeypatch):
    monkeypatch.setenv("TSONE_URL", "https://tsone.example")
    monkeypatch.setenv("AYUDAME2_URL", "https://ayudame2.example")
    get_settings.cache_clear()
    tsone_app = "https://tsone.example/php_relogin/?app=validar"
    ayudame2_app = "https://ayudame2.example/php_relogin/?app=validar"
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add("POST", "https://ayudame2.example/php_mua_externos/", body="ok")
        rsps.add("GET", "https://tsone.example/php_historia_estudiante/", body="<html></html>")
        for host, hash_ in (("tsone.example", "h-tsone"), ("ayudame2.example", "h-ayudame2")):
            relogin = f"https://{host}/php_relogin/"
            rsps.add("POST", f"{relogin}?app=ingreso", body="")
            rsps.add("POST", f"{relogin}?app=validar", json={"hash": hash_})
            rsps.add(
                "GET",
                f"https://{host}/php_libs/reauthenticate_end.php?hash={hash_}",
                body="<html></html>",
            )
        session = PortalSession()
        assert login(session, creds("usuario", "clave")) is True
        llamadas = [c.request.url for c in rsps.calls]
    assert tsone_app in llamadas
    assert ayudame2_app in llamadas
    assert session.udeasecure == "h-ayudame2"
