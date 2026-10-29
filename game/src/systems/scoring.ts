// Round scoring: how well you read a chance, how fast, and how many in a row.
//
// The base points mirror the Python quiz's beginner scoring (`bucket_points`):
// name the same chance band as the model for 100, a neighbouring band for 50.
// Everything on top (speed, combos) is pure game feel and never changes what
// counts as a correct read.

export type Grade = "exact" | "near" | "miss" | "timeout";

export const EXACT_POINTS = 100;
export const NEAR_POINTS = 50;
export const MAX_SPEED_BONUS = 25;

export function grade(guess: number | null, modelBand: number): Grade {
  if (guess === null) return "timeout";
  const gap = Math.abs(guess - modelBand);
  if (gap === 0) return "exact";
  if (gap === 1) return "near";
  return "miss";
}

export function basePoints(g: Grade): number {
  return g === "exact" ? EXACT_POINTS : g === "near" ? NEAR_POINTS : 0;
}

/** Up to 25 bonus points for answering early; nothing for a wrong read. */
export function speedBonus(g: Grade, elapsedMs: number, limitMs: number): number {
  if (g !== "exact" && g !== "near") return 0;
  const left = 1 - Math.min(Math.max(elapsedMs / limitMs, 0), 1);
  const bonus = Math.round(MAX_SPEED_BONUS * left);
  return g === "exact" ? bonus : Math.round(bonus / 2);
}

/** Exact reads build the combo, near reads hold it, anything else breaks it. */
export function nextCombo(combo: number, g: Grade): number {
  if (g === "exact") return combo + 1;
  if (g === "near") return combo;
  return 0;
}

export function comboMultiplier(combo: number): number {
  if (combo >= 6) return 2;
  if (combo >= 4) return 1.5;
  if (combo >= 2) return 1.25;
  return 1;
}

export interface RoundResult {
  grade: Grade;
  base: number;
  speed: number;
  combo: number;
  multiplier: number;
  total: number;
}

/** Score one read. `combo` is the streak *before* this round. */
export function scoreRound(
  guess: number | null,
  modelBand: number,
  elapsedMs: number,
  limitMs: number,
  combo: number,
): RoundResult {
  const g = grade(guess, modelBand);
  const base = basePoints(g);
  const speed = speedBonus(g, elapsedMs, limitMs);
  const newCombo = nextCombo(combo, g);
  const multiplier = comboMultiplier(newCombo);
  return { grade: g, base, speed, combo: newCombo, multiplier, total: Math.round((base + speed) * multiplier) };
}

/** Wordle-style square for the shareable daily result. */
export function gradeSquare(g: Grade): string {
  return g === "exact" ? "🟩" : g === "near" ? "🟨" : "🟥";
}
