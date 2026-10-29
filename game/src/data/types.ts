// Shapes of the JSON written by `python -m pitchsense.export_game`.

/** Freeze-frame player kind: opponent outfielder, teammate, defending keeper. */
export const OPPONENT = 0;
export const TEAMMATE = 1;
export const KEEPER = 2;
export type Kind = typeof OPPONENT | typeof TEAMMATE | typeof KEEPER;

export interface Shot {
  id: string;
  match: number;
  player: string;
  team: string;
  minute: number;
  x: number;
  y: number;
  end: [number, number, number] | null;
  outcome: string;
  goal: 0 | 1;
  header: 0 | 1;
  /** The trained model's pre-shot xG. */
  xg: number;
  /** Index into `Meta.bands` the model's xG falls in. */
  band: number;
  /** Post-shot xG, only for shots on target. */
  psxg: number | null;
  distance: number;
  angleDeg: number;
  concepts: number[];
  helped: [string, string][];
  hurt: [string, string][];
  frame: [number, number, Kind][];
}

export interface Level {
  stage: string;
  match: number;
  home: string;
  away: string;
  homeScore: number;
  awayScore: number;
  date: string;
  boss: boolean;
  /** `[minute, team]` for every goal scored from a shot, penalties included. */
  goals: [number, string][];
  shots: string[];
}

export interface World {
  name: string;
  champion: string;
  levels: Level[];
}

export interface Puzzle {
  name: string;
  start: [number, number];
  reach: number;
  defenders: [number, number][];
  header: boolean;
  assist: string;
  keeper: string;
  step: number;
  /** `[x, y, xg]` for every spot the striker can reach. */
  spots: [number, number, number][];
  best: [number, number, number];
}

export interface Band {
  label: string;
  emoji: string;
  lower: number;
  p: number;
  gloss: string;
}

export interface MatchMeta {
  tournament: string;
  stage: string;
  home: string;
  away: string;
  homeScore: number;
  awayScore: number;
}

export interface Meta {
  bands: Band[];
  concepts: string[];
  matches: Record<string, MatchMeta>;
}
