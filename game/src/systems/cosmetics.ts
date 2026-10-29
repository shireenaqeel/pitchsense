// Shop items. Pitch themes recolour the pitch; balls recolour the ball.

import type { SaveData } from "./save";

export interface PitchTheme {
  id: string;
  kind: "pitch";
  name: string;
  price: number;
  grass: number;
  stripe: number;
  line: number;
  /** Background behind the pitch. */
  stand: number;
  home: number;
  away: number;
  keeper: number;
}

export interface BallSkin {
  id: string;
  kind: "ball";
  name: string;
  price: number;
  fill: number;
  trim: number;
  trail: number;
}

export type Item = PitchTheme | BallSkin;

export const PITCHES: PitchTheme[] = [
  { id: "pitch.classic", kind: "pitch", name: "Matchday", price: 0, grass: 0x2f7a3e, stripe: 0x2b7039,
    line: 0xe9f2ea, stand: 0x0f1d15, home: 0x3d8bfd, away: 0xef4444, keeper: 0xfacc15 },
  { id: "pitch.night", kind: "pitch", name: "Floodlit Night", price: 300, grass: 0x1d4d2b, stripe: 0x1a4527,
    line: 0xcfe8ff, stand: 0x050a12, home: 0x60a5fa, away: 0xf87171, keeper: 0xfde047 },
  { id: "pitch.snow", kind: "pitch", name: "Snow Day", price: 500, grass: 0xdfe8ee, stripe: 0xd2dde5,
    line: 0x1e3a5f, stand: 0x6b7f8f, home: 0x1d4ed8, away: 0xdc2626, keeper: 0x16a34a },
  { id: "pitch.neon", kind: "pitch", name: "Neon Arcade", price: 800, grass: 0x120b2e, stripe: 0x170f3a,
    line: 0x22d3ee, stand: 0x07041a, home: 0x22d3ee, away: 0xf472b6, keeper: 0xa3e635 },
  { id: "pitch.gold", kind: "pitch", name: "Golden Final", price: 1500, grass: 0x3b5f23, stripe: 0x37591f,
    line: 0xfde68a, stand: 0x1c1405, home: 0xfbbf24, away: 0xe5e7eb, keeper: 0xf97316 },
];

export const BALLS: BallSkin[] = [
  { id: "ball.classic", kind: "ball", name: "Classic", price: 0, fill: 0xffffff, trim: 0x111111, trail: 0xffffff },
  { id: "ball.leather", kind: "ball", name: "1966 Leather", price: 250, fill: 0xa0622d, trim: 0x4a2a10, trail: 0xd6a36b },
  { id: "ball.neon", kind: "ball", name: "Neon", price: 600, fill: 0xa3e635, trim: 0x14532d, trail: 0xa3e635 },
  { id: "ball.gold", kind: "ball", name: "Golden Ball", price: 1200, fill: 0xfacc15, trim: 0x92400e, trail: 0xfde047 },
];

export const ITEMS: Item[] = [...PITCHES, ...BALLS];

export function pitchTheme(save: SaveData): PitchTheme {
  return PITCHES.find((p) => p.id === save.equipped.pitch) ?? PITCHES[0];
}

export function ballSkin(save: SaveData): BallSkin {
  return BALLS.find((b) => b.id === save.equipped.ball) ?? BALLS[0];
}

export type BuyResult = "bought" | "owned" | "poor";

export function buy(save: SaveData, item: Item): BuyResult {
  if (save.owned.includes(item.id)) return "owned";
  if (save.coins < item.price) return "poor";
  save.coins -= item.price;
  save.owned.push(item.id);
  save.stats.purchases += 1;
  return "bought";
}

export function equip(save: SaveData, item: Item): boolean {
  if (!save.owned.includes(item.id)) return false;
  save.equipped[item.kind] = item.id;
  return true;
}
