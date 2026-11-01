import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { G } from "../state";
import { dateKey, dailyNumber } from "../systems/rng";
import { levelFromXp, rankFor } from "../systems/progression";
import { pitchTheme } from "../systems/cosmetics";
import { worldStars } from "../systems/career";
import { LESSONS } from "../academy/curriculum";
import { academyComplete, lessonsDone, nextLesson } from "../systems/academy";
import { bandIcon, icon, inline, type IconName } from "../ui/icons";
import { bar, Button, goTo, panel } from "../ui/widgets";
import { BAND_COLORS, body, C, crisp, H, hex, title, W } from "../ui/theme";

export class MenuScene extends Phaser.Scene {
  constructor() {
    super("Menu");
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.drawBackdrop();

    const logo = this.add.text(70, 92, "PITCHSENSE", title(76, C.text)).setOrigin(0, 0.5);
    logo.setShadow(0, 6, "#000000", 0, true, true);
    this.add.text(74, 150, "READ THE GAME. BEAT THE MODEL.", title(20, C.accent)).setOrigin(0, 0.5);
    this.add.text(74, 184, "Real World Cup, Euro, Copa & AFCON shots. Call the chance before the ball is struck,\nthen see what an xG model trained on 45,000 shots says.",
      body(15, C.muted, "400")).setOrigin(0, 0).setLineSpacing(4);
    this.tweens.add({ targets: logo, scale: 1.02, duration: 1400, yoyo: true, repeat: -1, ease: "Sine.InOut" });

    this.profileCard();

    const s = G.save;
    const today = dateKey(new Date());
    const dailyDone = today in s.daily.scores;
    const totalStars = G.data.career.reduce((a, w, i) => a + worldStars(s.career, i, w.levels.length), 0);
    const maxStars = G.data.career.reduce((a, w) => a + w.levels.length * 3, 0);
    const puzzleStars = Object.values(s.puzzles).reduce((a, b) => a + b, 0);

    const lessons = lessonsDone(s);
    const modes: [IconName, string, string, number, () => void][] = [
      ["book", "Academy", academyComplete(s) ? `Course complete · ${lessons}/${LESSONS.length} lessons`
        : `New to football? Start here · ${lessons}/${LESSONS.length} lessons`, C.gold, () => goTo(this, "Academy")],
      ["trophy", "World Tour", `Career · ${s.trophies.length}/6 trophies · ★ ${totalStars}/${maxStars}`, C.accent,
        () => goTo(this, "Career")],
      ["whistle", "Read the Match", `Referee's Eye or What Happens Next? · real moves`, 0x14b8a6,
        () => goTo(this, "ReadMatch")],
      ["calendar", "Daily Challenge", dailyDone ? `#${dailyNumber(today)} done · ${s.daily.scores[today]} pts · ${s.daily.streak}-day streak`
        : `#${dailyNumber(today)} · 10 shots, same for everyone`, 0x3b82f6, () => goTo(this, "Play", { kind: "daily" })],
      ["stopwatch", "Rapid Fire", `60 seconds, endless shots · best ${s.rapidBest}`, 0xf97316,
        () => goTo(this, "Play", { kind: "rapid" })],
      ["target", "Striker's Instinct", `Find the best spot to shoot · ★ ${puzzleStars}/${G.data.puzzles.length * 3}`, 0xec4899,
        () => goTo(this, "Striker")],
    ];
    modes.forEach(([glyph, label, sub, color, go], i) => {
      const b = new Button(this, 300, 262 + i * 63, { w: 460, h: 56, label, sub, size: 20, align: "left", display: true,
        icon: glyph, iconColor: color }, go);
      b.label.setColor(hex(color));
      b.setAlpha(0).setX(260);
      this.tweens.add({ targets: b, alpha: 1, x: 300, duration: 300, delay: 80 * i, ease: "Back.Out" });
    });

    new Button(this, 166, 650, { w: 192, h: 50, label: "Trophy Room", icon: "medal", size: 16 }, () => goTo(this, "Trophies"));
    new Button(this, 374, 650, { w: 192, h: 50, label: "Kit Room", icon: "bag", size: 16 }, () => goTo(this, "Shop"));
    new Button(this, 580, 650, { w: 192, h: 50, label: "How to play", icon: "help", size: 16 }, () => this.howTo());
    new Button(this, 786, 650, { w: 192, h: 50, label: "Leaderboard", icon: "trophy", size: 16 }, () => goTo(this, "Leaderboard"));

    const mute = new Button(this, W - 60, H - 44, { w: 64, h: 44, label: "", icon: s.settings.muted ? "mute" : "sound", size: 20 }, () => {
      s.settings.muted = !s.settings.muted;
      mute.setIcon(s.settings.muted ? "mute" : "sound");
      G.persist();
      sfx.select();
    });

    this.input.keyboard?.on("keydown-ENTER", () => goTo(this, "Career"));
    if (s.stats.reads === 0 && s.academy.length === 0) this.time.delayedCall(450, () => this.welcome());
  }

  private drawBackdrop(): void {
    const theme = pitchTheme(G.save);
    const g = this.add.graphics();
    g.fillStyle(C.bg, 1).fillRect(0, 0, W, H);
    g.fillStyle(theme.grass, 0.35);
    for (let i = 0; i < 14; i += 2) g.fillRect(640 + i * 50, 0, 50, H);
    g.lineStyle(3, 0xffffff, 0.08).strokeCircle(980, 360, 140);
    g.lineBetween(980, 0, 980, H);
    // Drifting "players" for life in the background.
    for (let i = 0; i < 18; i++) {
      const dot = this.add.circle(Phaser.Math.Between(660, 1260), Phaser.Math.Between(20, 700), 7,
        i % 3 === 0 ? theme.away : theme.home, 0.35);
      this.tweens.add({
        targets: dot,
        x: `+=${Phaser.Math.Between(-60, 60)}`,
        y: `+=${Phaser.Math.Between(-60, 60)}`,
        duration: Phaser.Math.Between(2500, 4500),
        yoyo: true,
        repeat: -1,
        ease: "Sine.InOut",
      });
    }
  }

  private profileCard(): void {
    const s = G.save;
    const info = levelFromXp(s.xp);
    const x = 790;
    const y = 252;
    panel(this, x, y, 430, 196);
    this.add.text(x + 24, y + 30, rankFor(info.level).toUpperCase(), title(18, C.gold)).setOrigin(0, 0.5);
    this.add.text(x + 24, y + 66, `Scout level ${info.level}`, body(26, C.text, "800")).setOrigin(0, 0.5);
    bar(this, x + 24, y + 96, 382, 14, C.accent)(info.into / info.needed);
    this.add.text(x + 24, y + 124, `${info.into} / ${info.needed} XP`, body(13, C.muted)).setOrigin(0, 0.5);
    inline(this, x + 406, y + 124, [{ icon: "coin" }, ` ${s.coins}`], 16, C.gold, 1, "800");
    const acc = s.stats.reads ? Math.round((100 * s.stats.exact) / s.stats.reads) : 0;
    this.add.text(x + 24, y + 162, `${s.stats.reads} reads · ${acc}% spot on · best combo ${s.stats.bestCombo}`,
      body(14, C.muted)).setOrigin(0, 0.5);
  }

  /** First visit: point newcomers at the Academy, let fans go straight in. */
  private welcome(): void {
    const layer = this.add.container(0, 0).setDepth(100);
    layer.add(this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.7).setInteractive());
    const px = W / 2 - 340;
    const py = 150;
    layer.add(panel(this, px, py, 680, 420, C.panel, 1));
    layer.add(icon(this, W / 2, py + 62, "ball", 56, C.accent));
    layer.add(this.add.text(W / 2, py + 128, "WELCOME, SCOUT", title(30, C.accent)).setOrigin(0.5));
    layer.add(this.add.text(W / 2, py + 196,
      "PitchSense asks you to judge real chances from real tournaments.\n" +
      "If you're new to football, the Academy takes you from zero: the rules,\n" +
      "the positions, how attacks work, and how to read a chance like an expert.",
      { ...body(16, C.text, "400"), align: "center" }).setOrigin(0.5).setLineSpacing(6));
    const first = nextLesson(G.save)!;
    const close = () => [layer, learn, play].forEach((o) => o.destroy());
    const learn = new Button(this, W / 2 - 150, py + 330, { w: 270, h: 60, label: "Start the Academy", icon: "book", size: 17,
      display: true, color: C.accent }, () => goTo(this, "Lesson", { id: first.id }));
    const play = new Button(this, W / 2 + 150, py + 330, { w: 270, h: 60, label: "I know football", sub: "show me how to play", size: 17 },
      () => {
        close();
        this.howTo();
      });
    learn.setDepth(101);
    play.setDepth(101);
  }

  private howTo(): void {
    const layer = this.add.container(0, 0).setDepth(100);
    const shade = this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.7).setInteractive();
    layer.add(shade);
    const px = W / 2 - 380;
    const py = 70;
    layer.add(panel(this, px, py, 760, 580, C.panel, 1));
    layer.add(this.add.text(W / 2, py + 42, "HOW TO PLAY", title(30, C.accent)).setOrigin(0.5));
    layer.add(this.add.text(px + 40, py + 80,
      "You see the exact moment a real shot was struck: the shooter (white ring), teammates, defenders\n" +
      "and the keeper. Before the ball flies, call how big the chance was. Then an xG model trained on\n" +
      "45,000 real shots gives its rating — match it to score.", body(15, C.text, "400")).setLineSpacing(5));
    G.data.meta.bands.forEach((b, i) => {
      const y = py + 196 + i * 56;
      layer.add(this.add.text(px + 50, y, `${i + 1}`, title(22, BAND_COLORS[i])).setOrigin(0.5));
      layer.add(inline(this, px + 80, y - 11, [{ icon: bandIcon(i) }, ` ${b.label}`], 18, BAND_COLORS[i], 0, "800"));
      layer.add(this.add.text(px + 80, y + 13, b.gloss, body(14, C.muted, "400")).setOrigin(0, 0.5));
    });
    layer.add(this.add.text(px + 40, py + 476,
      "Same band as the model: 100 pts · one band off: 50 pts · answer fast for a bonus.\n" +
      "Chain spot-on reads for a combo multiplier, up to ×2.", body(15, C.text, "400")).setLineSpacing(5));
    const close = new Button(this, W / 2, py + 548, { w: 220, h: 48, label: "Let's go", display: true, color: C.accent }, () => {
      layer.destroy();
      close.destroy();
    });
    close.setDepth(101);
  }
}
