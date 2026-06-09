import type { FileClassification, SessionData, Summary } from "./types";

const BASE = "/api";

export async function getSession(): Promise<SessionData> {
  const r = await fetch(`${BASE}/session`);
  if (!r.ok) throw new Error(`Failed to load session: ${r.status}`);
  return r.json();
}

export async function getSummary(): Promise<Summary> {
  const r = await fetch(`${BASE}/summary`);
  if (!r.ok) throw new Error(`Failed to load summary: ${r.status}`);
  return r.json();
}

export async function submitDecision(
  fileId: string,
  decision: "accepted" | "rejected",
  finalContent: string,
): Promise<void> {
  const r = await fetch(`${BASE}/files/${fileId}/decision`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, final_content: finalContent }),
  });
  if (!r.ok) throw new Error(`Failed to submit decision: ${r.status}`);
}

export async function overrideClassification(
  fileId: string,
  cls: FileClassification | "",
): Promise<void> {
  const r = await fetch(`${BASE}/files/${fileId}/classification`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_classification: cls }),
  });
  if (!r.ok) throw new Error(`Failed to override classification: ${r.status}`);
}

export async function resetAll(): Promise<void> {
  const r = await fetch(`${BASE}/reset`, { method: "POST" });
  if (!r.ok) throw new Error(`Failed to reset: ${r.status}`);
}

export async function createPR(): Promise<{
  pr_url?: string;
  committed?: number;
  skipped?: string[];
  error?: string;
}> {
  const r = await fetch(`${BASE}/create-pr`, { method: "POST" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `PR creation failed: ${r.status}`);
  }
  return r.json();
}
