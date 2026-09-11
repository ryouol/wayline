"""Reject oversized request streams before their next chunk reaches a parser."""

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_upload_bytes: int):
        self.app = app
        self.upload_ceiling = max_upload_bytes + 1024 * 1024

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.upload_ceiling if scope["path"] == "/api/assets" else 64 * 1024
        if scope["path"] == "/analytics/page-view":
            limit = 512
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(
                    scope, receive, send
                )
                return
            if length < 0 or length > limit:
                await JSONResponse({"detail": "Request body is too large."}, status_code=413)(
                    scope, receive, send
                )
                return

        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Raised while the route reads its body: FastAPI preserves
                    # the 413 and Starlette closes any partial multipart files.
                    raise HTTPException(413, "Request body is too large.")
            return message

        await self.app(scope, bounded_receive, send)
