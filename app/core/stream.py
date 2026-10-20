import json
import logging
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from app.core.errors import PortalError, error_payload
from app.portal.session import PortalSession

log = logging.getLogger(__name__)

# Un evento lleva la clave "stage" y el resto del payload.
Event = dict[str, object]


@dataclass
class StreamContext:
    session: PortalSession
    requested_version: int
    results: dict[str, object] = field(default_factory=dict)


class Stage(Protocol):
    name: str
    optional: bool

    def run(self, ctx: StreamContext) -> Iterable[Event]: ...


def ndjson(event: Event) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def run_stages(
    stages: Sequence[Stage],
    ctx: StreamContext,
    on_finish: Callable[[], None],
) -> Iterator[str]:
    try:
        for stage in stages:
            try:
                for event in stage.run(ctx):
                    yield ndjson(event)
            except Exception as exc:
                if isinstance(exc, PortalError):
                    log.warning(
                        "%s: error del portal durante el streaming: %s",
                        stage.name,
                        exc.detail,
                        exc_info=exc.__cause__ if exc.__cause__ is not None else False,
                    )
                else:
                    log.exception("%s: error inesperado durante el streaming", stage.name)
                status, detail = error_payload(exc)
                if not stage.optional:
                    yield ndjson({"stage": "error", "status": status, "detail": detail})
                    return
                yield ndjson({"stage": "warning", "source": stage.name, "detail": detail})
    finally:
        on_finish()


class ClosingStreamingResponse(StreamingResponse):
    """StreamingResponse que llama a on_close al terminar, falle o no el envío.

    Red de seguridad para cuando el cliente corta: Starlette no cierra el
    generador síncrono y uno que nunca arrancó no ejecuta su finally."""

    def __init__(self, *args: Any, on_close: Callable[[], None], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._on_close = on_close

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._on_close()
