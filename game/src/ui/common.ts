// Helpers shared by several scenes.

import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { G } from "../state";
import { unlockNew } from "../systems/achievements";
import { levelFromXp, rankFor } from "../systems/progression";
import { toast } from "../scenes/OverlayScene";
import { icon, type IconName } from "./icons";
import { body, C } from "./theme";

const CODES: Record<string, string> = {
  "Côte d'Ivoire": "CIV", "Congo DR": "COD", "Saudi Arabia": "KSA", "South Korea": "KOR",
  "United States": "USA", "Equatorial Guinea": "EQG", Netherlands: "NED", Germany: "GER",
  Switzerland: "SUI", Croatia: "CRO", Denmark: "DEN", Uruguay: "URU", Portugal: "POR",
  Spain: "ESP", England: "ENG", Georgia: "GEO", "Cape Verde Islands": "CPV", Guinea: "GUI",
  "Guinea-Bissau": "GNB", "South Africa": "RSA", "Czech Republic": "CZE", Slovenia: "SVN",
  Slovakia: "SVK", Austria: "AUT", Australia: "AUS", Algeria: "ALG", Angola: "ANG",
  Paraguay: "PAR", Chile: "CHI", Mauritania: "MTN", Morocco: "MAR", Nigeria: "NGA",
};

export function teamCode(team: string): string {
  return CODES[team] ?? team.slice(0, 3).toUpperCase();
}

/**
 * After anything that changes the save: unlock achievements, announce them and
 * any level-up, and write the save.
 */
export function settle(scene: Phaser.Scene, levelBefore: number): void {
  for (const a of unlockNew(G.save)) {
    toast(scene, { icon: a.icon, head: "ACHIEVEMENT", text: `${a.name} — ${a.desc}` });
  }
  const after = levelFromXp(G.save.xp).level;
  if (after > levelBefore) {
    sfx.levelUp();
    const promoted = rankFor(after) !== rankFor(levelBefore);
    toast(scene, {
      icon: promoted ? "medal" : "levelUp",
      head: promoted ? "PROMOTED" : "LEVEL UP",
      text: promoted ? `You are now a ${rankFor(after)}` : `Scout level ${after}`,
      color: C.accent,
    });
  }
  G.persist();
}

export function currentLevel(): number {
  return levelFromXp(G.save.xp).level;
}

/** A small pill of text, e.g. a shot's "Header" tag, with an optional icon. Returns its width. */
export function chip(scene: Phaser.Scene, x: number, y: number, text: string, color = C.panelHi,
  parent?: Phaser.GameObjects.Container, glyph?: IconName): number {
  const pad = glyph ? 30 : 10;
  const t = scene.add.text(x + pad, y, text, body(13)).setOrigin(0, 0.5);
  const w = t.width + pad + 10;
  const g = scene.add.graphics();
  g.fillStyle(color, 1).fillRoundedRect(x, y - 13, w, 26, 13);
  g.lineStyle(1, C.edge, 1).strokeRoundedRect(x, y - 13, w, 26, 13);
  const parts: Phaser.GameObjects.GameObject[] = [g, t];
  if (glyph) parts.push(icon(scene, x + 19, y, glyph, 15, C.muted));
  parent?.add(parts);
  t.setDepth(1);
  return w;
}

export function confetti(scene: Phaser.Scene, x: number, y: number, colors: number[], count = 80): void {
  const p = scene.add.particles(x, y, "confetti", {
    speed: { min: 200, max: 520 },
    angle: { min: 200, max: 340 },
    gravityY: 600,
    rotate: { min: 0, max: 360 },
    lifespan: 1800,
    scale: { min: 0.6, max: 1.1 },
    tint: colors,
    emitting: false,
  }).setDepth(40);
  p.explode(count);
  scene.time.delayedCall(2000, () => p.destroy());
}
