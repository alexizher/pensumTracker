from app.core.errors import (
    InvalidCredentials,
    PortalFormatChanged,
    PortalUnavailable,
    error_payload,
)


def test_error_payload_por_tipo():
    assert error_payload(InvalidCredentials()) == (
        401,
        "Credenciales inválidas o sesión no establecida",
    )
    assert error_payload(PortalFormatChanged()) == (
        502,
        "El portal de la UdeA no devolvió una respuesta válida",
    )
    assert error_payload(PortalUnavailable()) == (500, "Error inesperado al obtener el pensum")
    assert error_payload(KeyError("creditos")) == (500, "Error inesperado al obtener el pensum")
