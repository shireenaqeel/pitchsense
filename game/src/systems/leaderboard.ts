// The shared leaderboards: today's Daily Challenge and Rapid Fire of all time.
//
// Scores live in a Supabase table (supabase/game_scores.sql), reached over its
// REST API with the project's publishable key. The key is built into the page,
// as a browser game's must be, so the table's own rules do the protecting:
// read and insert only, checked values, and a throttle. A build without the
// settings (local dev, pull requests) simply shows the boards as offline.

export type BoardMode = "daily" | "rapid";

export interface BoardRow {
  name: string;
  score: number;
  reads: number;
}

/** A finished run the player may post: the counted daily, or a Rapid Fire best. */
export interface PendingScore {
  mode: BoardMode;
  /** The daily's date key (YYYY-MM-DD); null for Rapid Fire. */
  day: string | null;
  score: number;
  reads: number;
}

export interface BoardConfig {
  endpoint: string;
  headers: Record<string, string>;
}

export const BOARD_SIZE = 10;
export const MAX_NAME = 20;
const TIMEOUT_MS = 6000;

/** Supabase settings from the build, or null when the boards are off. */
export function boardConfig(url: string | undefined, key: string | undefined): BoardConfig | null {
  if (!url || !key) return null;
  let origin: string;
  try {
    // The project URL is shown both bare and as its REST address; keep the origin.
    origin = new URL(url.trim()).origin;
  } catch {
    return null;
  }
  const headers: Record<string, string> = { apikey: key };
  // A legacy anon key is a JWT and goes in as a bearer token too.
  if (!key.startsWith("sb_")) headers.Authorization = `Bearer ${key}`;
  return { endpoint: `${origin}/rest/v1/game_scores`, headers };
}

export const CONFIG = boardConfig(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_KEY);

/** A display-safe name: no control or invisible characters, single spaces, at
 *  most MAX_NAME characters, "Anonymous" if nothing is left. Mirrors the app's. */
export function cleanName(raw: string | null | undefined): string {
  const text = (raw ?? "")
    .normalize("NFKC")
    .replace(/[\p{C}\p{Z}]/gu, (ch) => (ch === " " ? " " : ""))
    .replace(/\s+/g, " ")
    .trim();
  return [...text].slice(0, MAX_NAME).join("").trim() || "Anonymous";
}

/** The query for one board, best first; earlier posts win ties. */
export function boardQuery(mode: BoardMode, day: string | null): URLSearchParams {
  const q = new URLSearchParams({
    select: "name,score,reads",
    mode: `eq.${mode}`,
    order: "score.desc,created_at.asc",
    limit: String(BOARD_SIZE),
  });
  if (mode === "daily" && day) q.set("day", `eq.${day}`);
  return q;
}

type Fetch = typeof fetch;

async function request(fetchFn: Fetch, url: string, init: RequestInit): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetchFn(url, { ...init, signal: ctrl.signal });
    if (!res.ok) throw new Error(`leaderboard answered ${res.status}`);
    return res;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchBoard(cfg: BoardConfig, mode: BoardMode, day: string | null,
  fetchFn: Fetch = fetch): Promise<BoardRow[]> {
  const res = await request(fetchFn, `${cfg.endpoint}?${boardQuery(mode, day)}`, { headers: cfg.headers });
  const rows: unknown = await res.json();
  if (!Array.isArray(rows)) throw new Error("leaderboard answered with no rows");
  return rows.map((r) => ({ name: String(r.name), score: Number(r.score), reads: Number(r.reads) }));
}

export async function postScore(cfg: BoardConfig, name: string, p: PendingScore,
  fetchFn: Fetch = fetch): Promise<void> {
  const row = { mode: p.mode, day: p.mode === "daily" ? p.day : null, name: cleanName(name), score: p.score, reads: p.reads };
  await request(fetchFn, cfg.endpoint, {
    method: "POST",
    headers: { ...cfg.headers, "Content-Type": "application/json", Prefer: "return=minimal" },
    body: JSON.stringify(row),
  });
}
