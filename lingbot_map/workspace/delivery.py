"""Reserve delivery capacity after range validation and before response headers."""

from collections.abc import Callable
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.responses import FileResponse
from starlette.types import Message, Receive, Scope, Send


class BudgetedFileResponse(FileResponse):
    def __init__(self, *args: Any, reserve_bytes: Callable[[int], None], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.reserve_bytes = reserve_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def reserve_before_send(message: Message) -> None:
            if (
                message["type"] == "http.response.start"
                and message["status"] in (200, 206)
                and scope["method"] != "HEAD"
            ):
                # FileResponse has resolved Range / If-Range and set the actual
                # response length. Rejected ranges never reach this admission.
                size = int(Headers(raw=message["headers"])["content-length"])
                await run_in_threadpool(self.reserve_bytes, size)
                # Keep the reservation on disconnect: the peer may have received
                # bytes even when completion cannot be observed reliably.
            await send(message)

        await super().__call__(scope, receive, reserve_before_send)
