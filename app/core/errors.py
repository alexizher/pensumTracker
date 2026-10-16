from typing import ClassVar

GENERIC_DETAIL = "Error inesperado al obtener el pensum"


class PortalError(Exception):
    status_code: ClassVar[int] = 500
    detail: ClassVar[str] = GENERIC_DETAIL


class InvalidCredentials(PortalError):
    status_code = 401
    detail = "Credenciales inválidas o sesión no establecida"


class PortalFormatChanged(PortalError):
    status_code = 502
    detail = "El portal de la UdeA no devolvió una respuesta válida"


class PortalUnavailable(PortalError):
    pass


def error_payload(exc: BaseException) -> tuple[int, str]:
    if isinstance(exc, PortalError):
        return exc.status_code, exc.detail
    return 500, GENERIC_DETAIL
