import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

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
}

interface RootSpan extends SpanInfo {
  children?: RootSpan[];
}

export default function TraceListPage() {
  const [spans, setSpans] = useState<RootSpan[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    fetchSpans();

    // Set up WebSocket for live updates
    const ws = new WebSocket("ws://localhost:18003/ws");
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "spans_update") {
        setSpans(data.spans);
      }
    };

    return () => {
      ws.close();
    };
  }, [navigate]);

  const fetchSpans = async () => {
    try {
      const resp = await fetch("http://localhost:18003/api/spans");
      const data = await resp.json();
      setSpans(data);
    } catch (e) {
      console.error("Failed to fetch spans:", e);
    } finally {
      setLoading(false);
    }
  };

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
      <div>
        <h2>Loading traces...</h2>
      </div>
    );
  }

  const tree = buildTree(spans);

  return (
    <div>
      <h2>Traces</h2>

      {tree.map((root) => (
        <div key={root.id} style={{ display: "flex", alignItems: "center", padding: "0.5rem 0", borderBottom: "1px solid #30363d" }}>
          <div className="span-name" style={{ flex: 1 }}>
            <a href={`/trace/${root.id}`}>{root.name}</a>
          </div>
          <div style={{ flex: 0, width: "200px", fontSize: "0.75rem", color: "#6e7681", whiteSpace: "nowrap" }}>
            {root.id.substring(0, 16)}...
          </div>
          <span style={{ flex: 0, width: "60px", fontSize: "0.75rem", fontWeight: "500", textAlign: "center", color: "#43b581" }}>{root.status}</span>
        </div>
      ))}

      {tree.map((root) => {
        if (root.children) {
          return root.children.map((child) => (
            <div key={child.id} style={{ display: "flex", alignItems: "center", padding: "0.5rem 0" }}>
              <div className="span-name" style={{ flex: 1 }}>
                <a href={`/trace/${child.id}`}>{child.name}</a>
              </div>
              <div style={{ flex: 0, width: "200px", fontSize: "0.75rem", color: "#6e7681", whiteSpace: "nowrap" }}>
                {child.id.substring(0, 16)}...
              </div>
              <span style={{ flex: 0, width: "60px", fontSize: "0.75rem", fontWeight: "500", textAlign: "center", color: "#43b581" }}>{child.status}</span>
            </div>
          ));
        }
        return null;
      })}

    </div>
  );
}