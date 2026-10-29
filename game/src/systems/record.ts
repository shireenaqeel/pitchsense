// Folding a finished round, match or run into the save.

import { updateProgress } from "./adaptive";
import { levelKey } from "./career";
import { coinsForPoints, xpForPoints } from "./progression";
import { isNextDay } from "./rng";
import type { RoundResult } from "./scoring";
import type { SaveData } from "./save";

export interface Reward {
  xp: number;
  coins: number;
}

/** One read: stats, concept progress (on base points, as in the Python quiz) and rewards. */
export function recordRead(
  save: SaveData,
  concepts: string[],
  modelBand: number,
  result: RoundResult,
  elapsedMs: number,
): Reward {
  const s = save.stats;
  s.reads += 1;
  s.bestCombo = Math.max(s.bestCombo, result.combo);
  if (result.grade === "exact") {
    s.exact += 1;
    s.bandExact[modelBand] = (s.bandExact[modelBand] ?? 0) + 1;
    for (const c of concepts) s.conceptExact[c] = (s.conceptExact[c] ?? 0) + 1;
    if (s.fastestExactMs === null || elapsedMs < s.fastestExactMs) s.fastestExactMs = elapsedMs;
  }
  if (result.grade !== "timeout") updateProgress(save.concepts, concepts, result.base);
  const reward = { xp: xpForPoints(result.total), coins: coinsForPoints(result.total) };
  save.xp += reward.xp;
  save.coins += reward.coins;
  return reward;
}

export const STAR_COINS = 20;
export const TROPHY_COINS = 250;
export const TROPHY_XP = 400;

/** A finished career match. Stars only ever go up. */
export function recordMatch(
  save: SaveData,
  world: number,
  level: number,
  stars: number,
  flawless: boolean,
  trophy: string | null,
): Reward {
  const key = levelKey(world, level);
  const before = save.career[key] ?? 0;
  const reward = { xp: 0, coins: 0 };
  if (stars > before) {
    save.career[key] = stars;
    reward.coins += (stars - before) * STAR_COINS;
  }
  if (stars > 0 && flawless) save.stats.flawlessMatches += 1;
  if (stars === 3) save.stats.threeStarMatches += 1;
  if (trophy && stars > 0) {
    save.stats.bossesBeaten += 1;
    if (!save.trophies.includes(trophy)) {
      save.trophies.push(trophy);
      reward.coins += TROPHY_COINS;
      reward.xp += TROPHY_XP;
    }
  }
  save.coins += reward.coins;
  save.xp += reward.xp;
  return reward;
}

/** A finished daily. Only the first attempt each day counts and builds the streak. */
export function recordDaily(save: SaveData, key: string, score: number): boolean {
  if (key in save.daily.scores) return false;
  const d = save.daily;
  d.scores[key] = score;
  d.streak = d.last && isNextDay(d.last, key) ? d.streak + 1 : 1;
  d.bestStreak = Math.max(d.bestStreak, d.streak);
  d.last = key;
  return true;
}

export function recordRapid(save: SaveData, score: number): boolean {
  if (score <= save.rapidBest) return false;
  save.rapidBest = score;
  return true;
}

export function recordPuzzle(save: SaveData, name: string, stars: number): boolean {
  if (stars <= (save.puzzles[name] ?? 0)) return false;
  save.puzzles[name] = stars;
  return true;
}
