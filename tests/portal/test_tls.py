import pytest

from app.portal.session import PortalSession
from app.portal.tls import LegacyTLSAdapter, is_udea_host


@pytest.mark.parametrize(
    "url",
    [
        "https://tsone.udea.edu.co/php_historia_estudiante/",
        "https://ayudame2.udea.edu.co/",
        "https://wsingenieria.udea.edu.co:8094/cursum/ingenieria/programas",
        "https://udea.edu.co/",
        "https://TSONE.UDEA.EDU.CO/",
    ],
)
def test_hosts_de_la_udea(url):
    assert is_udea_host(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://udea.edu.co.evil.example/",
        "https://notudea.edu.co/",
        "https://example.com/",
        "http://localhost:8000/",
    ],
)
def test_hosts_ajenos(url):
    assert not is_udea_host(url)


def test_sesion_elige_adaptador_por_host():
    s = PortalSession(timeout=(1, 1))
    assert isinstance(s.get_adapter("https://tsone.udea.edu.co/x"), LegacyTLSAdapter)
    assert not isinstance(s.get_adapter("https://example.com/"), LegacyTLSAdapter)
