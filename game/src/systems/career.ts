// Career rules: hearts, stars, the boss fight, and what is unlocked.

import type { Grade } from "./scoring";

export const HEARTS = 3;
export const ROUND_MS = 10_000;
export const BOSS_ROUND_MS = 7_000;
/** Boss HP per shot in the final: you need to average well over a near read. */
export const BOSS_HP_PER_SHOT = 80;

export function heartsLost(g: Grade): number {
  return g === "miss" || g === "timeout" ? 1 : 0;
}

export function bossHp(nShots: number): number {
  return BOSS_HP_PER_SHOT * nShots;
}

/**
 * Stars for a finished match from the average *base* points (speed and combos
 * do not count, so stars measure reading, not reflexes). A match you ran out
 * of hearts in, or a final whose boss survived, earns none.
 */
export function matchStars(avgBase: number, cleared: boolean): 0 | 1 | 2 | 3 {
  if (!cleared) return 0;
  if (avgBase >= 85) return 3;
  if (avgBase >= 70) return 2;
  return 1;
}

export type StarMap = Record<string, number>;

export function levelKey(world: number, level: number): string {
  return `${world}-${level}`;
}

/**
 * First level of the first world is always open. Inside a world, a level opens
 * when the previous one has a star; a world opens when the previous world's
 * final has been won.
 */
export function isUnlocked(stars: StarMap, levelsPerWorld: number[], world: number, level: number): boolean {
  if (level > 0) return (stars[levelKey(world, level - 1)] ?? 0) > 0;
  if (world === 0) return true;
  const prevFinal = levelsPerWorld[world - 1] - 1;
  return (stars[levelKey(world - 1, prevFinal)] ?? 0) > 0;
}

export function worldStars(stars: StarMap, world: number, nLevels: number): number {
  let total = 0;
  for (let l = 0; l < nLevels; l++) total += stars[levelKey(world, l)] ?? 0;
  return total;
}

/** Striker puzzle stars: how close your spot came to the best reachable xG. */
export function puzzleStars(xg: number, best: number): 0 | 1 | 2 | 3 {
  const ratio = best > 0 ? xg / best : 0;
  if (ratio >= 0.95) return 3;
  if (ratio >= 0.8) return 2;
  if (ratio >= 0.6) return 1;
  return 0;
}
