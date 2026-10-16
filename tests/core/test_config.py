from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_origenes_separados_por_comas(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://a.example , ,https://b.example ")
    assert Settings(_env_file=None).allowed_origins == ["https://a.example", "https://b.example"]


def test_sin_origenes_extra(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    assert Settings(_env_file=None).allowed_origins == []


def test_timeouts_por_defecto():
    s = Settings(_env_file=None)
    assert (s.portal_connect_timeout, s.portal_read_timeout) == (5, 30)


def test_origenes_como_lista_se_limpian():
    s = Settings(_env_file=None, allowed_origins=[" https://x.example ", ""])
    assert s.allowed_origins == ["https://x.example"]


def test_create_app_suma_origenes_extra():
    app = create_app(Settings(_env_file=None, allowed_origins=["https://x.example"]))
    client = TestClient(app)
    for origin in ("https://x.example", "http://localhost:5173"):
        r = client.options(
            "/",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert r.headers["access-control-allow-origin"] == origin


def test_urls_del_portal_por_defecto():
    s = Settings(_env_file=None)
    assert s.tsone_url == "https://tsone.udea.edu.co"
    assert s.ayudame2_url == "https://ayudame2.udea.edu.co"
    assert s.cursum_url == "https://wsingenieria.udea.edu.co:8094/cursum/ingenieria"


def test_url_del_portal_desde_el_entorno(monkeypatch):
    monkeypatch.setenv("TSONE_URL", "https://tsone.example")
    assert Settings(_env_file=None).tsone_url == "https://tsone.example"


def test_urls_del_portal_sin_barra_final(monkeypatch):
    monkeypatch.setenv("TSONE_URL", "https://tsone.example/")
    s = Settings(_env_file=None, cursum_url="https://cursum.example/x/")
    assert s.tsone_url == "https://tsone.example"
    assert s.cursum_url == "https://cursum.example/x"
