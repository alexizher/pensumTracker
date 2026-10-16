from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import responses

from app.core.config import get_settings
from tests.fakes.portal import FakePortal


@pytest.fixture
def fake_portal_factory() -> Iterator[Callable[..., FakePortal]]:
    """Abre un RequestsMock y entrega una función que arma un FakePortal sobre él."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:

        def build(*, multi_program: bool = False, validar_ok: bool = True) -> FakePortal:
            return FakePortal(rsps, multi_program=multi_program, validar_ok=validar_ok)

        yield build


@pytest.fixture
def fake_portal(fake_portal_factory: Callable[..., FakePortal]) -> FakePortal:
    return fake_portal_factory()


@pytest.fixture(autouse=True)
def _configuracion_hermetica(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Ningún test lee el .env del desarrollador ni variables de configuración."""
    for name in ("ALLOWED_ORIGINS", "PORTAL_CONNECT_TIMEOUT", "PORTAL_READ_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
