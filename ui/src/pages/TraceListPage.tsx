import { useEffect, useState, type ReactElement } from "react";
import { Link } from "react-router-dom";

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

interface RootSpan extends SpanInfo {
  children?: RootSpan[];
}

export default function TraceListPage() {
  const [spans, setSpans] = useState<RootSpan[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState(false);

  async function fetchSpans() {
    try {
      const resp = await fetch(`${API_BASE}/api/spans`);
      if (!resp.ok) throw new Error(`API returned ${resp.status}`);
      const data = await resp.json();
      setSpans(data);
      setConnectionError(false);
    } catch (e) {
      console.error("Failed to fetch spans:", e);
      setConnectionError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const initialFetch = window.setTimeout(() => void fetchSpans(), 0);

    // Set up WebSocket for live updates
    const ws = new WebSocket("ws://127.0.0.1:18003/ws");
    ws.onopen = () => ws.send("get_spans");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "spans_update") {
        setSpans(data.spans);
        setConnectionError(false);
      }
    };

    const refresh = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("get_spans");
    }, 2000);

    return () => {
      window.clearTimeout(initialFetch);
      window.clearInterval(refresh);
      ws.close();
    };
  }, []);

  const buildTree = (spans: RootSpan[]): RootSpan[] => {
    const byId: Record<string, RootSpan> = {};
    const roots: RootSpan[] = [];

    // First pass: create all nodes
    for (const s of spans) {
      byId[s.id] = {
        ...s,
        children: [],
      };
    }

    // Second pass: assign children
    for (const s of spans) {
      const parentId = s.parent_id;
      if (parentId && byId[parentId]) {
        byId[parentId].children!.push(byId[s.id]);
      } else {
        roots.push(byId[s.id]);
      }
    }

    return roots;
  };

  if (loading) {
    return (
      <main className="app-shell"><div className="loading-state">Connecting to the trace server…</div></main>
    );
  }

  const tree = buildTree(spans);

  const renderSpan = (span: RootSpan, depth = 0): ReactElement[] => [
    <div className="trace-row" key={span.id}>
      <div className="trace-name" style={{ paddingLeft: `${depth * 22}px` }}>
        {depth > 0 && <span className="trace-branch" aria-hidden="true" />}
        <Link to={`/trace/${span.id}`}>{span.name}</Link>
      </div>
      <div className="trace-id">{span.id}</div>
      <span className={`trace-status ${span.status}`}>{span.status}</span>
    </div>,
    ...(span.children ?? []).flatMap((child) => renderSpan(child, depth + 1)),
  ];

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Local observability</p>
          <h1>AI DevTools</h1>
        </div>
        <p>Inspect every model run, tool call, error, and nested operation from one local trace.</p>
      </header>
      <section className="page-card" aria-labelledby="traces-heading">
        <div className="page-card-header">
          <h2 id="traces-heading">Traces</h2>
          <span>{tree.length} root {tree.length === 1 ? "trace" : "traces"}</span>
        </div>
        {connectionError && spans.length === 0 ? (
          <div className="empty-state">Trace server unavailable. Start FastAPI on 127.0.0.1:18003, then refresh.</div>
        ) : tree.length === 0 ? (
          <div className="empty-state">No traces yet. Run the demo seed script to create sample data.</div>
        ) : (
          <div className="trace-table">
            <div className="trace-table-head"><span>Name</span><span>Span ID</span><span>Status</span></div>
            {tree.flatMap((root) => renderSpan(root))}
          </div>
        )}
      </section>
    </main>
  );
}
