"""inpho-sse: a minimal Server-Sent Events notification service."""
import asyncio
import hmac
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from .broadcaster import Broadcaster
from .config import Settings, load_settings

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


async def event_stream(
    request: Request, queue: asyncio.Queue, heartbeat: float
) -> AsyncIterator[str]:
    """Yield SSE frames until the client disconnects or the task is cancelled."""
    yield ": connected\n\n"
    while True:
        if await request.is_disconnected():
            return
        try:
            message = await asyncio.wait_for(queue.get(), timeout=heartbeat)
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"
            continue
        yield f"event: {message}\ndata: changed\n\n"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="inpho-sse", docs_url=None, redoc_url=None, openapi_url=None)
    broadcaster = Broadcaster(settings.queue_size)
    app.state.broadcaster = broadcaster

    def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
        if x_api_key is None or not hmac.compare_digest(
            x_api_key.encode(), settings.api_key.encode()
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @app.get("/stream")
    async def stream(request: Request) -> StreamingResponse:
        queue = broadcaster.subscribe()

        async def generate() -> AsyncIterator[str]:
            try:
                async for frame in event_stream(
                    request, queue, settings.heartbeat_seconds
                ):
                    yield frame
            finally:
                # Runs on disconnect and on cancellation.
                broadcaster.unsubscribe(queue)

        return StreamingResponse(
            generate(), media_type="text/event-stream", headers=SSE_HEADERS
        )

    @app.post("/notify", dependencies=[Depends(require_api_key)])
    async def notify() -> dict:
        count = broadcaster.broadcast()
        return {"status": "sent", "clients": count}

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "clients": broadcaster.client_count}

    return app


def get_app() -> FastAPI:
    return create_app()
