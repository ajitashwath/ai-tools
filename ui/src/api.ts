// Shared API configuration and types for the AI DevTools dashboard.
// The FastAPI backend serves on 18003 (see aidev/server.py API_PORT);
// the Vite dev server itself runs on 5174.

export const API_BASE = "http://127.0.0.1:18003";
export const WS_URL = "ws://127.0.0.1:18003/ws";

export interface SpanInfo {
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

export async function fetchSpans(): Promise<SpanInfo[]> {
  const resp = await fetch(`${API_BASE}/api/spans`);
  if (!resp.ok) throw new Error(`API returned ${resp.status}`);
  return resp.json();
}

export async function fetchSpan(id: string): Promise<SpanInfo> {
  const resp = await fetch(`${API_BASE}/api/spans/${id}`);
  if (!resp.ok) throw new Error(`API returned ${resp.status}`);
  return resp.json();
}
