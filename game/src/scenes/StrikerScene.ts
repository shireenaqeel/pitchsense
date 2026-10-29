import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import type { Puzzle } from "../data/types";
import { PitchView } from "../pitch/PitchView";
import { G } from "../state";
import { puzzleStars } from "../systems/career";
import { ballSkin, pitchTheme } from "../systems/cosmetics";
import { recordPuzzle } from "../systems/record";
import { confetti, currentLevel, settle } from "../ui/common";
import { icon, starRow } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, Button, floatText, panel, stars } from "../ui/widgets";

const GOAL: [number, number] = [120, 40];
const PUZZLE_COINS_PER_STAR = 15;

/** Where the keeper stands for a shot from (x, y): ported from `sandbox.keeper_point`. */
export function keeperPoint(x: number, y: number, keeper: string): [number, number] {
  const dx = GOAL[0] - x;
  const dy = GOAL[1] - y;
  const dist = Math.hypot(dx, dy) || 1e-6;
  const off = keeper === "Rushing out" ? Math.min(10, dist * 0.55) : keeper === "Off the line" ? Math.min(4, dist * 0.4) : 1;
  return [GOAL[0] - (dx / dist) * off, GOAL[1] - (dy / dist) * off];
}

/** Visible goal-mouth angle in degrees, as in `features.shot_angle`. */
export function shotAngle(x: number, y: number): number {
  const a = Math.atan2(36 - y, 120 - x);
  const b = Math.atan2(44 - y, 120 - x);
  return Math.abs(Phaser.Math.RadToDeg(b - a));
}

/** "Striker's Instinct": carry the ball to the spot the model likes best. */
export class StrikerScene extends Phaser.Scene {
  private pitch!: PitchView;
  private puzzle!: Puzzle;
  private index = 0;
  private side!: Phaser.GameObjects.Container;
  private list: Button[] = [];
  private ghost?: Phaser.GameObjects.Arc;
  private keeper?: Phaser.GameObjects.Arc;
  private path?: Phaser.GameObjects.Graphics;
  private choice: [number, number, number] | null = null;
  private done = false;

  constructor() {
    super("Striker");
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this);
    this.add.text(250, 44, "STRIKER'S INSTINCT", title(26, 0xec4899)).setOrigin(0, 0.5);
    this.add.text(250, 76, "Carry the ball (inside the dotted zone) to the spot the xG model rates highest, then shoot.",
      body(14, C.muted)).setOrigin(0, 0.5);
    // Zoomed in on the box: the puzzles all happen in the last 36 yards.
    this.pitch = new PitchView(this, 40, 190, 680 / 60, pitchTheme(G.save), ballSkin(G.save), { xMin: 84, yMin: 10, yMax: 70 });
    panel(this, 760, 104, 490, 600);
    this.side = this.add.container(0, 0);
    this.drawList();
    this.openPuzzle(0);

    // World coordinates: the camera is zoomed to the screen's resolution.
    this.input.on("pointermove", (p: Phaser.Input.Pointer) => this.hover(p.worldX, p.worldY));
    this.input.on("pointerdown", (p: Phaser.Input.Pointer) => {
      if (this.pitch.contains(p.worldX, p.worldY)) this.choose(p.worldX, p.worldY);
    });
  }

  private drawList(): void {
    this.list.forEach((b) => b.destroy());
    this.list = G.data.puzzles.map((pz, i) => {
      const got = G.save.puzzles[pz.name] ?? 0;
      const b = new Button(this, 760 + 245, 140 + i * 48, { w: 450, h: 42, label: `${i + 1}. ${pz.name}   ${stars(got)}`, size: 15, align: "left" },
        () => this.openPuzzle(i));
      b.setSelected(i === this.index);
      return b;
    });
  }

  private nearest(x: number, y: number): [number, number, number] | null {
    let best: [number, number, number] | null = null;
    let bd = Infinity;
    for (const s of this.puzzle.spots) {
      const d = (s[0] - x) ** 2 + (s[1] - y) ** 2;
      if (d < bd) {
        bd = d;
        best = s;
      }
    }
    return bd <= 2 ? best : null;
  }

  private openPuzzle(i: number): void {
    this.index = i;
    this.puzzle = G.data.puzzles[i];
    this.done = false;
    this.choice = null;
    this.list.forEach((b, j) => b.setSelected(j === i).setVisible(true));
    const pz = this.puzzle;
    const [sx, sy] = pz.start;
    this.pitch.stage(sx, sy, pz.defenders.map(([x, y]) => [x, y, 0]), "You", false);

    const dots = this.add.graphics();
    dots.fillStyle(0xffffff, 0.22);
    for (const [x, y] of pz.spots) {
      const p = this.pitch.at(x, y);
      dots.fillCircle(p.x, p.y, 1.6);
    }
    this.pitch.add(dots);
    const kp = keeperPoint(sx, sy, pz.keeper);
    const k = this.pitch.at(kp[0], kp[1]);
    this.keeper = this.add.circle(k.x, k.y, 8, pitchTheme(G.save).keeper).setStrokeStyle(2, 0x000000, 0.6);
    this.path = this.add.graphics();
    this.ghost = this.add.circle(0, 0, 10, 0xffffff, 0.35).setStrokeStyle(2, 0xffffff).setVisible(false);
    this.pitch.add([this.keeper, this.path, this.ghost]);
    this.drawSide();
  }

  private hover(px: number, py: number): void {
    if (this.done || !this.ghost) return;
    const { x, y } = this.pitch.toPitch(px, py);
    const spot = this.nearest(x, y);
    if (!spot && !this.choice) {
      this.ghost.setVisible(false);
      return;
    }
    const [tx, ty] = spot ?? this.choice!;
    this.placeGhost(tx, ty);
  }

  private placeGhost(tx: number, ty: number): void {
    const p = this.pitch.at(tx, ty);
    this.ghost!.setPosition(p.x, p.y).setVisible(true);
    const kp = keeperPoint(tx, ty, this.puzzle.keeper);
    const k = this.pitch.at(kp[0], kp[1]);
    this.keeper!.setPosition(k.x, k.y);
    const s = this.pitch.at(this.puzzle.start[0], this.puzzle.start[1]);
    this.path!.clear().lineStyle(2, 0xffffff, 0.6).lineBetween(s.x, s.y, p.x, p.y);
  }

  private choose(px: number, py: number): void {
    if (this.done) return;
    const { x, y } = this.pitch.toPitch(px, py);
    const spot = this.nearest(x, y);
    if (!spot) {
      sfx.miss();
      return;
    }
    sfx.select();
    this.choice = spot;
    this.placeGhost(spot[0], spot[1]);
    this.drawSide();
  }

  private drawSide(): void {
    this.side.removeAll(true);
    const pz = this.puzzle;
    const x = 784;
    const y = 540;
    const extras = [pz.header ? "Header" : "", pz.assist !== "None" ? `From a ${pz.assist.toLowerCase()}` : "",
      pz.keeper !== "On the line" ? `Keeper: ${pz.keeper.toLowerCase()}` : ""].filter(Boolean).join(" · ");
    this.side.add(this.add.text(x, y - 14, pz.name.toUpperCase(), title(20, 0xec4899)).setOrigin(0, 0.5));
    this.side.add(this.add.text(x, y + 14, `${pz.defenders.length} defenders · up to ${pz.reach} yds of carry${extras ? ` · ${extras}` : ""}`,
      { ...body(13, C.muted), wordWrap: { width: 440 } }).setOrigin(0, 0));
    if (this.done) return;
    const label = this.choice ? "SHOOT FROM HERE" : "Click a spot in the zone";
    const b = new Button(this, 760 + 245, 660, { w: 450, h: 54, label, display: true, size: 18, color: this.choice ? 0xec4899 : C.panelHi,
      icon: this.choice ? "ball" : undefined },
      () => this.shoot());
    b.setEnabled(Boolean(this.choice));
    this.side.add(b);
    this.input.keyboard?.once("keydown-SPACE", () => this.choice && this.shoot());
  }

  private shoot(): void {
    if (this.done || !this.choice) return;
    this.done = true;
    const pz = this.puzzle;
    const [cx, cy, xg] = this.choice;
    const [bx, by, best] = pz.best;
    const got = puzzleStars(xg, best);
    this.ghost?.setVisible(false);
    this.pitch.placeBall(cx, cy);
    void this.pitch.shoot(cx, cy, [120, 40 + Phaser.Math.FloatBetween(-3, 3), 1], "Off T", 1.3).then(() => {
      this.heatmap();
      const levelBefore = currentLevel();
      const improved = payPuzzle(pz.name, got);
      settle(this, levelBefore);
      const p = this.pitch.at(cx, cy);
      floatText(this, p.x, p.y - 20, `${Math.round(xg * 100)}% xG`, got >= 2 ? C.exact : got === 1 ? C.near : C.miss, 26);
      if (got === 3) {
        sfx.exact();
        confetti(this, p.x, p.y, [0xec4899, C.gold, 0xffffff], 70);
      } else if (got > 0) sfx.near();
      else sfx.miss();
      this.result(xg, best, bx, by, cx, cy, got, improved);
    });
  }

  private heatmap(): void {
    const pz = this.puzzle;
    const g = this.add.graphics();
    const size = pz.step * this.pitch.s;
    const best = pz.best[2];
    for (const [x, y, v] of pz.spots) {
      const p = this.pitch.at(x, y);
      const t = Phaser.Math.Clamp(v / best, 0, 1);
      const c = Phaser.Display.Color.Interpolate.ColorWithColor(
        Phaser.Display.Color.ValueToColor(0x1e3a8a), Phaser.Display.Color.ValueToColor(0xf43f5e), 100, Math.round(t * 100));
      g.fillStyle(Phaser.Display.Color.GetColor(c.r, c.g, c.b), 0.25 + 0.55 * t).fillRect(p.x - size / 2, p.y - size / 2, size, size);
    }
    g.setAlpha(0);
    this.pitch.add(g);
    this.tweens.add({ targets: g, alpha: 1, duration: 500 });
    const b = this.pitch.at(pz.best[0], pz.best[1]);
    const star = icon(this, b.x, b.y, "star", 26, C.gold);
    const full = star.scale;
    star.setScale(0);
    this.pitch.add(star);
    this.tweens.add({ targets: star, scale: full, duration: 300, delay: 400, ease: "Back.Out" });
    const c = this.choice!;
    const you = this.pitch.at(c[0], c[1]);
    this.pitch.add(this.add.circle(you.x, you.y, 11).setStrokeStyle(3, 0xffffff));
  }

  private result(xg: number, best: number, bx: number, by: number, cx: number, cy: number, got: number, improved: boolean): void {
    this.drawList();
    this.list.forEach((b) => b.setVisible(false));
    this.drawSide();
    const x = 784;
    const y = 140;
    this.side.add(starRow(this, x + 64, y + 18, got, 36));
    const lines: [string, number, number][] = [
      [`Your spot: ${Math.round(xg * 100)}% xG   ·   Best: ${Math.round(best * 100)}%`, 17, C.text],
    ];
    const dDist = Math.hypot(120 - cx, 40 - cy) - Math.hypot(120 - bx, 40 - by);
    const dAng = shotAngle(bx, by) - shotAngle(cx, cy);
    const tip = got === 3 ? "Perfect instinct — that's the spot the model likes best."
      : `The best spot was ${Math.abs(dDist).toFixed(0)} yds ${dDist > 0 ? "closer" : "further out"} with ${Math.abs(dAng).toFixed(0)}° ${dAng > 0 ? "more" : "less"} goal to aim at. Bodies in the lane and the keeper's position matter as much as distance.`;
    lines.push([tip, 14, C.muted]);
    if (improved) lines.push([`New best! +${PUZZLE_COINS_PER_STAR} coins per new star`, 14, C.gold]);
    let yy = y + 52;
    for (const [t, size, color] of lines) {
      const txt = this.add.text(x, yy, t, { ...(size > 30 ? title(size, color) : body(size, color)), wordWrap: { width: 440 } }).setOrigin(0, 0);
      this.side.add(txt);
      yy += txt.height + 10;
    }
    const retry = new Button(this, 760 + 130, 660, { w: 220, h: 54, label: "Try again", icon: "retry", size: 16 }, () => this.openPuzzle(this.index));
    const next = new Button(this, 760 + 360, 660, { w: 220, h: 54, label: "Next", icon: "next", display: true, size: 18, color: 0xec4899 },
      () => this.openPuzzle((this.index + 1) % G.data.puzzles.length));
    this.side.add([retry, next]);
  }
}

/** Save puzzle stars and pay for each new star. */
function payPuzzle(name: string, stars: number): boolean {
  const before = G.save.puzzles[name] ?? 0;
  const improved = recordPuzzle(G.save, name, stars);
  if (improved) G.save.coins += (stars - before) * PUZZLE_COINS_PER_STAR;
  return improved;
}
