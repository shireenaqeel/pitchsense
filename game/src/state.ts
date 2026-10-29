// Loaded game data and the player's save, shared by every scene.

import type { Meta, Puzzle, Shot, World } from "./data/types";
import { browserStore, defaultSave, loadSave, writeSave, type SaveData } from "./systems/save";

export interface GameData {
  shots: Shot[];
  byId: Map<string, Shot>;
  career: World[];
  puzzles: Puzzle[];
  meta: Meta;
  /** Concept names per shot, aligned with `shots`. */
  concepts: string[][];
  /** Indices of shots far enough upfield to stage on the attacking half. */
  pool: number[];
}

/** The pitch view shows the attacking half, so shots from deeper are left out. */
export const MIN_SHOT_X = 62;

class GameState {
  data!: GameData;
  save: SaveData = defaultSave();

  setData(shots: Shot[], career: World[], puzzles: Puzzle[], meta: Meta): void {
    const concepts = shots.map((s) => s.concepts.map((c) => meta.concepts[c]));
    const pool = shots.map((s, i) => (s.x >= MIN_SHOT_X ? i : -1)).filter((i) => i >= 0);
    this.data = { shots, byId: new Map(shots.map((s) => [s.id, s])), career, puzzles, meta, concepts, pool };
  }

  load(): void {
    this.save = loadSave(browserStore());
  }

  persist(): void {
    writeSave(browserStore(), this.save);
  }

  conceptsOf(shot: Shot): string[] {
    return shot.concepts.map((c) => this.data.meta.concepts[c]);
  }
}

export const G = new GameState();
