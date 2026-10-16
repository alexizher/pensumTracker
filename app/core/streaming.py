from collections.abc import Callable
from typing import Any

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send


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
