from fastapi import HTTPException
from starlette.responses import JSONResponse


class UploadLimit:
    """Enforce the cap while multipart bytes arrive, even for chunked requests."""

    def __init__(self, app, max_bytes=27 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        header = dict(scope["headers"]).get(b"content-length", b"")
        if header.isdigit() and int(header) > self.max_bytes:
            return await JSONResponse({"message": "Upload is too large"}, status_code=413)(
                scope, receive, send
            )
        count = 0

        async def bounded():
            nonlocal count
            event = await receive()
            if event["type"] == "http.request":
                count += len(event.get("body", b""))
                if count > self.max_bytes:
                    raise HTTPException(413, "Upload is too large")
            return event

        await self.app(scope, bounded, send)
