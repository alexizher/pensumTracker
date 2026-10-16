from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import InvalidCredentials, PortalFormatChanged, error_payload


async def _handle_portal_error(request: Request, exc: Exception) -> JSONResponse:
    status, detail = error_payload(exc)
    return JSONResponse({"detail": detail}, status_code=status)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InvalidCredentials, _handle_portal_error)
    app.add_exception_handler(PortalFormatChanged, _handle_portal_error)
