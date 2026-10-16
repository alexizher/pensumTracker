import pytest
import requests

from scraper.portal_scraper import PortalScraper
from tests.fakes.portal import CURSUM, FakePortal


def test_login_contra_portal_falso(fake_portal):
    s = PortalScraper(cookies={})
    assert s.login("usuario", "clave") is True
    assert s.fetch_student_info() == ("ANA PRUEBA", "INGENIERÍA DE PRUEBA", "506")


def test_login_falla_si_validar_rechaza(fake_portal_factory):
    fake_portal_factory(validar_ok=False)
    assert PortalScraper(cookies={}).login("usuario", "clave") is False


def test_varios_programas_toma_version_del_selector(fake_portal_factory):
    fake_portal_factory(multi_program=True)
    s = PortalScraper(cookies={})
    assert s.login("usuario", "clave")
    assert s.fetch_enrolled_version("506") == 3


def test_url_no_registrada_falla_fuerte(fake_portal):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://tsone.udea.edu.co/php_historia_estudiante/?app=otra")


def test_query_distinta_no_coincide(fake_portal):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://tsone.udea.edu.co/php_constancia_estudiante/?app=consultar&x=1")


def test_override_reemplaza_respuesta(fake_portal: FakePortal):
    fake_portal.override("GET", f"{CURSUM}/programas", json=[])
    s = PortalScraper(cookies={})
    assert s.fetch_program_info("506") == (0, [], 0)


def test_override_acepta_excepcion(fake_portal: FakePortal):
    fake_portal.override("GET", f"{CURSUM}/programas", body=requests.exceptions.Timeout("lento"))
    with pytest.raises(requests.exceptions.Timeout):
        PortalScraper(cookies={}).fetch_program_info("506")
