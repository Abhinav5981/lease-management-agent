import type { Building, Lease, MaintenanceRequest, Tenant, Unit } from "@/types";

const BASE = "/api/v1";

async function get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── Buildings ──────────────────────────────────────────────────────────────

export const getBuildings = () => get<Building[]>("/buildings");

// ── Units ──────────────────────────────────────────────────────────────────

export const getUnits = (params?: { status?: string }) =>
  get<Unit[]>("/units", params as Record<string, string>);

// ── Tenants ───────────────────────────────────────────────────────────────

export const getTenants = () => get<Tenant[]>("/tenants");

// ── Leases ────────────────────────────────────────────────────────────────

export const getLeases = (params?: { status?: string; limit?: number }) =>
  get<Lease[]>("/leases", params as Record<string, string>);

export const getExpiringLeases = (days = 90) =>
  get<Lease[]>("/leases/expiring", { days });

// ── Maintenance ───────────────────────────────────────────────────────────

export const getMaintenance = (params?: { status?: string; limit?: number }) =>
  get<MaintenanceRequest[]>("/maintenance", params as Record<string, string>);

// ── Agent / Chat ──────────────────────────────────────────────────────────

export async function sendMessage(message: string, threadId: string): Promise<string> {
  const res = await fetch(`${BASE}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const data = await res.json();
  return data.response as string;
}

export async function streamMessage(
  message: string,
  threadId: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${BASE}/agent/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  });

  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const json = line.slice(6).trim();
        if (!json) continue;
        try {
          const event = JSON.parse(json) as { type: string; data: string };
          if (event.type === "chunk") onChunk(event.data);
          else if (event.type === "done") onDone();
          else if (event.type === "error") onError(event.data);
        } catch {
          // skip malformed SSE lines
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
