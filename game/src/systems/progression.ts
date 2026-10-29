// Scout level, rank title and coins.

export const RANKS = [
  "Sunday League Scout",
  "Academy Scout",
  "Lower League Scout",
  "Top-Flight Scout",
  "International Scout",
  "Chief Scout",
  "Legendary Scout",
];

/** Levels between rank promotions. */
export const LEVELS_PER_RANK = 5;

export function xpToNext(level: number): number {
  return 100 + 40 * (level - 1);
}

export interface LevelInfo {
  level: number;
  /** XP earned inside the current level. */
  into: number;
  /** XP the current level needs in total. */
  needed: number;
}

export function levelFromXp(xp: number): LevelInfo {
  let level = 1;
  let left = Math.max(0, Math.floor(xp));
  while (left >= xpToNext(level)) {
    left -= xpToNext(level);
    level += 1;
  }
  return { level, into: left, needed: xpToNext(level) };
}

export function rankFor(level: number): string {
  return RANKS[Math.min(Math.floor((level - 1) / LEVELS_PER_RANK), RANKS.length - 1)];
}

export function xpForPoints(points: number): number {
  return Math.round(points / 5);
}

export function coinsForPoints(points: number): number {
  return Math.floor(points / 25);
}
