// Draws a lesson's marks (players, passes, zones...) onto a PitchView, with a
// little animation as each step adds to the picture.

import Phaser from "phaser";

import type { PitchView } from "../pitch/PitchView";
import type { PitchTheme } from "../systems/cosmetics";
import { BAND_COLORS, body, C } from "../ui/theme";
import type { Mark, Pt, Tone } from "./curriculum";

const TONES: Record<Tone, number> = { accent: C.accent, gold: C.gold, danger: C.miss, info: 0x60a5fa };

/** Zones and lines sit under arrows, which sit under players. */
const LAYER: Record<Mark["kind"], number> = { zone: 0, line: 0, cone: 0, arrow: 1, ring: 2, spot: 2, player: 3, ball: 4 };

export class Diagram {
  private delay = 0;
  private animate = true;

  constructor(private scene: Phaser.Scene, private pitch: PitchView, private theme: PitchTheme) {}

  clear(): void {
    this.pitch.clear();
  }

  /** Add marks to the picture; `animate` false draws them in place at once. */
  draw(marks: Mark[], animate = true): void {
    this.animate = animate;
    this.delay = 0;
    const ordered = marks.map((m, i) => [m, i] as const).sort((a, b) => LAYER[a[0].kind] - LAYER[b[0].kind] || a[1] - b[1]);
    for (const [m] of ordered) this.mark(m);
  }

  private get r(): number {
    return Math.max(6, 0.95 * this.pitch.s);
  }

  private at([x, y]: Pt): { x: number; y: number } {
    return this.pitch.at(x, y);
  }

  /** Pop an object in, a beat after the previous one. */
  private pop(obj: Phaser.GameObjects.GameObject & { setScale(v: number): unknown; setAlpha(v: number): unknown }, fade = false): void {
    this.pitch.add(obj);
    if (!this.animate) return;
    const delay = this.delay;
    this.delay += 35;
    if (fade) {
      obj.setAlpha(0);
      this.scene.tweens.add({ targets: obj, alpha: 1, duration: 400, delay });
    } else {
      obj.setScale(0);
      this.scene.tweens.add({ targets: obj, scale: 1, duration: 320, delay, ease: "Back.Out" });
    }
  }

  private label(x: number, y: number, text: string, color = 0xffffff, originY = 0): void {
    const t = this.scene.add.text(x, y, text, body(13, color, "800")).setOrigin(0.5, originY);
    t.setStroke("#000000", 4);
    this.pop(t, true);
  }

  private mark(m: Mark): void {
    const { scene, theme } = this;
    switch (m.kind) {
      case "player": {
        const p = this.at(m.at);
        const color = m.side === "keeper" ? theme.keeper : m.side === "away" ? theme.away : theme.home;
        this.pop(scene.add.circle(p.x, p.y, this.r, color).setStrokeStyle(2, 0x000000, 0.6));
        if (m.label) this.label(p.x, p.y + this.r + 4, m.label);
        return;
      }
      case "ball": {
        const p = this.at(m.at);
        const r = Math.max(4, 0.5 * this.pitch.s);
        this.pop(scene.add.circle(p.x, p.y, r, 0xffffff).setStrokeStyle(2, 0x111111));
        return;
      }
      case "zone": {
        const tone = TONES[m.tone ?? "accent"];
        const a = this.at([m.x[1], m.y[0]]);
        const w = (m.y[1] - m.y[0]) * this.pitch.s;
        const h = (m.x[1] - m.x[0]) * this.pitch.s;
        const g = scene.add.graphics();
        g.fillStyle(tone, 0.22).fillRect(a.x, a.y, w, h);
        g.lineStyle(2, tone, 0.9).strokeRect(a.x, a.y, w, h);
        this.pop(g, true);
        if (m.label) this.label(a.x + w / 2, a.y + h / 2, m.label, tone, 0.5);
        return;
      }
      case "line": {
        const y = this.at([m.x, 0]).y;
        const g = scene.add.graphics().lineStyle(3, C.gold, 0.95);
        const x0 = this.pitch.ox;
        const x1 = this.pitch.ox + this.pitch.w;
        for (let x = x0; x < x1; x += 16) g.lineBetween(x, y, Math.min(x + 9, x1), y);
        this.pop(g, true);
        if (m.label) this.label(x1 - 70, y - 6, m.label, C.gold, 1);
        return;
      }
      case "cone": {
        const p = this.at(m.from);
        const l = this.pitch.at(120, 36);
        const r = this.pitch.at(120, 44);
        this.pop(scene.add.triangle(0, 0, p.x, p.y, l.x, l.y, r.x, r.y, 0xffffff, 0.16).setOrigin(0, 0), true);
        return;
      }
      case "ring": {
        const p = this.at(m.at);
        const ring = scene.add.circle(p.x, p.y, this.r * 1.8).setStrokeStyle(3, C.gold, 1);
        this.pop(ring, true);
        scene.tweens.add({ targets: ring, scale: { from: 0.7, to: 1.25 }, alpha: { from: 1, to: 0.3 }, duration: 900, repeat: -1, yoyo: true });
        if (m.label) this.label(p.x, p.y + this.r * 2.4, m.label, C.gold);
        return;
      }
      case "spot": {
        const p = this.at(m.at);
        const color = BAND_COLORS[m.band];
        this.pop(scene.add.circle(p.x, p.y, this.r * 1.1, color).setStrokeStyle(3, 0xffffff, 0.95));
        if (m.label) this.label(p.x, p.y - this.r * 1.5, m.label, color, 1);
        return;
      }
      case "arrow":
        this.arrow(m.from, m.to, m.style, m.label);
    }
  }

  private arrow(from: Pt, to: Pt, style: "pass" | "run" | "shot", label?: string): void {
    const a = this.at(from);
    const b = this.at(to);
    const color = style === "shot" ? C.gold : style === "run" ? 0xbfdbfe : 0xffffff;
    const width = style === "shot" ? 4 : 3;
    const g = this.scene.add.graphics();
    this.pitch.add(g);
    const angle = Math.atan2(b.y - a.y, b.x - a.x);
    const len = Math.hypot(b.x - a.x, b.y - a.y);
    const head = style === "shot" ? 14 : 11;

    const render = (t: number) => {
      if (!g.scene) return; // cleared by the next step mid-animation
      g.clear().lineStyle(width, color, 0.95);
      const end = Math.max(0, len * t - head * 0.6);
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      if (style === "run") {
        for (let d = 0; d < end; d += 12) g.lineBetween(a.x + cos * d, a.y + sin * d, a.x + cos * Math.min(d + 7, end), a.y + sin * Math.min(d + 7, end));
      } else {
        g.lineBetween(a.x, a.y, a.x + cos * end, a.y + sin * end);
      }
      if (t < 1) return;
      g.fillStyle(color, 1).fillTriangle(
        b.x, b.y,
        b.x - cos * head - sin * head * 0.55, b.y - sin * head + cos * head * 0.55,
        b.x - cos * head + sin * head * 0.55, b.y - sin * head - cos * head * 0.55,
      );
    };

    if (label) {
      // Beside the arrow's midpoint, on the side away from the goal mouth.
      const side = Math.sin(angle) > 0 ? 1 : -1;
      this.label((a.x + b.x) / 2 + side * 14 * Math.abs(Math.sin(angle)), (a.y + b.y) / 2 - 8, label, color, 1);
    }
    if (!this.animate) return render(1);
    render(0);
    this.scene.tweens.addCounter({ from: 0, to: 1, duration: 520, delay: this.delay + 120, ease: "Sine.Out", onUpdate: (tw) => render(tw.getValue() ?? 0) });
  }
}
