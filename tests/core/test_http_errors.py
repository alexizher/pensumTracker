from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import InvalidCredentials, PortalFormatChanged, PortalUnavailable
from app.core.http_errors import register_error_handlers


def _app_con_ruta(exc: Exception) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/falla")
    def falla() -> None:
        raise exc

    return app


def test_manejador_responde_json_igual_que_httpexception():
    client = TestClient(_app_con_ruta(InvalidCredentials()))
    response = client.get("/falla")
    assert response.status_code == 401
    assert response.text == '{"detail":"Credenciales inválidas o sesión no establecida"}'


def test_manejador_de_formato_cambiado_responde_502():
    client = TestClient(_app_con_ruta(PortalFormatChanged()))
    response = client.get("/falla")
    assert response.status_code == 502
    assert response.text == '{"detail":"El portal de la UdeA no devolvió una respuesta válida"}'


def test_portal_unavailable_no_tiene_manejador():
    client = TestClient(_app_con_ruta(PortalUnavailable()), raise_server_exceptions=False)
    response = client.get("/falla")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
