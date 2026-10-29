import { describe, expect, it } from "vitest";

import { lessonById, type Mark, type Pt } from "../src/academy/curriculum";
import { pickCalls, REF_CALLS } from "../src/academy/referee";
import type { Moment } from "../src/data/types";
import { commonCall, judgeNext, NEXT_COMMON, NEXT_EXACT, pickMoments } from "../src/systems/next";

function points(m: Mark): Pt[] {
  if (m.kind === "arrow") return [m.from, m.to];
  if (m.kind === "cone") return [m.from];
  if (m.kind === "zone") return [[m.x[0], m.y[0]], [m.x[1], m.y[1]]];
  if (m.kind === "line") return [[m.x, 40]];
  return [m.at];
}

/** A seeded generator, so the shuffles are repeatable. */
function seeded(seed: number): () => number {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

describe("referee's eye", () => {
  it("has unique ids, a valid answer and a real lesson for every call", () => {
    expect(new Set(REF_CALLS.map((c) => c.id)).size).toBe(REF_CALLS.length);
    for (const c of REF_CALLS) {
      expect(c.answer, c.id).toBeGreaterThanOrEqual(0);
      expect(c.answer, c.id).toBeLessThan(c.options.length);
      expect(c.options.length, c.id).toBeLessThanOrEqual(3);
      expect(lessonById(c.lesson), c.id).toBeDefined();
    }
  });

  it("draws every call inside the view it uses", () => {
    const xMin = { half: 60, box: 84, full: 0 };
    for (const c of REF_CALLS) {
      for (const m of c.marks) {
        for (const [x, y] of points(m)) {
          expect(x, `${c.id} ${m.kind}`).toBeGreaterThanOrEqual(xMin[c.view]);
          expect(x, `${c.id} ${m.kind}`).toBeLessThanOrEqual(121);
          expect(y, `${c.id} ${m.kind}`).toBeGreaterThanOrEqual(0);
          expect(y, `${c.id} ${m.kind}`).toBeLessThanOrEqual(80);
        }
      }
    }
  });

  it("deals a round of different calls", () => {
    const round = pickCalls(seeded(1), 8);
    expect(round).toHaveLength(8);
    expect(new Set(round.map((c) => c.id)).size).toBe(8);
  });
});

const moment = (call: number, rates: number[], id = "m"): Moment => ({
  id, match: 1, minute: 10, player: "P", team: "T", call, x: 100, y: 40, frame: [], before: [], after: [],
  outcome: "no shot", rates,
});

describe("what happens next", () => {
  it("finds the most common call from the zone's rates", () => {
    expect(commonCall([0.1, 0.6, 0.2, 0.1])).toBe(1);
    expect(commonCall([0.4, 0.4, 0.1, 0.1])).toBe(0);
  });

  it("pays in full for the real call and half for the common one", () => {
    const m = moment(2, [0.1, 0.6, 0.2, 0.1]);
    expect(judgeNext(m, 2)).toEqual({ verdict: "exact", points: NEXT_EXACT });
    expect(judgeNext(m, 1)).toEqual({ verdict: "common", points: NEXT_COMMON });
    expect(judgeNext(m, 0)).toEqual({ verdict: "miss", points: 0 });
  });

  it("deals a round spread across all four calls", () => {
    const pool = Array.from({ length: 40 }, (_, i) => moment(i % 4, [0.25, 0.25, 0.25, 0.25], `m${i}`));
    const round = pickMoments(pool, seeded(3), 8);
    expect(new Set(round.map((m) => m.id)).size).toBe(8);
    for (let call = 0; call < 4; call++) expect(round.filter((m) => m.call === call)).toHaveLength(2);
  });

  it("copes with a pool smaller than a round", () => {
    expect(pickMoments([moment(0, [1, 0, 0, 0])], seeded(5), 8)).toHaveLength(1);
  });
});
