import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { G } from "../state";
import { pitchTheme } from "../systems/cosmetics";
import { levelFromXp, rankFor } from "../systems/progression";
import type { Grade } from "../systems/scoring";
import { confetti } from "../ui/common";
import { icon, inline } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { bar, Button, goTo, panel } from "../ui/widgets";
import type { PlayMode } from "./PlayScene";

export interface ResultsData {
  mode: PlayMode;
  score: number;
  grades: Grade[];
  bestCombo: number;
  headline: string;
  sub: string;
  stars: number | null;
  xp: number;
  coins: number;
  share: string | null;
  newBest: boolean;
  trophy: string | null;
  won: boolean;
}

export class ResultsScene extends Phaser.Scene {
  constructor() {
    super("Results");
  }

  create(d: ResultsData): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    const color = d.trophy ? C.gold : d.won ? C.accent : C.miss;

    if (d.trophy) {
      const cup = icon(this, W / 2, 120, "trophy", 110, C.gold);
      const full = cup.scale;
      cup.setScale(0);
      this.tweens.add({ targets: cup, scale: full, angle: { from: -20, to: 0 }, duration: 700, ease: "Back.Out" });
      this.time.delayedCall(400, () => {
        sfx.levelUp();
        confetti(this, W / 2, 140, [C.gold, 0xffffff, pitchTheme(G.save).home], 160);
      });
    }
    const top = d.trophy ? 228 : 110;
    const head = this.add.text(W / 2, top, d.headline, title(d.trophy ? 52 : 60, color)).setOrigin(0.5).setScale(0.6);
    head.setShadow(0, 6, "#000", 0, true, true);
    this.tweens.add({ targets: head, scale: 1, duration: 420, ease: "Back.Out" });
    if (d.trophy) this.add.text(W / 2, top + 44, `${d.trophy} — you read it like a champion`, body(18, C.text)).setOrigin(0.5);
    this.add.text(W / 2, top + (d.trophy ? 74 : 54), d.sub, body(16, C.muted)).setOrigin(0.5);

    const py = top + (d.trophy ? 102 : 92);
    const panelH = d.stars !== null ? 300 : 236;
    panel(this, W / 2 - 330, py, 660, panelH);

    if (d.stars !== null) this.popStars(d.stars, py + 50);
    const scoreY = d.stars !== null ? py + 120 : py + 60;
    const scoreText = this.add.text(W / 2, scoreY, "0", title(54)).setOrigin(0.5);
    this.tweens.addCounter({
      from: 0, to: d.score, duration: 900, ease: "Cubic.Out",
      onUpdate: (tw) => scoreText.setText(Math.round(tw.getValue() ?? 0).toLocaleString()),
    });
    if (d.newBest) {
      const nb = this.add.text(W / 2 + 160, scoreY - 26, "NEW BEST!", title(16, C.gold)).setOrigin(0.5).setAngle(10);
      this.tweens.add({ targets: nb, scale: 1.15, yoyo: true, repeat: -1, duration: 400 });
    }

    const count = (g: Grade) => d.grades.filter((x) => x === g).length;
    inline(this, W / 2, scoreY + 52, [
      { icon: "check", color: C.exact }, ` ${count("exact")} spot on     `,
      { icon: "target", color: C.near }, ` ${count("near")} close     `,
      { icon: "cross", color: C.miss }, ` ${count("miss") + count("timeout")} misread     `,
      { icon: "flame", color: C.gold }, ` best combo ${d.bestCombo}`,
    ], 16, C.text, 0.5);

    // XP bar fills from where it was before this run.
    const now = levelFromXp(G.save.xp);
    const yb = scoreY + 96;
    inline(this, W / 2 - 290, yb, [`+${d.xp} XP   +${d.coins} `, { icon: "coin" }], 16, C.gold, 0, "800");
    this.add.text(W / 2 + 290, yb, `Lv ${now.level} · ${rankFor(now.level)}`, body(14, C.muted)).setOrigin(1, 0.5);
    const xpBar = bar(this, W / 2 - 290, yb + 20, 580, 14, C.accent);
    const before = levelFromXp(Math.max(0, G.save.xp - d.xp));
    const from = before.level < now.level ? 0 : before.into / before.needed;
    this.tweens.addCounter({ from, to: now.into / now.needed, duration: 900, delay: 300, onUpdate: (tw) => xpBar(tw.getValue() ?? 0) });
    if (d.coins > 0) this.time.delayedCall(500, () => sfx.coin());

    const by = py + panelH + 50;
    const m = d.mode;
    const again = m.kind === "career" ? (d.won ? "Replay" : "Try again") : m.kind === "daily" ? "Replay (unscored)" : "Play again";
    new Button(this, W / 2 - 230, by, { w: 210, h: 54, label: again, size: 18 }, () => goTo(this, "Play", m));
    const nextLabel = m.kind === "career" ? "World Tour" : "Menu";
    new Button(this, W / 2 + 230, by, { w: 210, h: 54, label: nextLabel, icon: "next", size: 18, color: C.accent, display: true },
      () => goTo(this, m.kind === "career" ? "Career" : "Menu", m.kind === "career" ? { world: m.world } : undefined));
    if (d.share) {
      const share = new Button(this, W / 2, by, { w: 210, h: 54, label: "Copy result", icon: "clipboard", size: 18 }, () => {
        void navigator.clipboard?.writeText(d.share!).then(
          () => share.label.setText("Copied!"),
          () => share.label.setText("Copy blocked"),
        );
      });
      const g = this.add.graphics();
      const colors = { exact: C.exact, near: C.near, miss: C.miss, timeout: C.miss };
      const x0 = W / 2 - (d.grades.length * 22 - 4) / 2;
      d.grades.forEach((gr, i) => g.fillStyle(colors[gr], 1).fillRoundedRect(x0 + i * 22, by + 40, 18, 18, 4));
    }
    this.input.keyboard?.once("keydown-ENTER", () => goTo(this, m.kind === "career" ? "Career" : "Menu",
      m.kind === "career" ? { world: m.world } : undefined));
  }

  private popStars(n: number, y: number): void {
    for (let i = 0; i < 3; i++) {
      const on = i < n;
      const star = icon(this, W / 2 + (i - 1) * 84, y + (i === 1 ? -10 : 0), "star", 64, on ? C.gold : 0x334155);
      const full = star.scale;
      star.setScale(0);
      this.tweens.add({
        targets: star, scale: full, duration: 320, delay: 300 + i * 260, ease: "Back.Out",
        onStart: () => on && sfx.combo(3 + i * 2),
      });
    }
  }
}
