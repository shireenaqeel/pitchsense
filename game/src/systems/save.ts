// The save file: one JSON blob in localStorage, merged over defaults on load so
// a save from an older build never crashes a newer one.

import type { ConceptProgress } from "./adaptive";
import type { StarMap } from "./career";

export const SAVE_KEY = "pitchsense.save.v1";

export interface Stats {
  reads: number;
  exact: number;
  bestCombo: number;
  /** Fastest exact read, in ms. */
  fastestExactMs: number | null;
  /** Exact reads per chance band. */
  bandExact: number[];
  /** Exact reads per concept name. */
  conceptExact: Record<string, number>;
  bossesBeaten: number;
  flawlessMatches: number;
  threeStarMatches: number;
  purchases: number;
}

export interface DailyState {
  last: string | null;
  streak: number;
  bestStreak: number;
  scores: Record<string, number>;
}

export interface SaveData {
  version: 1;
  xp: number;
  coins: number;
  stats: Stats;
  concepts: ConceptProgress;
  career: StarMap;
  trophies: string[];
  puzzles: Record<string, number>;
  rapidBest: number;
  /** Best round scores in Referee's Eye and What Happens Next? */
  refBest: number;
  nextBest: number;
  daily: DailyState;
  achievements: string[];
  /** Ids of finished Academy lessons. */
  academy: string[];
  owned: string[];
  equipped: { pitch: string; ball: string };
  settings: { muted: boolean };
  /** The name last used on the shared leaderboards. */
  playerName: string;
}

export function defaultSave(): SaveData {
  return {
    version: 1,
    xp: 0,
    coins: 0,
    stats: {
      reads: 0,
      exact: 0,
      bestCombo: 0,
      fastestExactMs: null,
      bandExact: [0, 0, 0, 0, 0],
      conceptExact: {},
      bossesBeaten: 0,
      flawlessMatches: 0,
      threeStarMatches: 0,
      purchases: 0,
    },
    concepts: {},
    career: {},
    trophies: [],
    puzzles: {},
    rapidBest: 0,
    refBest: 0,
    nextBest: 0,
    daily: { last: null, streak: 0, bestStreak: 0, scores: {} },
    achievements: [],
    academy: [],
    owned: ["pitch.classic", "ball.classic"],
    equipped: { pitch: "pitch.classic", ball: "ball.classic" },
    settings: { muted: false },
    playerName: "",
  };
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Deep-merge `loaded` over `base`, keeping only keys whose types agree. */
export function mergeSave<T>(base: T, loaded: unknown): T {
  if (Array.isArray(base)) return (Array.isArray(loaded) ? loaded : base) as T;
  if (isObject(base)) {
    if (!isObject(loaded)) return base;
    // An empty default object is a free-form map (stars per level, scores per
    // day): take the saved one as it is.
    if (Object.keys(base).length === 0) return loaded as T;
    const out: Record<string, unknown> = { ...base };
    for (const k of Object.keys(base)) if (k in loaded) out[k] = mergeSave(base[k], loaded[k]);
    return out as T;
  }
  if (base === null) return (loaded ?? null) as T;
  return (typeof loaded === typeof base ? loaded : base) as T;
}

export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** Load the save; storage that is missing, blocked or corrupt gives a new save. */
export function loadSave(store: KeyValueStore | null): SaveData {
  try {
    const raw = store?.getItem(SAVE_KEY);
    if (!raw) return defaultSave();
    return mergeSave(defaultSave(), JSON.parse(raw));
  } catch {
    return defaultSave();
  }
}

export function writeSave(store: KeyValueStore | null, save: SaveData): void {
  try {
    store?.setItem(SAVE_KEY, JSON.stringify(save));
  } catch {
    // Private windows and full quotas: the game keeps working, unsaved.
  }
}

export function browserStore(): KeyValueStore | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
