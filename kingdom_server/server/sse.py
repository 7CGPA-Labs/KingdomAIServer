"""
OpenAI SSE Streaming protocol helper.
"""
from typing import AsyncGenerator
from fastapi.responses import StreamingResponse

def create_sse_response(generator: AsyncGenerator[str, None]) -> StreamingResponse:
    """Wraps an async generator yielding SSE strings into a FastAPI StreamingResponse."""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )
