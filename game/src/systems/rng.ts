// Seeded randomness, so the daily challenge is the same shots for everyone.

export type Rng = () => number;

export function mulberry32(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashString(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Local calendar date as YYYY-MM-DD. */
export function dateKey(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const DAILY_EPOCH = Date.UTC(2026, 9, 22);

/** Puzzle number shown in the share text: #1 on launch day. */
export function dailyNumber(key: string): number {
  const [y, m, d] = key.split("-").map(Number);
  return Math.floor((Date.UTC(y, m - 1, d) - DAILY_EPOCH) / 86_400_000) + 1;
}

/** Whether `later` is the calendar day after `earlier`. */
export function isNextDay(earlier: string, later: string): boolean {
  return dailyNumber(later) - dailyNumber(earlier) === 1;
}

export function shuffle<T>(items: T[], rng: Rng): T[] {
  const out = items.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/**
 * The day's shots: two from each chance band, shuffled, so the daily is never
 * eight hopeful long shots. `bands[i]` is shot i's model band.
 */
export function dailyPicks(bands: number[], key: string, perBand = 2, nBands = 5): number[] {
  const rng = mulberry32(hashString(`pitchsense-daily-${key}`));
  const picks: number[] = [];
  for (let b = 0; b < nBands; b++) {
    const inBand = bands.map((band, i) => (band === b ? i : -1)).filter((i) => i >= 0);
    picks.push(...shuffle(inBand, rng).slice(0, perBand));
  }
  return shuffle(picks, rng);
}
