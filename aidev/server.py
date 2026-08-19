"""FastAPI server for AI DevTools trace inspection."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aidev.storage import TraceSQLite
from aidev.trace import Span, SpanStatus


# --- Pydantic models for API ---

class SpanInfo(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None
    start_time: float
    end_time: Optional[float] = None
    status: str = "ok"
    metadata: Dict[str, Any] = {}
    errors: List[str] = []
    inputs: Optional[Any] = None
    outputs: Optional[Any] = None
    model: Optional[str] = None
    model_token_count: Optional[int] = None
    operation: Optional[str] = None


class NewSpan(BaseModel):
    name: str
    parent_id: Optional[str] = None
    inputs: Optional[Any] = None


# --- Module-level storage (initialized in lifespan) ---

storage: Optional[TraceSQLite] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global storage
    storage = TraceSQLite("traces.db")
    yield
    storage.close()


# --- FastAPI app ---

app = FastAPI(
    title="AI DevTools",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper to get storage ---

def get_storage() -> TraceSQLite:
    if storage is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="storage not initialized")
    return storage


# --- API Routes ---

@app.get("/api/spans", response_model=List[SpanInfo])
def list_spans():
    """List all spans sorted by start time."""
    s = get_storage()
    spans = s.get_root_spans()
    return [_span_to_info(si) for si in spans]


@app.get("/api/spans/{span_id}", response_model=SpanInfo)
def get_span(span_id: str):
    """Get a single span by ID."""
    s = get_storage()
    span = s.get_by_id(span_id)
    if span is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Span not found")
    return _span_to_info(span)


@app.post("/api/spans", response_model=SpanInfo)
def create_span(new_span: NewSpan):
    """Create a new root span."""
    from fastapi import HTTPException
    from aidev.trace import Tracer

    tracer = Tracer(storage=get_storage())
    ctx = tracer.trace(new_span.name, inputs=new_span.inputs)
    span = ctx._span
    return _span_to_info(span)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live trace updates."""
    await websocket.accept()
    try:
        while True:
            # Keep connection alive; receive messages
            msg = await websocket.receive_text()
            if msg == "get_spans":
                s = get_storage()
                spans = s.get_root_spans()
                ws_data = [_span_to_info(si) for si in spans]
                await websocket.send_json({"type": "spans_update", "spans": ws_data})
    except WebSocketDisconnect:
        pass


def _add_children(span: Span, span_map: Dict[str, any]) -> None:
    children = get_storage().get_children(span.id)
    for child in children:
        span_map[child.id] = _span_to_info(child)
        _add_children(child, span_map)


def _span_to_info(span: Span) -> SpanInfo:
    return SpanInfo(
        id=span.id,
        name=span.name,
        parent_id=span.parent_id,
        start_time=span.start_time,
        end_time=span.end_time,
        status=span.status.value,
        metadata=span.metadata,
        errors=span.errors,
        inputs=span.inputs,
        outputs=span.outputs,
        model=span.model,
        model_token_count=span.model_token_count,
        operation=span.operation,
    )


# --- Serve static UI from ./static ---

@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response