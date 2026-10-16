"""Pruebas HTTP directas del portal falso: qué acepta y qué rechaza.

No importan código de la app; lo que hace el scraper contra el fake lo fijan los
snapshots de tests/characterization.
"""

import pytest
import requests

from tests.fakes.portal import (
    CONSTANCIA,
    CURSUM,
    HISTORIA,
    SELECTOR,
    SSO,
    FakePortal,
    validar_url,
)

TSONE_HOST = "tsone.udea.edu.co"
XHR = {"X-Requested-With": "XMLHttpRequest"}

TSONE_GETS = (
    f"{CONSTANCIA}?app=consultar",
    f"{HISTORIA}?app=consultar",
    f"{HISTORIA}?app=ver_semestre&semestre=20241",
)


def _validar(host: str = TSONE_HOST) -> str:
    resp = requests.post(validar_url(host), data={"clave": "clave"}, headers=XHR)
    return resp.json()["hash"]


def test_url_no_registrada_falla_fuerte(fake_portal):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://tsone.udea.edu.co/php_historia_estudiante/?app=otra")


def test_query_distinta_no_coincide(fake_portal):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://tsone.udea.edu.co/php_constancia_estudiante/?app=consultar&x=1")


def test_sso_acepta_usuario_y_clave(fake_portal):
    assert requests.post(SSO, data={"usuario": "usuario", "clave": "clave"}).status_code == 200


def test_sso_rechaza_otra_clave(fake_portal):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.post(SSO, data={"usuario": "usuario", "clave": "otra"})


@pytest.mark.parametrize("host", ["tsone.udea.edu.co", "ayudame2.udea.edu.co"])
def test_validar_entrega_hash_y_lo_recuerda(fake_portal: FakePortal, host: str):
    assert _validar(host) == f"hash-{host}"
    assert fake_portal.udeasecure == f"hash-{host}"


@pytest.mark.parametrize("host", ["tsone.udea.edu.co", "ayudame2.udea.edu.co"])
def test_validar_exige_header_xhr(fake_portal, host: str):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.post(validar_url(host), data={"clave": "clave"})


@pytest.mark.parametrize("host", ["tsone.udea.edu.co", "ayudame2.udea.edu.co"])
def test_validar_exige_la_clave(fake_portal, host: str):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.post(validar_url(host), data={"clave": "otra"}, headers=XHR)


def test_validar_rechazado_no_entrega_hash(fake_portal_factory):
    fake = fake_portal_factory(validar_ok=False)
    resp = requests.post(validar_url(TSONE_HOST), data={"clave": "clave"}, headers=XHR)
    assert resp.json() == {"error": "clave"}
    assert fake.udeasecure is None


@pytest.mark.parametrize("url", TSONE_GETS)
def test_tsone_acepta_la_cookie_del_ultimo_hash(fake_portal, url: str):
    h = _validar()
    assert requests.get(url, headers={"Cookie": f"udeasecure={h}"}).status_code == 200


@pytest.mark.parametrize("url", TSONE_GETS)
def test_tsone_sin_cookie_falla(fake_portal, url: str):
    _validar()
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(url)


@pytest.mark.parametrize("url", TSONE_GETS)
def test_tsone_con_hash_viejo_falla(fake_portal, url: str):
    _validar("tsone.udea.edu.co")
    _validar("ayudame2.udea.edu.co")
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(url, headers={"Cookie": "udeasecure=hash-tsone.udea.edu.co"})


def test_varios_programas_redirige_al_selector(fake_portal_factory):
    fake_portal_factory(multi_program=True)
    resp = requests.get(f"{HISTORIA}?app=consultar")
    assert resp.url == SELECTOR
    assert 'value="506" data-version="3"' in resp.text


def test_historia_post_acepta_programa_y_version_con_mas_campos(fake_portal_factory):
    fake_portal_factory(multi_program=True)
    form = {"programa": "506", "version": "3", "facultad": "25", "api": "programasudea"}
    assert requests.post(f"{HISTORIA}?app=consultar", data=form).status_code == 200


def test_historia_post_sin_version_falla(fake_portal_factory):
    fake_portal_factory(multi_program=True)
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.post(f"{HISTORIA}?app=consultar", data={"programa": "506"})


def test_override_reemplaza_respuesta(fake_portal: FakePortal):
    fake_portal.override("GET", f"{CURSUM}/programas", json=[])
    assert requests.get(f"{CURSUM}/programas").json() == []


def test_override_acepta_excepcion(fake_portal: FakePortal):
    fake_portal.override("GET", f"{CURSUM}/programas", body=requests.exceptions.Timeout("lento"))
    with pytest.raises(requests.exceptions.Timeout):
        requests.get(f"{CURSUM}/programas")


def test_override_conserva_los_matchers(fake_portal: FakePortal):
    fake_portal.override("POST", SSO, status=500)
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.post(SSO, data={"usuario": "usuario", "clave": "otra"})
    assert requests.post(SSO, data={"usuario": "usuario", "clave": "clave"}).status_code == 500


def test_override_no_toca_otras_queries_de_la_misma_ruta(fake_portal: FakePortal):
    fake_portal.override("POST", validar_url(TSONE_HOST), json={"error": "clave"})
    ingreso = requests.post("https://tsone.udea.edu.co/php_relogin/?app=ingreso")
    assert ingreso.status_code == 200
