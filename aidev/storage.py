"""SQLite persistence for trace spans."""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from aidev.trace import Span, SpanStatus


class TraceSQLite:
    """Persistence layer using SQLite for trace spans."""

    def __init__(self, db_path: str = "traces.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_id TEXT,
                start_time REAL NOT NULL,
                end_time REAL,
                status TEXT NOT NULL,
                metadata TEXT,
                errors TEXT,
                inputs TEXT,
                outputs TEXT,
                model TEXT,
                model_token_count INTEGER,
                operation TEXT,
                ttft REAL,
                tokens_per_sec REAL,
                stop_reason TEXT,
                total_tokens INTEGER
            )
            """
        )
        self._conn.commit()

    def save(self, span: Span) -> None:
        """Save a single span to SQLite."""
        metadata_json = json.dumps(span.metadata) if span.metadata else None
        errors_json = json.dumps(span.errors) if span.errors else None
        inputs_json = json.dumps(span.inputs) if span.inputs is not None else None
        outputs_json = json.dumps(span.outputs) if span.outputs is not None else None

        self._conn.execute(
            """
            INSERT OR REPLACE INTO spans
            (id, name, parent_id, start_time, end_time, status, metadata, errors, inputs, outputs, model, model_token_count, operation, ttft, tokens_per_sec, stop_reason, total_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span.id,
                span.name,
                span.parent_id,
                span.start_time,
                span.end_time,
                span.status.value,
                metadata_json,
                errors_json,
                inputs_json,
                outputs_json,
                span.model,
                span.model_token_count,
                span.operation,
                span.ttft,
                span.tokens_per_sec,
                span.stop_reason,
                span.total_tokens,
            ),
        )
        self._conn.commit()

    def save_all(self, spans: List[Span]) -> None:
        """Save multiple spans."""
        for span in spans:
            self.save(span)

    def get_by_id(self, span_id: str) -> Optional[Span]:
        """Retrieve a span by ID."""
        row = self._conn.execute(
            "SELECT id, name, parent_id, start_time, end_time, status, metadata, errors, inputs, outputs, model, model_token_count, operation, ttft, tokens_per_sec, stop_reason, total_tokens FROM spans WHERE id = ?",
            (span_id,),
        ).fetchone()
        if row is None:
            return None
        return Span(
            id=row[0],
            name=row[1],
            parent_id=row[2],
            start_time=row[3],
            end_time=row[4],
            status=SpanStatus(row[5]),
            metadata=json.loads(row[6]) if row[6] else {},
            errors=json.loads(row[7]) if row[7] else [],
            inputs=json.loads(row[8]) if row[8] else None,
            outputs=json.loads(row[9]) if row[9] else None,
            model=row[10],
            model_token_count=row[11],
            operation=row[12],
            ttft=row[13],
            tokens_per_sec=row[14],
            stop_reason=row[15],
            total_tokens=row[16],
        )

    def get_root_spans(self) -> List[Span]:
        """Retrieve all root spans (no parent)."""
        rows = self._conn.execute(
            "SELECT id, name, parent_id, start_time, end_time, status, metadata, errors, inputs, outputs, model, model_token_count, operation, ttft, tokens_per_sec, stop_reason, total_tokens FROM spans WHERE parent_id IS NULL ORDER BY start_time"
        ).fetchall()
        return [
            Span(
                id=row[0],
                name=row[1],
                parent_id=row[2],
                start_time=row[3],
                end_time=row[4],
                status=SpanStatus(row[5]),
                metadata=json.loads(row[6]) if row[6] else {},
                errors=json.loads(row[7]) if row[7] else [],
                inputs=json.loads(row[8]) if row[8] else None,
                outputs=json.loads(row[9]) if row[9] else None,
                model=row[10],
                model_token_count=row[11],
                operation=row[12],
                ttft=row[13],
                tokens_per_sec=row[14],
                stop_reason=row[15],
                total_tokens=row[16],
            )
            for row in rows
        ]

    def get_children(self, parent_id: str) -> List[Span]:
        """Retrieve child spans for a given parent ID."""
        rows = self._conn.execute(
            "SELECT id, name, parent_id, start_time, end_time, status, metadata, errors, inputs, outputs, model, model_token_count, operation, ttft, tokens_per_sec, stop_reason, total_tokens FROM spans WHERE parent_id = ? ORDER BY start_time",
            (parent_id,),
        ).fetchall()
        return [
            Span(
                id=row[0],
                name=row[1],
                parent_id=row[2],
                start_time=row[3],
                end_time=row[4],
                status=SpanStatus(row[5]),
                metadata=json.loads(row[6]) if row[6] else {},
                errors=json.loads(row[7]) if row[7] else [],
                inputs=json.loads(row[8]) if row[8] else None,
                outputs=json.loads(row[9]) if row[9] else None,
                model=row[10],
                model_token_count=row[11],
                operation=row[12],
                ttft=row[13],
                tokens_per_sec=row[14],
                stop_reason=row[15],
                total_tokens=row[16],
            )
            for row in rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None