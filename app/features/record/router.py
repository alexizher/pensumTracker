import functools
import logging
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from pydantic import BaseModel, SecretStr

from app.core.stream import ClosingStreamingResponse, Stage, StreamContext, run_stages
from app.portal.credentials import PortalCredentials, SessionProvider, get_session_provider

log = logging.getLogger(__name__)

_STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class LoginRequest(BaseModel):
    username: str
    password: SecretStr
    pensum_version: int = 0


def build_router(stages: Sequence[Stage]) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/login/stream")
    def login_and_stream(
        body: LoginRequest, provider: SessionProvider = Depends(get_session_provider)
    ) -> ClosingStreamingResponse:
        log.info("login/stream: intento de autenticación | pensum_version=%d", body.pensum_version)
        session = provider.open(PortalCredentials(body.username, body.password))
        log.info("login/stream: autenticación exitosa")
        release = functools.partial(provider.release, session)
        try:
            ctx = StreamContext(session, body.pensum_version)
            return ClosingStreamingResponse(
                run_stages(stages, ctx, on_finish=release),
                media_type="application/x-ndjson",
                headers=_STREAM_HEADERS,
                on_close=release,
            )
        except BaseException:
            release()
            raise

    return router
