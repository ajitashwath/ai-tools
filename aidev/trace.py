"""Minimal tracing SDK for AI DevTools."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Dict, List, Callable, ContextManager


class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"


@dataclass
class Span:
    id: str
    name: str
    parent_id: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    status: SpanStatus = SpanStatus.OK
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    inputs: Optional[Any] = None
    outputs: Optional[Any] = None
    model: Optional[str] = None
    model_token_count: Optional[int] = None
    operation: Optional[str] = None
    ttft: Optional[float] = None  # Time To First Token
    tokens_per_sec: Optional[float] = None
    stop_reason: Optional[str] = None
    total_tokens: Optional[int] = None


class Tracer:
    """Simple tracer with SQLite persistence support."""

    def __init__(self, storage=None):
        self._spans: List[Span] = []
        self._span_stack: List[Span] = []
        self._next_id: int = 1
        self._storage = storage
        self._closed = False

    def trace(self, name: str, inputs: Optional[Any] = None) -> "Tracer.SpanContext":
        """Start a new trace span."""
        span_id = f"span-{uuid.uuid4()}"
        span = Span(
            id=span_id,
            name=name,
            start_time=time.time(),
            inputs=inputs,
        )
        self._spans.append(span)
        self._span_stack.append(span)
        if self._storage:
            self._storage.save(span)
        return Tracer.SpanContext(self, span)

    class SpanContext:
        """Context manager for a trace span.

        Attributes delegate to the underlying Span for convenience.

        The span is flushed to storage on context exit.
        """

        def __init__(self, tracer: "Tracer", span: Span):
            self._tracer = tracer
            self._span = span

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self._span.end_time = time.time()
            if exc_type is not None:
                self._span.status = SpanStatus.ERROR
                self._span.errors.append(str(exc_val))
            self._tracer._span_stack.pop()
            # Save the final state of the span to storage
            if self._tracer._storage:
                self._tracer._storage.save(self._span)
            self._tracer._maybe_flush()
            return False

        def set_metadata(self, key: str, value: Any) -> None:
            self._span.metadata[key] = value

        def set_model(self, model: str, token_count: Optional[int] = None) -> None:
            self._span.model = model
            self._span.model_token_count = token_count

        def set_operation(self, operation: str) -> None:
            self._span.operation = operation

        def set_error(self, error: str) -> None:
            self._span.status = SpanStatus.ERROR
            self._span.errors.append(error)

        # Set TTFT (Time To First Token)
        def set_ttft(self, ttft: float) -> None:
            self._span.ttft = ttft

        # Set tokens per second (throughput)
        def set_tokens_per_sec(self, tokens_per_sec: float) -> None:
            self._span.tokens_per_sec = tokens_per_sec

        # Set stop reason (e.g., "end_seq", "length", "error")
        def set_stop_reason(self, reason: str) -> None:
            self._span.stop_reason = reason

        # Set total token count
        def set_total_tokens(self, total_tokens: int) -> None:
            self._span.total_tokens = total_tokens

        # Delegate span attributes for convenience
        @property
        def id(self) -> str:
            return self._span.id

        @property
        def name(self) -> str:
            return self._span.name

        @property
        def parent_id(self) -> Optional[str]:
            return self._span.parent_id

        @property
        def start_time(self) -> float:
            return self._span.start_time

        @property
        def end_time(self) -> float:
            return self._span.end_time

        @property
        def status(self) -> SpanStatus:
            return self._span.status

        @property
        def metadata(self) -> Dict[str, Any]:
            return self._span.metadata

        @property
        def errors(self) -> List[str]:
            return self._span.errors

        @property
        def inputs(self) -> Optional[Any]:
            return self._span.inputs

        @property
        def outputs(self) -> Optional[Any]:
            return self._span.outputs

        @property
        def model(self) -> Optional[str]:
            return self._span.model

        @property
        def model_token_count(self) -> Optional[int]:
            return self._span.model_token_count

        @property
        def operation(self) -> Optional[str]:
            return self._span.operation

        @property
        def ttft(self) -> Optional[float]:
            return self._span.ttft

        @property
        def tokens_per_sec(self) -> Optional[float]:
            return self._span.tokens_per_sec

        @property
        def stop_reason(self) -> Optional[str]:
            return self._span.stop_reason

        @property
        def total_tokens(self) -> Optional[int]:
            return self._span.total_tokens

    def span(self, name: str, parent_id: Optional[str] = None) -> "Tracer.SpanContext":
        """Create a child span with a parent relationship."""
        parent = self._span_stack[-1] if self._span_stack else None
        span_id = f"span-{uuid.uuid4()}"
        span = Span(
            id=span_id,
            name=name,
            parent_id=parent_id or (parent.id if parent else None),
            start_time=time.time(),
        )
        self._spans.append(span)
        self._span_stack.append(span)
        if self._storage:
            self._storage.save(span)
        return Tracer.SpanContext(self, span)

    @property
    def spans(self) -> List[Span]:
        return list(self._spans)

    @property
    def root_spans(self) -> List[Span]:
        """Return spans that have no parent."""
        return [s for s in self._spans if s.parent_id is None]

    def _maybe_flush(self) -> None:
        """Persist spans to storage if available."""
        pass

    def end(self) -> None:
        """Close the tracer."""
        self._closed = True
        for span in self._spans:
            if span.end_time == 0.0:
                span.end_time = time.time()
            if span.status == SpanStatus.OK:
                span.status = SpanStatus.OK
        if self._storage:
            self._storage.save_all(self._spans)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()
        return False


def trace(name: str, inputs: Optional[Any] = None):
    """Convenience function: `with trace("agent"): run_agent()`"""
    tracer = Tracer()
    return tracer.trace(name, inputs)


__all__ = ["trace", "Tracer", "Span", "SpanStatus", "trace"]