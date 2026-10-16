import pytest
import requests
import responses

from app.core.errors import PortalUnavailable
from app.portal.session import PortalSession

URL = "https://tsone.udea.edu.co/x"


def test_timeout_por_defecto():
    with responses.RequestsMock() as rsps:
        rsps.get(URL, body="ok")
        PortalSession().get(URL)
        assert rsps.calls[0].request.req_kwargs["timeout"] == (5, 30)


def test_error_de_red_es_portal_unavailable():
    with responses.RequestsMock() as rsps:
        rsps.get(URL, body=requests.ConnectTimeout())
        with pytest.raises(PortalUnavailable):
            PortalSession().get(URL)


def test_tsone_get_envia_udeasecure():
    with responses.RequestsMock() as rsps:
        rsps.get(URL, body="ok")
        s = PortalSession()
        s.set_udeasecure("h1")
        s.tsone_get(URL)
        assert "udeasecure=h1" in rsps.calls[0].request.headers["Cookie"]


def test_close_borra_estado():
    s = PortalSession.from_cookies({"user_name": "u", "udeasecure": "h"})
    s.credentials = object()
    assert len(s.cookies) == 2
    pool = s._legacy_adapter.poolmanager
    pool.connection_from_url("https://tsone.udea.edu.co/")
    assert len(pool.pools) == 1
    s.close()
    assert len(pool.pools) == 0
    assert s.credentials is None
    assert s.udeasecure == ""
    assert len(s.cookies) == 0
    assert s.closed is True


def test_from_cookies():
    s = PortalSession.from_cookies({"udeasecure": "h", "user_name": "u", "phpsessid_ayudame2": "p"})
    assert s.udeasecure == "h"
    found = {(c.name, c.domain, c.path): c.value for c in s.cookies}
    assert found[("udeasecure", ".udea.edu.co", "/")] == "h"
    assert found[("user_name", ".udea.edu.co", "/")] == "u"
    assert found[("PHPSESSID", "ayudame2.udea.edu.co", "/")] == "p"
