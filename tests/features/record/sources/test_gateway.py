from collections.abc import Callable

import pytest
import requests
from pydantic import SecretStr

from app.core.errors import PortalFormatChanged
from app.features.record.sources.gateway import PortalRecordSource
from app.features.record.sources.models import OfficialPensum
from app.portal.credentials import PortalCredentials
from app.portal.session import PortalSession
from tests.fakes.portal import (
    CLAVE,
    CONSTANCIA,
    CURSUM,
    PENSUM,
    USUARIO,
    FakePortal,
    fixture,
    validar_url,
)

PENSUM_CONSULTAR = f"{PENSUM}?app=consultar"


def _calls(portal: FakePortal, url: str) -> int:
    return sum(1 for c in portal.rsps.calls if c.request.url == url)


def _source(with_credentials: bool = False) -> PortalRecordSource:
    session = PortalSession()
    if with_credentials:
        session.credentials = PortalCredentials(USUARIO, SecretStr(CLAVE))
    return PortalRecordSource(session)


def test_constancia_se_pide_una_vez(fake_portal: FakePortal) -> None:
    source = _source()
    info = source.student_info()
    codes = source.current_subject_codes()
    assert info.program_code == "506"
    assert codes
    assert _calls(fake_portal, f"{CONSTANCIA}?app=consultar") == 1


def test_historia_con_selector(fake_portal_factory: Callable[..., FakePortal]) -> None:
    fake_portal_factory(multi_program=True)
    page = _source().historia("506")
    assert page.selector is not None
    assert page.selector.version == 3
    assert page.semester_codes == ["20241", "20242"]


def test_historia_sin_selector(fake_portal: FakePortal) -> None:
    page = _source().historia("506")
    assert page.selector is None
    assert page.semester_codes == ["20241", "20242"]


def test_official_pensum_reintenta_con_reauth(fake_portal: FakePortal) -> None:
    calls = {"n": 0}

    def callback(request: requests.PreparedRequest) -> tuple[int, dict[str, str], str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return 200, {}, "<html>php_relogin</html>"
        return 200, {}, fixture("pensum_oficial.html")

    fake_portal._add(
        "GET", PENSUM_CONSULTAR, callback=callback, content_type="text/html; charset=utf-8"
    )
    pensum = _source(with_credentials=True).official_pensum()
    assert isinstance(pensum, OfficialPensum)
    assert pensum.version == 5
    validar = [
        c for c in fake_portal.rsps.calls if c.request.url == validar_url("ayudame2.udea.edu.co")
    ]
    assert len(validar) == 1
    assert validar[0].request.body == "clave=clave"


def test_official_pensum_sin_credenciales_no_reintenta(fake_portal: FakePortal) -> None:
    fake_portal.override("GET", PENSUM_CONSULTAR, body="<html>php_relogin</html>")
    source = _source()
    assert source.official_pensum() is None
    assert source.official_pensum() is None
    assert len(fake_portal.rsps.calls) == 1


def test_curriculum_se_pide_una_vez(fake_portal: FakePortal) -> None:
    source = _source()
    first = source.curriculum("506", 5)
    second = source.curriculum("506", 5)
    assert first and first == second
    assert _calls(fake_portal, f"{CURSUM}/pensum/506/5") == 1


def test_program_sin_json_lanza_portal_format_changed(fake_portal: FakePortal) -> None:
    fake_portal.override("GET", f"{CURSUM}/programas", body="<html>error</html>")
    with pytest.raises(PortalFormatChanged):
        _source().program("506")
