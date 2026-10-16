from collections.abc import Callable, Iterator

import pytest
import responses

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
