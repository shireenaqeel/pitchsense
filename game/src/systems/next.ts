// Scoring for What Happens Next?: calling what the real player did is the full
// score; calling what most players do from that spot, when this one did
// something else, is half, because it's a sound read of the picture.

import type { Moment } from "../data/types";

export const NEXT_ROUND = 8;
export const NEXT_EXACT = 100;
export const NEXT_COMMON = 50;

export type NextVerdict = "exact" | "common" | "miss";

/** The call real players make most often from this moment's zone. */
export function commonCall(rates: number[]): number {
  return rates.reduce((best, r, i) => (r > rates[best] ? i : best), 0);
}

export function judgeNext(moment: Moment, pick: number): { verdict: NextVerdict; points: number } {
  if (pick === moment.call) return { verdict: "exact", points: NEXT_EXACT };
  if (pick === commonCall(moment.rates)) return { verdict: "common", points: NEXT_COMMON };
  return { verdict: "miss", points: 0 };
}

/** `n` moments for a round, spread across the four calls so no call dominates. */
export function pickMoments(moments: Moment[], rand: () => number, n = NEXT_ROUND): Moment[] {
  const pool = [...moments];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  const out: Moment[] = [];
  for (let call = 0; out.length < n && pool.length; call = (call + 1) % 4) {
    const k = pool.findIndex((m) => m.call === call);
    out.push(...pool.splice(k >= 0 ? k : 0, 1));
  }
  // Shuffle again so the calls don't come round in a fixed order.
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
