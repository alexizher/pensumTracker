import pytest
from pydantic import SecretStr

from app.core.errors import InvalidCredentials
from app.portal.credentials import LoginPerRequest, PortalCredentials
from tests.fakes.portal import FakePortal


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
