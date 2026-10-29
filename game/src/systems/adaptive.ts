// Weak-spot practice, ported from `pitchsense/concepts.py`: shots that carry
// the concepts you read worst are served more often.

import type { Rng } from "./rng";

export interface ConceptRecord {
  attempts: number;
  points: number;
}
export type ConceptProgress = Record<string, ConceptRecord>;

export function updateProgress(progress: ConceptProgress, concepts: string[], points: number): void {
  for (const c of concepts) {
    const r = (progress[c] ??= { attempts: 0, points: 0 });
    r.attempts += 1;
    r.points += points;
  }
}

/** Average base points (0-100) per concept that has been attempted. */
export function conceptScores(progress: ConceptProgress): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [c, r] of Object.entries(progress)) if (r.attempts > 0) out[c] = r.points / r.attempts;
  return out;
}

export function conceptWeights(
  progress: ConceptProgress,
  all: string[],
  floor = 0.1,
  explore = 1.5,
): Record<string, number> {
  const w: Record<string, number> = {};
  for (const c of all) {
    const r = progress[c];
    w[c] = !r || r.attempts === 0 ? explore : floor + (1 - r.points / r.attempts / 100);
  }
  return w;
}

/** Inverse-sqrt band weights so long shots (half the pool) do not dominate. */
export function bandBalance(bands: number[], nBands = 5): number[] {
  const counts = new Array(nBands).fill(0);
  for (const b of bands) counts[b] += 1;
  return bands.map((b) => 1 / Math.sqrt(counts[b]));
}

/** Weighted-random pick; `exclude` holds indices already seen. */
export function pickAdaptive(
  conceptsPerShot: string[][],
  weights: Record<string, number>,
  rng: Rng,
  boost?: number[],
  exclude: Set<number> = new Set(),
): number {
  const w = conceptsPerShot.map((cs, i) => {
    if (exclude.has(i) && exclude.size < conceptsPerShot.length) return 0;
    const need = Math.max(...cs.map((c) => weights[c] ?? 1));
    return need * (boost ? boost[i] : 1);
  });
  const total = w.reduce((a, b) => a + b, 0);
  if (total <= 0) return Math.floor(rng() * conceptsPerShot.length);
  let r = rng() * total;
  for (let i = 0; i < w.length; i++) {
    r -= w[i];
    if (r < 0) return i;
  }
  return w.length - 1;
}
