import Phaser from "phaser";

import { G } from "../state";
import { BOSS_ROUND_MS, bossHp, HEARTS, isUnlocked, levelKey, ROUND_MS, worldStars } from "../systems/career";
import { teamCode } from "../ui/common";
import { icon, inline, starRow } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, Button, goTo, panel, stars } from "../ui/widgets";

const STAGE_SHORT: Record<string, string> = {
  "Group Stage": "GROUP", "Round of 16": "LAST 16", "Quarter-finals": "QUARTER", "Semi-finals": "SEMI", Final: "FINAL",
};

/** The World Tour map: a tab per tournament, a winding road of matches. */
export class CareerScene extends Phaser.Scene {
  private world = 0;
  private layer!: Phaser.GameObjects.Container;
  private tabs: Button[] = [];

  constructor() {
    super("Career");
  }

  init(data: { world?: number }): void {
    const sizes = G.data.career.map((w) => w.levels.length);
    // Open on the furthest unlocked world unless told otherwise.
    const furthest = sizes.reduce((best, _, w) => (isUnlocked(G.save.career, sizes, w, 0) ? w : best), 0);
    this.world = data?.world ?? furthest;
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this);
    this.add.text(W / 2, 44, "WORLD TOUR", title(34, C.accent)).setOrigin(0.5);
    this.add.text(W / 2, 80, "Follow each champion's road to the trophy. Beat The Model in the final to unlock the next tournament.",
      body(14, C.muted)).setOrigin(0.5);
    this.layer = this.add.container(0, 0);
    this.drawTabs();
    this.drawWorld();
    this.input.keyboard?.on("keydown-LEFT", () => this.select(Math.max(0, this.world - 1)));
    this.input.keyboard?.on("keydown-RIGHT", () => this.select(Math.min(G.data.career.length - 1, this.world + 1)));
  }

  private sizes(): number[] {
    return G.data.career.map((w) => w.levels.length);
  }

  private drawTabs(): void {
    this.tabs.forEach((t) => t.destroy());
    const worlds = G.data.career;
    const w = 196;
    const x0 = W / 2 - ((worlds.length - 1) * (w + 8)) / 2;
    this.tabs = worlds.map((world, i) => {
      const open = isUnlocked(G.save.career, this.sizes(), i, 0);
      const won = G.save.trophies.includes(world.name);
      const sub = `★ ${worldStars(G.save.career, i, world.levels.length)}/${world.levels.length * 3}`;
      const glyph = won ? "trophy" : open ? undefined : "lock";
      const b = new Button(this, x0 + i * (w + 8), 136, { w, h: 56, label: world.name, sub, size: 14, icon: glyph,
        iconColor: won ? C.gold : C.muted }, () => this.select(i));
      b.setSelected(i === this.world);
      if (!open) b.setAlpha(0.5);
      return b;
    });
  }

  private select(i: number): void {
    if (i === this.world) return;
    this.world = i;
    this.tabs.forEach((t, j) => t.setSelected(j === i));
    this.drawWorld();
  }

  private drawWorld(): void {
    this.layer.removeAll(true);
    const world = G.data.career[this.world];
    const n = world.levels.length;
    const sizes = this.sizes();

    // A winding road across the screen.
    const pts = world.levels.map((_, i) => {
      const t = n === 1 ? 0.5 : i / (n - 1);
      return { x: 120 + t * (W - 240), y: 400 + Math.sin(t * Math.PI * 2.2) * 110 };
    });
    const road = this.add.graphics();
    road.lineStyle(14, 0x000000, 0.35);
    road.strokePoints(pts.map((p) => new Phaser.Math.Vector2(p.x, p.y + 5)));
    road.lineStyle(10, C.edge, 1);
    road.strokePoints(pts.map((p) => new Phaser.Math.Vector2(p.x, p.y)));
    this.layer.add(road);

    world.levels.forEach((lv, i) => {
      const { x, y } = pts[i];
      const open = isUnlocked(G.save.career, sizes, this.world, i);
      const got = G.save.career[levelKey(this.world, i)] ?? 0;
      const r = lv.boss ? 50 : 38;
      const color = !open ? 0x1f2937 : lv.boss ? C.boss : got ? C.accent : C.panelHi;
      const node = this.add.circle(x, y, r, color).setStrokeStyle(4, open ? 0xffffff : 0x374151, open ? 0.9 : 1);
      const opp = lv.home === world.champion ? lv.away : lv.home;
      const mark = lv.boss ? icon(this, x, y, "model", 40, 0xffffff)
        : open ? this.add.text(x, y, teamCode(opp), title(18)).setOrigin(0.5) : icon(this, x, y, "lock", 26, 0x64748b);
      const stage = this.add.text(x, y - r - 18, STAGE_SHORT[lv.stage] ?? lv.stage, title(13, lv.boss ? C.boss : C.muted)).setOrigin(0.5);
      const st = starRow(this, x, y + r + 16, got, 17);
      this.layer.add([node, mark, stage, st]);

      // The next level to play bobs to draw the eye.
      const isNext = open && !got;
      if (isNext) this.tweens.add({ targets: [node, mark], y: "-=8", yoyo: true, repeat: -1, duration: 600, ease: "Sine.InOut" });
      if (open) {
        node.setInteractive({ useHandCursor: true });
        node.on("pointerover", () => node.setScale(1.08));
        node.on("pointerout", () => node.setScale(1));
        node.on("pointerdown", () => this.preview(i));
      }
      node.setScale(0);
      mark.setAlpha(0);
      this.tweens.add({ targets: node, scale: 1, duration: 300, delay: 50 * i, ease: "Back.Out" });
      this.tweens.add({ targets: mark, alpha: 1, duration: 300, delay: 50 * i + 150 });
    });

    const won = G.save.trophies.includes(world.name);
    this.layer.add(won ? inline(this, W / 2, 650, [{ icon: "trophy" }, ` ${world.name} won · ${world.champion}'s road complete`], 16, C.gold, 0.5)
      : this.add.text(W / 2, 650, `Play as a scout on ${world.champion}'s road · ${n} matches`, body(16, C.muted)).setOrigin(0.5));
  }

  private preview(i: number): void {
    const world = G.data.career[this.world];
    const lv = world.levels[i];
    const box = this.add.container(0, 0).setDepth(50);
    const shade = this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.65).setInteractive();
    box.add(shade);
    box.add(panel(this, W / 2 - 280, 170, 560, 380, C.panel, 1));
    box.add(this.add.text(W / 2, 214, `${world.name.toUpperCase()} · ${lv.stage.toUpperCase()}`, title(18, lv.boss ? C.boss : C.accent)).setOrigin(0.5));
    box.add(this.add.text(W / 2, 266, `${lv.home}  vs  ${lv.away}`, title(28)).setOrigin(0.5));
    box.add(this.add.text(W / 2, 302, lv.date, body(14, C.muted)).setOrigin(0.5));
    const got = G.save.career[levelKey(this.world, i)] ?? 0;
    const rules = lv.boss
      ? [`BOSS FIGHT — The Model has ${bossHp(lv.shots.length)} HP`, `Your points are damage · ${BOSS_ROUND_MS / 1000}s per shot`,
        `${HEARTS} hearts · a misread lets The Model strike back`]
      : [`${lv.shots.length} real shots from this match, in order`, `${HEARTS} hearts · a misread costs one · ${ROUND_MS / 1000}s per shot`,
        "★ avg 50+   ★★ avg 70+   ★★★ avg 85+"];
    rules.forEach((r, k) => box.add(this.add.text(W / 2, 352 + k * 30, r, body(16)).setOrigin(0.5)));
    box.add(this.add.text(W / 2, 450, `Best: ${stars(got)}`, title(18, got ? C.gold : C.muted)).setOrigin(0.5));
    const cancel = new Button(this, W / 2 - 130, 506, { w: 200, h: 52, label: "Not yet", size: 16 }, () => {
      box.destroy();
      cancel.destroy();
      play.destroy();
    });
    const play = new Button(this, W / 2 + 130, 506, { w: 200, h: 52, label: lv.boss ? "FIGHT!" : "KICK OFF", display: true, size: 20,
      color: lv.boss ? C.boss : C.accent }, () => goTo(this, "Play", { kind: "career", world: this.world, level: i }));
    cancel.setDepth(51);
    play.setDepth(51);
    this.input.keyboard?.once("keydown-ENTER", () => play.press(() => goTo(this, "Play", { kind: "career", world: this.world, level: i })));
  }
}
