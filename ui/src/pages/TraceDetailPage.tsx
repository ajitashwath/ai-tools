import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

const API_BASE = "http://127.0.0.1:18003";

interface SpanInfo {
  id: string;
  name: string;
  parent_id: string | null;
  start_time: number;
  end_time: number | null;
  status: string;
  metadata: Record<string, any>;
  errors: string[];
  inputs: any;
  outputs: any;
  model: string | null;
  model_token_count: number | null;
  operation: string | null;
  ttft: number | null;
  tokens_per_sec: number | null;
  stop_reason: string | null;
  total_tokens: number | null;
}

export default function TraceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [span, setSpan] = useState<SpanInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;

    // Fetch span from API
    fetch(`${API_BASE}/api/spans/${id}`)
      .then((resp) => resp.json())
      .then((data: SpanInfo) => {
        setSpan(data);
        setLoading(false);
      })
      .catch((e) => {
        console.error("Failed to fetch span:", e);
        setLoading(false);
      });
  }, [id]);

  if (loading || !span) {
    return (
      <div className="trace-detail">
        <h1>Trace Detail</h1>
        <p>Loading trace...</p>
      </div>
    );
  }

  // Calculate duration
  const duration = span.end_time ? (span.end_time - span.start_time).toFixed(2) : "—";

  return (
    <div className="trace-detail">
      <Link className="back-link" to="/">← All traces</Link>
      <h1>{span.name}</h1>

      <div className="trace-meta">
        <div>
          <span className="key">ID</span>
          <span>{span.id}</span>
        </div>
        <div>
          <span className="key">Status</span>
          <span>{span.status}</span>
        </div>
        <div>
          <span className="key">Duration</span>
          <span>{duration}s</span>
        </div>
        <div>
          <span className="key">Model</span>
          <span>{span.model || "—"}</span>
        </div>
        <div>
          <span className="key">Tokens</span>
          <span>{span.model_token_count || "—"}</span>
        </div>
        <div>
          <span className="key">Operation</span>
          <span>{span.operation || "—"}</span>
        </div>
        <div>
          <span className="key">TTFT</span>
          <span>{span.ttft !== null ? `${span.ttft.toFixed(2)}s` : "—"}</span>
        </div>
        <div>
          <span className="key">Throughput</span>
          <span>{span.tokens_per_sec !== null ? `${span.tokens_per_sec.toFixed(1)} tok/s` : "—"}</span>
        </div>
        <div>
          <span className="key">Total tokens</span>
          <span>{span.total_tokens ?? "—"}</span>
        </div>
      </div>

      {span.inputs !== undefined && span.inputs !== null && (
        <div className="trace-meta">
          <div>
            <span className="key">Inputs</span>
            <span>{JSON.stringify(span.inputs).substring(0, 200)}{JSON.stringify(span.inputs).length > 200 ? "..." : ""}</span>
          </div>
        </div>
      )}

      {span.outputs !== undefined && span.outputs !== null && (
        <div className="trace-meta">
          <div>
            <span className="key">Outputs</span>
            <span>{JSON.stringify(span.outputs).substring(0, 200)}{JSON.stringify(span.outputs).length > 200 ? "..." : ""}</span>
          </div>
        </div>
      )}

      {span.errors.length > 0 && (
        <div className="trace-errors">
          <h3>Errors</h3>
          {span.errors.map((err, i) => (
            <div key={i} className="error-item">{err}</div>
          ))}
        </div>
      )}

      {Object.keys(span.metadata).length > 0 && (
        <div className="trace-metadata">
          <h3>Metadata</h3>
          {Object.entries(span.metadata).map(([key, value]) => (
            <div key={key} className="metadata-row">
              <span className="metadata-key">{key}</span>
              <span className="metadata-value">{String(value).substring(0, 100)}{String(value).length > 100 ? "..." : ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
