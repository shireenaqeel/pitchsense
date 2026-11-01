import { describe, expect, it } from "vitest";

import { boardConfig, boardQuery, cleanName, fetchBoard, postScore, type PendingScore } from "../src/systems/leaderboard";
import { defaultSave, loadSave } from "../src/systems/save";

type Call = { url: string; init: RequestInit };

function fakeFetch(body: unknown, status = 200) {
  const calls: Call[] = [];
  const fn = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(body), { status });
  }) as unknown as typeof fetch;
  return { fn, calls };
}

const cfg = boardConfig("https://abc.supabase.co/rest/v1/", "sb_publishable_x")!;

describe("leaderboard settings", () => {
  it("is off without both settings, or with a malformed URL", () => {
    expect(boardConfig(undefined, "k")).toBeNull();
    expect(boardConfig("https://abc.supabase.co", "")).toBeNull();
    expect(boardConfig("not a url", "k")).toBeNull();
  });

  it("keeps only the project's origin, however the URL was copied", () => {
    for (const url of ["https://abc.supabase.co", "https://abc.supabase.co/", " https://abc.supabase.co/rest/v1/ "]) {
      expect(boardConfig(url, "k")!.endpoint).toBe("https://abc.supabase.co/rest/v1/game_scores");
    }
  });

  it("sends a publishable key alone and a legacy key as a bearer token too", () => {
    expect(cfg.headers).toEqual({ apikey: "sb_publishable_x" });
    expect(boardConfig("https://abc.supabase.co", "eyJ.legacy.jwt")!.headers.Authorization).toBe("Bearer eyJ.legacy.jwt");
  });
});

describe("names", () => {
  it("strips control and invisible characters and caps the length, like the app", () => {
    expect(cleanName("  Ada‮​  \n Lovelace\x00 ")).toBe("Ada Lovelace");
    expect(cleanName("​\t")).toBe("Anonymous");
    expect(cleanName(undefined)).toBe("Anonymous");
    expect([...cleanName("x".repeat(100))].length).toBe(20);
    expect(cleanName("Zoë ⚽ Ünal")).toBe("Zoë ⚽ Ünal");
  });
});

describe("boards", () => {
  it("asks for today's daily, best first, earliest post winning ties", () => {
    const q = boardQuery("daily", "2026-11-01");
    expect(q.get("mode")).toBe("eq.daily");
    expect(q.get("day")).toBe("eq.2026-11-01");
    expect(q.get("order")).toBe("score.desc,created_at.asc");
    expect(q.get("limit")).toBe("10");
    expect(boardQuery("rapid", null).has("day")).toBe(false);
  });

  it("reads rows from the table", async () => {
    const { fn, calls } = fakeFetch([{ name: "Ana", score: 1840, reads: 10 }]);
    expect(await fetchBoard(cfg, "daily", "2026-11-01", fn)).toEqual([{ name: "Ana", score: 1840, reads: 10 }]);
    expect(calls[0].url.startsWith("https://abc.supabase.co/rest/v1/game_scores?")).toBe(true);
  });

  it("fails loudly when the table is unreachable", async () => {
    const { fn } = fakeFetch({ message: "down" }, 503);
    await expect(fetchBoard(cfg, "rapid", null, fn)).rejects.toThrow("503");
  });

  it("posts a cleaned name, and a daily's day but never a rapid one's", async () => {
    const { fn, calls } = fakeFetch(null, 201);
    const daily: PendingScore = { mode: "daily", day: "2026-11-01", score: 1840, reads: 10 };
    await postScore(cfg, " Ana​ ", daily, fn);
    await postScore(cfg, "Ben", { mode: "rapid", day: "2026-11-01", score: 3125, reads: 24 }, fn);
    const [first, second] = calls.map((c) => JSON.parse(String(c.init.body)));
    expect(first).toEqual({ mode: "daily", day: "2026-11-01", name: "Ana", score: 1840, reads: 10 });
    expect(second.day).toBeNull();
    expect((calls[0].init.headers as Record<string, string>).Prefer).toBe("return=minimal");
    expect(calls[0].init.method).toBe("POST");
  });
});

describe("save", () => {
  it("remembers the leaderboard name, and old saves load without one", () => {
    expect(defaultSave().playerName).toBe("");
    const old = { getItem: () => JSON.stringify({ version: 1, xp: 50 }), setItem: () => undefined };
    expect(loadSave(old).playerName).toBe("");
  });
});
