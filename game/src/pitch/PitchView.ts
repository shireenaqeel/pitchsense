// The attacking half of a pitch, goal at the top, drawn from StatsBomb yards.
//
// StatsBomb's pitch is 120 x 80 with the attacked goal at x = 120. Screen x is
// the pitch width (y) and screen y runs from the goal down to halfway (x), so
// the player looks at the chance the way a striker does.

import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { KEEPER, OPPONENT, type Kind } from "../data/types";
import type { BallSkin, PitchTheme } from "../systems/cosmetics";
import { body } from "../ui/theme";

export const HALF_X = 60;
const POSTS = [36, 44];
const NET_DEPTH = 2.2;

/** The slice of the pitch on screen: from `xMin` up to the goal, `yMin`..`yMax` across. */
export interface Viewport {
  xMin: number;
  yMin: number;
  yMax: number;
}

export const HALF: Viewport = { xMin: HALF_X, yMin: 0, yMax: 80 };

export type Flight = "goal" | "saved" | "blocked" | "wide";

export function flightOf(outcome: string): Flight {
  if (outcome === "Goal") return "goal";
  if (outcome === "Blocked") return "blocked";
  if (outcome.startsWith("Saved")) return "saved";
  return "wide";
}

export class PitchView {
  readonly w: number;
  readonly h: number;
  private layer: Phaser.GameObjects.Container;
  private actors: Phaser.GameObjects.Container;
  private net!: Phaser.GameObjects.Graphics;
  private ball?: Phaser.GameObjects.Container;
  private shadow?: Phaser.GameObjects.Ellipse;

  constructor(
    private scene: Phaser.Scene,
    readonly ox: number,
    readonly oy: number,
    readonly s: number,
    private theme: PitchTheme,
    private ballSkin: BallSkin,
    readonly view: Viewport = HALF,
  ) {
    this.w = (view.yMax - view.yMin) * s;
    this.h = (120 - view.xMin) * s;
    this.drawStand();
    this.layer = scene.add.container(0, 0);
    this.actors = scene.add.container(0, 0);
    // Markings and players outside a zoomed viewport are clipped; the net and
    // a shot flying over the bar stay visible above the goal line.
    const below = view.xMin <= 0 ? 4 * s : 0;
    const clip = scene.make.graphics({}, false).fillRect(this.ox, this.oy - 4 * s, this.w, this.h + 4 * s + below);
    const mask = clip.createGeometryMask();
    this.layer.setMask(mask);
    this.actors.setMask(mask);
    this.draw();
  }

  /** StatsBomb (x, y) to screen pixels. */
  at(x: number, y: number): { x: number; y: number } {
    return { x: this.ox + (y - this.view.yMin) * this.s, y: this.oy + (120 - x) * this.s };
  }

  /** Screen pixels back to StatsBomb (x, y). */
  toPitch(px: number, py: number): { x: number; y: number } {
    return { x: 120 - (py - this.oy) / this.s, y: this.view.yMin + (px - this.ox) / this.s };
  }

  contains(px: number, py: number): boolean {
    return px >= this.ox && px <= this.ox + this.w && py >= this.oy && py <= this.oy + this.h;
  }

  /** True when the view reaches our own goal line, so the whole pitch is on screen. */
  get full(): boolean {
    return this.view.xMin <= 0;
  }

  private drawStand(): void {
    this.scene.add.graphics().fillStyle(this.theme.stand, 1)
      .fillRoundedRect(this.ox - 24, this.oy - 44, this.w + 48, this.h + 60 + (this.full ? 28 : 0), 18);
  }

  /**
   * Markings for the whole pitch; the mask trims them to the viewport, so the
   * same drawing serves the attacking half, a zoom on the box, or both ends.
   */
  private draw(): void {
    const { scene, s, theme } = this;
    const g = scene.add.graphics();
    this.layer.add(g);

    g.fillStyle(theme.grass, 1).fillRect(this.ox, this.oy, this.w, this.h);
    for (let x = 120; x > this.view.xMin; x -= 12) {
      const top = this.at(x, 0).y;
      g.fillStyle(theme.stripe, 1).fillRect(this.ox, top, this.w, 6 * s);
    }

    g.lineStyle(2, theme.line, 0.9);
    const corner = this.at(120, 0);
    g.strokeRect(corner.x, corner.y, 80 * s, 120 * s);
    const rect = (x0: number, x1: number, y0: number, y1: number) => {
      const a = this.at(x1, y0);
      g.strokeRect(a.x, a.y, (y1 - y0) * s, (x1 - x0) * s);
    };
    const d = Math.asin(0.6);
    for (const [end, dir] of [[120, -1], [0, 1]] as const) {
      rect(Math.min(end, end + dir * 18), Math.max(end, end + dir * 18), 18, 62);
      rect(Math.min(end, end + dir * 6), Math.max(end, end + dir * 6), 30, 50);
      const spot = this.at(end + dir * 12, 40);
      g.fillStyle(theme.line, 0.9).fillCircle(spot.x, spot.y, 3);
      // The "D": the part of the penalty-spot circle outside the box.
      g.beginPath();
      if (dir < 0) g.arc(spot.x, spot.y, 10 * s, d, Math.PI - d);
      else g.arc(spot.x, spot.y, 10 * s, Math.PI + d, 2 * Math.PI - d);
      g.strokePath();
    }
    const centre = this.at(HALF_X, 40);
    g.lineBetween(this.at(HALF_X, 0).x, centre.y, this.at(HALF_X, 80).x, centre.y);
    g.strokeCircle(centre.x, centre.y, 10 * s);
    g.fillCircle(centre.x, centre.y, 3);

    if (this.full) {
      // Our own goal, below the bottom goal line. It never animates.
      const a = this.at(0, POSTS[0]);
      const width = (POSTS[1] - POSTS[0]) * s;
      const depth = NET_DEPTH * s;
      g.fillStyle(0xffffff, 0.12).fillRect(a.x, a.y, width, depth);
      g.lineStyle(4, 0xffffff, 1);
      g.lineBetween(a.x, a.y, a.x, a.y + depth);
      g.lineBetween(a.x + width, a.y, a.x + width, a.y + depth);
      g.lineBetween(a.x, a.y + depth, a.x + width, a.y + depth);
    }

    this.net = scene.add.graphics();
    this.layer.add(this.net);
    this.drawNet(0);
  }

  private drawNet(bulge: number): void {
    const { s } = this;
    const a = this.at(120, POSTS[0]);
    const width = (POSTS[1] - POSTS[0]) * s;
    const depth = NET_DEPTH * s + bulge;
    const g = this.net;
    g.clear();
    g.fillStyle(0xffffff, 0.12).fillRect(a.x, a.y - depth, width, depth);
    g.lineStyle(1, 0xffffff, 0.35);
    for (let i = 1; i < 8; i++) g.lineBetween(a.x + (width * i) / 8, a.y - depth, a.x + (width * i) / 8, a.y);
    for (let j = 1; j < 3; j++) g.lineBetween(a.x, a.y - (depth * j) / 3, a.x + width, a.y - (depth * j) / 3);
    g.lineStyle(4, 0xffffff, 1);
    g.lineBetween(a.x, a.y, a.x, a.y - depth);
    g.lineBetween(a.x + width, a.y, a.x + width, a.y - depth);
    g.lineBetween(a.x, a.y - depth, a.x + width, a.y - depth);
  }

  clear(): void {
    this.actors.removeAll(true);
    this.ball?.destroy();
    this.shadow?.destroy();
    this.ball = this.shadow = undefined;
  }

  /** Bring a freeze-frame on: players slide into their positions. */
  stage(x: number, y: number, frame: [number, number, Kind][], label?: string, cone = true): void {
    this.clear();
    const { scene, theme, s } = this;
    const r = Math.max(6, 0.95 * s);

    if (cone) {
      const p = this.at(x, y);
      const l = this.at(120, POSTS[0]);
      const rr = this.at(120, POSTS[1]);
      const tri = scene.add.triangle(0, 0, p.x, p.y, l.x, l.y, rr.x, rr.y, 0xffffff, 0.13).setOrigin(0, 0);
      tri.setAlpha(0);
      this.actors.add(tri);
      scene.tweens.add({ targets: tri, alpha: 1, duration: 500, delay: 250 });
    }

    frame.forEach(([px, py, kind], i) => {
      if (px < this.view.xMin - 1) return;
      const p = this.at(px, py);
      const color = kind === KEEPER ? theme.keeper : kind === OPPONENT ? theme.away : theme.home;
      const dot = scene.add.circle(p.x, p.y, r, color).setStrokeStyle(2, 0x000000, 0.6);
      if (kind !== OPPONENT && kind !== KEEPER) dot.setAlpha(0.75);
      const from = Phaser.Math.Angle.Between(p.x, p.y, this.ox + this.w / 2, this.oy) + Math.PI;
      dot.x += Math.cos(from) * 40;
      dot.y += Math.sin(from) * 40;
      dot.setScale(0);
      this.actors.add(dot);
      scene.tweens.add({ targets: dot, x: p.x, y: p.y, scale: 1, duration: 380, delay: 20 * i, ease: "Back.Out" });
    });

    const p = this.at(x, y);
    const ring = scene.add.circle(p.x, p.y, r * 2.2).setStrokeStyle(3, 0xffffff, 0.9);
    scene.tweens.add({ targets: ring, scale: { from: 0.6, to: 1.2 }, alpha: { from: 1, to: 0.2 }, duration: 800, repeat: -1 });
    const shooter = scene.add.circle(p.x, p.y, r * 1.3, theme.home).setStrokeStyle(3, 0xffffff, 1);
    this.actors.add([ring, shooter]);
    if (label) {
      const t = scene.add.text(p.x, p.y + r * 2.6, label, body(13)).setOrigin(0.5, 0);
      t.setStroke("#000000", 4);
      this.actors.add(t);
    }
    this.placeBall(x, y);
  }

  /** Extra markers drawn on top of the frame (puzzle defenders, the reach circle). */
  add(obj: Phaser.GameObjects.GameObject | Phaser.GameObjects.GameObject[]): void {
    this.actors.add(obj);
  }

  placeBall(x: number, y: number): void {
    this.ball?.destroy();
    this.shadow?.destroy();
    const p = this.at(x, y);
    const r = Math.max(4, 0.55 * this.s);
    this.shadow = this.scene.add.ellipse(p.x + 2, p.y + 3, r * 2, r * 1.3, 0x000000, 0.35);
    const fill = this.scene.add.circle(0, 0, r, this.ballSkin.fill).setStrokeStyle(2, this.ballSkin.trim);
    const patch = this.scene.add.circle(0, 0, r * 0.35, this.ballSkin.trim);
    this.ball = this.scene.add.container(p.x, p.y, [fill, patch]);
  }

  /**
   * Animate the strike to where it finished. The view is top-down, so height
   * is shown the Sensible Soccer way: the ball grows as it rises and its
   * shadow stays on the grass.
   */
  shoot(x: number, y: number, end: [number, number, number] | null, outcome: string, speed = 1): Promise<Flight> {
    const flight = flightOf(outcome);
    const ball = this.ball!;
    const shadow = this.shadow!;
    const trail = this.scene.add.particles(0, 0, "dot", {
      follow: ball,
      lifespan: 260,
      scale: { start: 0.25, end: 0 },
      alpha: { start: 0.5, end: 0 },
      tint: this.ballSkin.trail,
      frequency: 16,
    });
    let [ex, ey, ez] = end ?? [120, 40, 0.5];
    if (flight === "goal") ex = Math.max(ex, 121.2);
    if (flight === "wide" && ex >= 119) ex = 121.5;
    const from = this.at(x, y);
    const to = this.at(Math.min(ex, 122), ey);
    const dist = Phaser.Math.Distance.Between(x, y, ex, ey);
    const peak = Math.min(2.5, dist / 14) + (ez > 2.4 ? 1 : 0);
    sfx.kick();

    return new Promise((resolve) => {
      this.scene.tweens.addCounter({
        from: 0,
        to: 1,
        duration: Phaser.Math.Clamp(dist * 22, 380, 900) / speed,
        ease: "Sine.In",
        onUpdate: (tw) => {
          const t = tw.getValue() ?? 0;
          const gx = Phaser.Math.Linear(from.x, to.x, t);
          const gy = Phaser.Math.Linear(from.y, to.y, t);
          const height = 4 * peak * t * (1 - t) + ez * t;
          shadow.setPosition(gx + 2 + height * 2, gy + 3 + height * 2);
          ball.setPosition(gx, gy).setScale(1 + height * 0.22);
        },
        onComplete: () => {
          trail.stop();
          this.scene.time.delayedCall(400, () => trail.destroy());
          if (flight === "goal") this.rippleNet();
          if (flight === "saved" || flight === "blocked") this.deflect(ball, shadow, flight === "blocked");
          resolve(flight);
        },
      });
    });
  }

  private deflect(ball: Phaser.GameObjects.Container, shadow: Phaser.GameObjects.Ellipse, blocked: boolean): void {
    const angle = Phaser.Math.FloatBetween(blocked ? 0.3 : -0.4, blocked ? Math.PI - 0.3 : Math.PI + 0.4);
    const d = (blocked ? 4 : 6) * this.s;
    const dx = Math.cos(angle) * d;
    const dy = Math.abs(Math.sin(angle)) * d;
    this.scene.tweens.add({ targets: [ball, shadow], x: `+=${dx}`, y: `+=${dy}`, duration: 420, ease: "Quad.Out" });
    this.scene.tweens.add({ targets: ball, scale: 1, duration: 420 });
  }

  rippleNet(): void {
    this.scene.tweens.addCounter({
      from: 0,
      to: 1,
      duration: 600,
      onUpdate: (tw) => {
        const t = tw.getValue() ?? 0;
        this.drawNet(Math.sin(t * Math.PI * 3) * (1 - t) * 10);
      },
      onComplete: () => this.drawNet(0),
    });
  }

  destroy(): void {
    this.clear();
    this.actors.destroy();
    this.layer.destroy();
  }
}
