import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import type { Level, Shot } from "../data/types";
import { PitchView, type Flight } from "../pitch/PitchView";
import { G } from "../state";
import { bandBalance, conceptWeights, pickAdaptive } from "../systems/adaptive";
import { BOSS_ROUND_MS, bossHp, HEARTS, heartsLost, matchStars, ROUND_MS } from "../systems/career";
import { ballSkin, pitchTheme } from "../systems/cosmetics";
import { recordDaily, recordMatch, recordRapid, recordRead } from "../systems/record";
import { dailyNumber, dailyPicks, dateKey, mulberry32 } from "../systems/rng";
import { comboMultiplier, gradeSquare, scoreRound, type Grade, type RoundResult } from "../systems/scoring";
import { CONCEPT_NOTES, lessonById, REASON_LESSONS } from "../academy/curriculum";
import { chip, confetti, currentLevel, settle, teamCode } from "../ui/common";
import { bandIcon, icon, inline, type IconName } from "../ui/icons";
import { BAND_COLORS, body, C, crisp, GRADE_STYLE, H, hex, title, W } from "../ui/theme";
import { bar, Button, floatText, goTo, panel } from "../ui/widgets";
import type { ResultsData } from "./ResultsScene";

export type PlayMode =
  | { kind: "career"; world: number; level: number }
  | { kind: "rapid" }
  | { kind: "daily" };

const RAPID_MS = 60_000;
const RAPID_ROUND_MS = 6_000;
const DAILY_ROUND_MS = 12_000;
/** Shots in a daily: two from each chance band (see dailyPicks). */
const DAILY_SHOTS = 10;
const RAPID_TIME_BONUS: Record<Grade, number> = { exact: 2000, near: 1000, miss: 0, timeout: 0 };

const PANEL_X = 760;
const PANEL_W = 490;

const OUTCOME_STAMP: Record<Flight, [string, number]> = {
  goal: ["GOAL!", C.gold],
  saved: ["SAVED!", 0x93c5fd],
  blocked: ["BLOCKED", 0xd1d5db],
  wide: ["MISSED", 0xd1d5db],
};

export class PlayScene extends Phaser.Scene {
  private mode!: PlayMode;
  private level?: Level;
  private queue: number[] = [];
  private seen = new Set<number>();
  private rng = mulberry32(Date.now() >>> 0);

  private round = 0;
  private score = 0;
  private combo = 0;
  private hearts = HEARTS;
  private bossMax = 0;
  private boss = 0;
  private results: RoundResult[] = [];
  private shot!: Shot;
  private shotIndex = 0;
  private limitMs = ROUND_MS;
  private roundStart = 0;
  private locked = true;
  private clockMs = RAPID_MS;
  private over = false;
  private levelBefore = 1;
  private xpStart = 0;
  private coinsStart = 0;

  private pitch!: PitchView;
  private timer!: (v: number, c?: number) => void;
  private buttons: Button[] = [];
  private panelLayer!: Phaser.GameObjects.Container;
  private scoreText!: Phaser.GameObjects.Text;
  private comboText!: Phaser.GameObjects.Text;
  private hearts3: Phaser.GameObjects.Image[] = [];
  private comboIcon!: Phaser.GameObjects.Image;
  private dailyRow?: Phaser.GameObjects.Graphics;
  private centerText!: Phaser.GameObjects.Text;
  private centerSub!: Phaser.GameObjects.Text;
  private bossBar?: (v: number, c?: number) => void;
  private bossLabel?: Phaser.GameObjects.Text;
  private bossIcon?: Phaser.GameObjects.Image;
  private lastTick = 0;

  constructor() {
    super("Play");
  }

  init(mode: PlayMode): void {
    this.mode = mode;
    this.round = this.score = this.combo = 0;
    this.hearts = HEARTS;
    this.results = [];
    this.seen = new Set();
    this.over = false;
    this.locked = true;
    this.clockMs = RAPID_MS;
    this.buttons = [];
    this.level = undefined;
    this.levelBefore = currentLevel();
    this.xpStart = G.save.xp;
    this.coinsStart = G.save.coins;
    this.bossBar = this.bossLabel = this.bossIcon = this.dailyRow = undefined;
    this.hearts3 = [];

    if (mode.kind === "career") {
      this.level = G.data.career[mode.world].levels[mode.level];
      this.queue = this.level.shots.map((id) => G.data.shots.indexOf(G.data.byId.get(id)!));
      this.limitMs = this.level.boss ? BOSS_ROUND_MS : ROUND_MS;
      this.bossMax = this.boss = this.level.boss ? bossHp(this.queue.length) : 0;
    } else if (mode.kind === "daily") {
      const pool = G.data.pool;
      this.queue = dailyPicks(pool.map((i) => G.data.shots[i].band), dateKey(new Date())).map((p) => pool[p]);
      this.limitMs = DAILY_ROUND_MS;
    } else {
      this.queue = [];
      this.limitMs = RAPID_ROUND_MS;
    }
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    const theme = pitchTheme(G.save);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    this.pitch = new PitchView(this, 40, 158, 8.5, theme, ballSkin(G.save));
    this.timer = bar(this, 40, 112, 680, 12, C.accent);
    this.timer(1);
    this.hud();
    panel(this, PANEL_X, 104, PANEL_W, 600);
    this.panelLayer = this.add.container(0, 0);

    const keys = ["ONE", "TWO", "THREE", "FOUR", "FIVE"];
    keys.forEach((k, i) => this.input.keyboard?.on(`keydown-${k}`, () => this.buttons[i]?.press(() => this.pick(i))));
    this.input.keyboard?.on("keydown-ESC", () => this.quit());

    if (this.level?.boss) this.bossIntro();
    this.time.delayedCall(this.level?.boss ? 1900 : 350, () => this.nextRound());
  }

  private bossIntro(): void {
    sfx.bossHit();
    const shade = this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.6).setDepth(60);
    const t1 = this.add.text(W / 2, H / 2 - 40, "FINAL BOSS", title(28, C.text)).setOrigin(0.5).setDepth(61);
    const t2 = this.add.container(W / 2, H / 2 + 20, [
      icon(this, -210, 0, "model", 64, C.boss),
      this.add.text(40, 0, "THE MODEL", title(64, C.boss)).setOrigin(0.5).setStroke("#000000", 10),
    ]).setDepth(61).setScale(3).setAlpha(0);
    const t3 = this.add.text(W / 2, H / 2 + 84, "Out-read the xG model to lift the trophy", body(16, C.muted)).setOrigin(0.5).setDepth(61);
    this.tweens.add({ targets: t2, scale: 1, alpha: 1, duration: 420, ease: "Back.Out", onComplete: () => this.cameras.main.shake(200, 0.01) });
    this.tweens.add({ targets: [shade, t1, t2, t3], alpha: 0, delay: 1500, duration: 350, onComplete: () => [shade, t1, t2, t3].forEach((o) => o.destroy()) });
  }

  // ------------------------------------------------------------------ HUD --
  private hud(): void {
    const m = this.mode;
    const name = m.kind === "career" ? G.data.career[m.world].name.toUpperCase()
      : m.kind === "daily" ? `DAILY CHALLENGE #${dailyNumber(dateKey(new Date()))}` : "RAPID FIRE";
    const sub = m.kind === "career" ? `${this.level!.stage} · ${this.level!.home} vs ${this.level!.away}`
      : m.kind === "daily" ? "10 shots · two from every chance band" : "Exact read +2s · close read +1s";
    this.add.text(40, 30, name, title(22, this.level?.boss ? C.boss : C.accent)).setOrigin(0, 0.5);
    this.add.text(40, 60, sub, body(14, C.muted)).setOrigin(0, 0.5);
    if (m.kind === "career") this.hearts3 = Array.from({ length: HEARTS }, (_, i) => icon(this, 50 + i * 26, 88, "heart", 20, C.miss));
    if (m.kind === "daily") this.dailyRow = this.add.graphics();

    this.centerText = this.add.text(W / 2 + 20, 38, "", title(30)).setOrigin(0.5);
    this.centerSub = this.add.text(W / 2 + 20, 74, "", body(14, C.muted)).setOrigin(0.5);

    this.add.text(W - 40, 22, "SCORE", body(12, C.muted, "800")).setOrigin(1, 0.5);
    this.scoreText = this.add.text(W - 40, 52, "0", title(32)).setOrigin(1, 0.5);
    this.comboText = this.add.text(W - 40, 86, "", body(15, C.gold, "800")).setOrigin(1, 0.5);
    this.comboIcon = icon(this, 0, 86, "flame", 18, C.gold).setVisible(false);

    new Button(this, W - 230, 44, { w: 96, h: 38, label: "Quit", icon: "cross", size: 14 }, () => this.quit());
    this.refreshHud();
  }

  private refreshHud(): void {
    this.scoreText.setText(this.score.toLocaleString());
    this.comboText.setText(this.combo >= 2 ? `COMBO ${this.combo} · ×${comboMultiplier(this.combo)}` : "");
    this.comboIcon.setVisible(this.combo >= 2).setX(W - 40 - this.comboText.width - 14);
    this.hearts3.forEach((h, i) => {
      const full = i < this.hearts;
      h.setTexture(full ? "icon.heart" : "icon.heartEmpty").setTint(full ? C.miss : 0x475569);
    });
    if (this.mode.kind === "career") {
      const lv = this.level!;
      const upto = this.revealedMinute;
      const goals = (team: string) => lv.goals.filter(([min, t]) => t === team && min <= upto).length;
      this.centerText.setText(`${teamCode(lv.home)}  ${goals(lv.home)} – ${goals(lv.away)}  ${teamCode(lv.away)}`);
      this.centerSub.setText(this.shot ? `${this.shot.minute}'  ·  shot ${this.round} of ${this.queue.length}` : "");
    } else if (this.mode.kind === "daily") {
      this.centerText.setText(`${this.round} / ${this.queue.length}`);
      this.drawDailyRow();
    }
    if (this.bossBar) {
      this.bossBar(this.boss / this.bossMax, C.boss);
      this.bossLabel!.setText(`${Math.max(0, this.boss)} / ${this.bossMax} HP`);
    }
  }

  /** Minute up to which goals have happened on the scoreboard. */
  private revealedMinute = 0;

  // -------------------------------------------------------------- rounds --
  private nextRound(): void {
    if (this.over) return;
    if (this.matchOver()) return this.finish();
    if (this.mode.kind === "rapid") this.queue.push(this.pickRapid());

    this.shotIndex = this.queue[this.round];
    this.seen.add(this.shotIndex);
    this.shot = G.data.shots[this.shotIndex];
    this.round += 1;
    this.revealedMinute = this.shot.minute - 1;
    this.refreshHud();

    this.pitch.stage(this.shot.x, this.shot.y, this.shot.frame, this.shot.player);
    this.buildQuestion();
    this.locked = false;
    this.roundStart = this.time.now;
    this.lastTick = 0;
    if (this.round === 1 && this.mode.kind !== "rapid") sfx.whistle();
  }

  private pickRapid(): number {
    const pool = G.data.pool;
    const weights = conceptWeights(G.save.concepts, G.data.meta.concepts);
    const boost = bandBalance(pool.map((i) => G.data.shots[i].band));
    const exclude = new Set(pool.map((idx, i) => (this.seen.has(idx) ? i : -1)).filter((i) => i >= 0));
    return pool[pickAdaptive(pool.map((i) => G.data.concepts[i]), weights, this.rng, boost, exclude)];
  }

  private buildQuestion(): void {
    this.panelLayer.removeAll(true);
    this.buttons.forEach((b) => b.destroy());
    this.buttons = [];
    const s = this.shot;
    let y = 134;

    if (this.level?.boss) {
      if (!this.bossBar) {
        this.bossIcon = icon(this, PANEL_X + 40, 136, "model", 30, C.boss);
        this.add.text(PANEL_X + 66, 126, "BOSS: THE MODEL", title(15, C.boss)).setOrigin(0, 0.5);
        this.bossLabel = this.add.text(PANEL_X + PANEL_W - 24, 126, "", body(13, C.muted)).setOrigin(1, 0.5);
        this.bossBar = bar(this, PANEL_X + 66, 142, PANEL_W - 90, 12, C.boss);
        this.refreshHud();
      }
      y = 184;
    }

    const p = this.panelLayer;
    const match = G.data.meta.matches[String(s.match)];
    const opp = match ? (match.home === s.team ? match.away : match.home) : "";
    p.add(this.add.text(PANEL_X + 24, y, s.player, title(22)).setOrigin(0, 0.5));
    p.add(this.add.text(PANEL_X + 24, y + 30,
      `${s.team}${opp ? ` vs ${opp}` : ""} · ${s.minute}'${this.mode.kind !== "career" && match ? ` · ${match.tournament}` : ""}`,
      body(14, C.muted)).setOrigin(0, 0.5));
    let cx = PANEL_X + 24;
    const tags: [string, IconName?][] = [[`${Math.round(s.distance)} yds`, "ruler"], s.header ? ["Header", "head"] : ["Foot", "boot"],
      ...G.conceptsOf(s).filter((c) => c !== "Standard chance" && c !== "Header" && c !== "Close range" && c !== "Long range")
        .map((c): [string] => [c])];
    for (const [tag, glyph] of tags.slice(0, 4)) cx += chip(this, cx, y + 64, tag, C.panelHi, p, glyph) + 8;

    p.add(this.add.text(PANEL_X + 24, y + 104, "HOW BIG WAS THE CHANCE?", title(16, C.accent)).setOrigin(0, 0.5));
    const bands = G.data.meta.bands;
    const top = y + 150;
    const step = this.level?.boss ? 66 : 74;
    bands.forEach((b, i) => {
      const btn = new Button(this, PANEL_X + PANEL_W / 2, top + i * step,
        { w: PANEL_W - 40, h: step - 10, label: b.label, sub: b.gloss, key: String(i + 1), align: "left", size: 19,
          icon: bandIcon(i), iconColor: BAND_COLORS[i] },
        () => this.pick(i));
      btn.label.setColor(hex(BAND_COLORS[i]));
      btn.setAlpha(0);
      this.tweens.add({ targets: btn, alpha: 1, duration: 200, delay: 40 * i });
      this.buttons.push(btn);
    });
  }

  update(time: number, delta: number): void {
    if (this.over) return;
    if (this.mode.kind === "rapid" && this.round > 0) {
      this.clockMs -= delta;
      this.centerText.setText(`${Math.max(0, Math.ceil(this.clockMs / 1000))}s`);
      this.centerSub.setText(`${this.results.length} reads`);
      this.timer(this.clockMs / RAPID_MS, this.clockMs < 10_000 ? C.miss : C.accent);
      if (this.clockMs <= 0 && !this.locked) return this.finish();
    }
    if (this.locked) return;
    const elapsed = time - this.roundStart;
    if (this.mode.kind !== "rapid") {
      const left = 1 - elapsed / this.limitMs;
      this.timer(left, left < 0.3 ? C.miss : left < 0.6 ? C.near : C.accent);
      const secs = Math.ceil((this.limitMs - elapsed) / 1000);
      if (left < 0.3 && secs !== this.lastTick) {
        this.lastTick = secs;
        sfx.tick();
      }
      if (elapsed >= this.limitMs) this.pick(null);
    }
  }

  private pick(guess: number | null): void {
    if (this.locked || this.over) return;
    this.locked = true;
    const elapsed = this.time.now - this.roundStart;
    const s = this.shot;
    const result = scoreRound(guess, s.band, elapsed, this.limitMs, this.combo);
    this.combo = result.combo;
    this.score += result.total;
    this.results.push(result);
    if (guess !== null) {
      sfx.select();
      this.buttons[guess].setSelected(true);
    }
    this.buttons.forEach((b, i) => {
      if (i !== guess) b.setEnabled(false);
    });

    recordRead(G.save, G.conceptsOf(s), s.band, result, elapsed);
    settle(this, this.levelBefore);
    this.levelBefore = currentLevel();

    const rapid = this.mode.kind === "rapid";
    if (rapid) this.clockMs += RAPID_TIME_BONUS[result.grade];

    // The model "locks in" its own call next to yours.
    const modelBtn = this.buttons[s.band];
    const tag = inline(this, modelBtn.x + modelBtn.width / 2 - 20, modelBtn.y, [{ icon: "model" }, " MODEL"], 13, C.boss, 1, "800")
      .setScale(0);
    this.panelLayer.add(tag);
    this.tweens.add({ targets: tag, scale: 1, duration: 220, delay: rapid ? 0 : 200, ease: "Back.Out" });

    this.time.delayedCall(rapid ? 100 : 550, async () => {
      const flight = await this.pitch.shoot(s.x, s.y, s.end, s.outcome, rapid ? 2.2 : 1);
      this.revealedMinute = s.minute;
      this.outcome(flight, rapid);
      this.applyGrade(result, rapid);
      this.refreshHud();
      if (this.over) return;
      if (rapid) {
        this.time.delayedCall(450, () => (this.clockMs <= 0 ? this.finish() : this.nextRound()));
      } else {
        this.time.delayedCall(500, () => this.reveal(result, guess));
      }
    });
  }

  private outcome(flight: Flight, quick: boolean): void {
    const [text, color] = OUTCOME_STAMP[flight];
    if (flight === "goal") {
      sfx.goal();
      this.cameras.main.shake(quick ? 120 : 280, 0.008);
      const g = this.pitch.at(120, 40);
      confetti(this, g.x, g.y, [pitchTheme(G.save).home, C.gold, 0xffffff], quick ? 30 : 90);
    } else if (flight === "saved") sfx.save();
    else sfx.groan();
    if (quick) return;
    const c = this.pitch.at(96, 40);
    const stamp = this.add.text(c.x, c.y, text, title(64, color)).setOrigin(0.5).setAngle(-8).setScale(2.4).setAlpha(0).setDepth(30);
    stamp.setStroke("#000000", 10);
    this.tweens.add({ targets: stamp, scale: 1, alpha: 1, duration: 260, ease: "Back.Out" });
    this.tweens.add({ targets: stamp, alpha: 0, delay: 1300, duration: 400, onComplete: () => stamp.destroy() });
  }

  private applyGrade(r: RoundResult, quick: boolean): void {
    const style = GRADE_STYLE[r.grade];
    const p = this.pitch.at(this.shot.x, this.shot.y);
    floatText(this, p.x, p.y - 30, r.total > 0 ? `${style.label} +${r.total}` : style.label, style.color, quick ? 22 : 26);
    if (r.grade === "exact") sfx.exact();
    else if (r.grade === "near") sfx.near();
    else sfx.miss();
    if (r.combo >= 2 && r.grade === "exact") {
      sfx.combo(r.combo);
      this.tweens.add({ targets: this.comboText, scale: 1.4, duration: 120, yoyo: true });
    }

    if (this.mode.kind !== "career") return;
    if (this.level!.boss && r.total > 0) {
      this.boss -= r.total;
      sfx.bossHit();
      floatText(this, PANEL_X + PANEL_W - 80, 170, `-${r.total}`, C.boss, 26);
      this.tweens.add({ targets: this.bossIcon, x: "+=8", duration: 50, yoyo: true, repeat: 3 });
    }
    const lost = heartsLost(r.grade);
    if (lost) {
      this.hearts -= lost;
      sfx.heartLost();
      const red = this.add.rectangle(W / 2, H / 2, W, H, C.miss, 0.22).setDepth(45);
      this.tweens.add({ targets: red, alpha: 0, duration: 350, onComplete: () => red.destroy() });
      const lostHeart = this.hearts3[Math.max(0, this.hearts)];
      if (lostHeart) this.tweens.add({ targets: lostHeart, scale: lostHeart.scale * 1.4, duration: 120, yoyo: true });
      if (this.level!.boss) floatText(this, PANEL_X + 120, 170, "THE MODEL STRIKES", C.miss, 20);
    }
  }

  /** Career and daily end when the shots run out; a career match also on no hearts or a dead boss. */
  private matchOver(): boolean {
    if (this.mode.kind === "rapid") return false;
    if (this.round >= this.queue.length) return true;
    return this.mode.kind === "career" && (this.hearts <= 0 || (this.level!.boss && this.boss <= 0));
  }

  private reveal(r: RoundResult, guess: number | null): void {
    if (this.over) return;
    this.buttons.forEach((b) => b.destroy());
    this.buttons = [];
    this.panelLayer.removeAll(true);
    const s = this.shot;
    const p = this.panelLayer;
    const bands = G.data.meta.bands;
    const x = PANEL_X + 24;
    let y = this.level?.boss ? 190 : 140;

    const style = GRADE_STYLE[r.grade];
    p.add(this.add.text(x, y, style.label, title(34, style.color)).setOrigin(0, 0.5));
    p.add(this.add.text(PANEL_X + PANEL_W - 24, y, `+${r.total}`, title(30, r.total ? C.gold : C.muted)).setOrigin(1, 0.5));
    y += 36;
    const parts = [`read ${r.base}`];
    if (r.speed) parts.push(`speed +${r.speed}`);
    if (r.multiplier > 1) parts.push(`combo ×${r.multiplier}`);
    p.add(this.add.text(x, y, parts.join("  ·  "), body(14, C.muted)).setOrigin(0, 0.5));

    y += 40;
    p.add(this.add.text(x, y, "YOU", body(12, C.muted, "800")).setOrigin(0, 0.5));
    p.add(guess === null ? this.add.text(x + 70, y, "no call", body(17, C.muted, "800")).setOrigin(0, 0.5)
      : inline(this, x + 70, y, [{ icon: bandIcon(guess) }, ` ${bands[guess].label}`], 17, BAND_COLORS[guess], 0, "800"));
    y += 30;
    p.add(this.add.text(x, y, "MODEL", body(12, C.boss, "800")).setOrigin(0, 0.5));
    p.add(inline(this, x + 70, y, [{ icon: bandIcon(s.band) }, ` ${bands[s.band].label}  ·  ${Math.round(s.xg * 100)}% xG`],
      17, BAND_COLORS[s.band], 0, "800"));
    y += 30;
    p.add(this.add.text(x, y, "RESULT", body(12, C.muted, "800")).setOrigin(0, 0.5));
    const happened = s.goal ? "GOAL" : s.outcome.replace("Off T", "Off target").replace("Saved Off T", "Saved");
    const psxg = s.psxg !== null ? `  ·  ${Math.round(s.psxg * 100)}% after the strike` : "";
    p.add(this.add.text(x + 70, y, `${happened}${psxg}`, body(15)).setOrigin(0, 0.5));

    y += 40;
    p.add(this.add.text(x, y, "WHY THE MODEL RATED IT THAT WAY", title(13, C.accent)).setOrigin(0, 0.5));
    y += 22;
    const lines: [IconName | null, string, number][] = [
      ...s.helped.slice(0, 2).map(([f, t]) => ["up", `${f}: ${t}`, C.exact] as [IconName, string, number]),
      ...s.hurt.slice(0, 2).map(([f, t]) => ["down", `${f}: ${t}`, C.miss] as [IconName, string, number]),
    ];
    if (!lines.length) lines.push([null, "A very ordinary chance — nothing pushed it far from an average shot.", C.muted]);
    for (const [arrow, text, color] of lines) {
      if (arrow) p.add(icon(this, x + 6, y + 9, arrow, 11, color));
      const t = this.add.text(x + 20, y, text, { ...body(14, C.text, "400"), wordWrap: { width: PANEL_W - 70 } }).setOrigin(0, 0);
      p.add(t);
      y += t.height + 8;
    }
    y = this.scoutNote(x, y + 8);
    if (r.grade === "timeout") {
      p.add(this.add.text(x, y + 4, "Out of time — go with your gut next time.", body(13, C.muted, "400")).setOrigin(0, 0));
    }

    for (const o of p.list) (o as Phaser.GameObjects.Text).setAlpha(0);
    this.tweens.add({ targets: p.list, alpha: 1, duration: 220 });

    const last = this.matchOver();
    const next = new Button(this, PANEL_X + PANEL_W / 2, 662, {
      w: PANEL_W - 40, h: 54, label: last ? "FULL TIME" : "NEXT SHOT", icon: "next", display: true, size: 20, color: C.accent,
    }, () => {
      next.destroy();
      this.nextRound();
    });
    const go = () => next.active && next.press(() => {
      next.destroy();
      this.nextRound();
    });
    this.input.keyboard?.once("keydown-SPACE", go);
    this.input.keyboard?.once("keydown-ENTER", go);
  }

  /**
   * The Academy idea behind this shot: a note on its most telling concept, or
   * else on the model's top reason, and the lesson that explains it. Returns
   * the y below it.
   */
  private scoutNote(x: number, y: number): number {
    const s = this.shot;
    const concept = G.conceptsOf(s).find((c) => c !== "Standard chance" && CONCEPT_NOTES[c]);
    const reason = [...s.hurt, ...s.helped].map(([f]) => f).find((f) => REASON_LESSONS[f]);
    const note = concept ? CONCEPT_NOTES[concept].note : reason ? `${reason} decided a lot here.` : null;
    const lesson = lessonById(concept ? CONCEPT_NOTES[concept].lesson : reason ? REASON_LESSONS[reason] : "xg");
    if (!note || !lesson) return y;
    const p = this.panelLayer;
    p.add(icon(this, x + 8, y + 9, "bulb", 16, C.gold));
    const t = this.add.text(x + 24, y, note, { ...body(14, C.gold, "600"), wordWrap: { width: PANEL_W - 74 } });
    p.add(t);
    y += t.height + 4;
    p.add(inline(this, x + 24, y + 9, [{ icon: "book" }, ` Learn why in the Academy: ${lesson.title}`], 12, C.muted));
    return y + 24;
  }

  /** Daily: a coloured square per read so far, like the shared result. */
  private drawDailyRow(): void {
    const g = this.dailyRow!.clear();
    const n = this.results.length;
    const size = 14;
    const x0 = W / 2 + 20 - (n * (size + 4) - 4) / 2;
    const colors = { exact: C.exact, near: C.near, miss: C.miss, timeout: C.miss };
    this.results.forEach((r, i) => g.fillStyle(colors[r.grade], 1).fillRoundedRect(x0 + i * (size + 4), 74 - size / 2, size, size, 3));
  }

  // ------------------------------------------------------------- finish --
  private finish(): void {
    if (this.over) return;
    this.over = true;
    this.locked = true;
    sfx.whistle();
    const m = this.mode;
    const grades = this.results.map((r) => r.grade);
    const base = this.results.reduce((a, r) => a + r.base, 0);
    const data: ResultsData = {
      mode: m,
      score: this.score,
      grades,
      bestCombo: Math.max(0, ...this.results.map((r) => r.combo)),
      headline: "FULL TIME",
      sub: "",
      stars: null,
      xp: 0,
      coins: 0,
      share: null,
      newBest: false,
      trophy: null,
      won: true,
      post: null,
    };

    if (m.kind === "career") {
      const lv = this.level!;
      const played = Math.max(1, this.results.length);
      const cleared = this.hearts > 0 && (!lv.boss || this.boss <= 0);
      const stars = matchStars(base / played, cleared);
      const trophy = lv.boss ? G.data.career[m.world].name : null;
      recordMatch(G.save, m.world, m.level, stars, this.hearts === HEARTS, trophy);
      data.stars = stars;
      data.won = cleared;
      data.trophy = cleared && trophy ? trophy : null;
      data.headline = cleared ? (lv.boss ? "CHAMPIONS!" : "MATCH WON") : lv.boss ? "THE MODEL WINS" : "OUT OF HEARTS";
      data.sub = `${lv.home} ${lv.homeScore}–${lv.awayScore} ${lv.away} · real full-time score`;
    } else if (m.kind === "daily") {
      const key = dateKey(new Date());
      const counted = recordDaily(G.save, key, this.score);
      data.headline = "DAILY DONE";
      data.sub = counted ? `Streak: ${G.save.daily.streak} day${G.save.daily.streak === 1 ? "" : "s"}`
        : `Replay — today's scored attempt was ${G.save.daily.scores[key]} pts`;
      data.share = `PitchSense Daily #${dailyNumber(key)}\n${grades.map(gradeSquare).join("")}\n${this.score} pts`;
      // Only the day's first, scored attempt, with all ten shots, can go on the board.
      if (counted && this.results.length === DAILY_SHOTS) data.post = { mode: "daily", day: key, score: this.score, reads: this.results.length };
    } else {
      data.newBest = recordRapid(G.save, this.score);
      data.headline = "TIME UP";
      data.sub = data.newBest ? "New personal best!" : `Best: ${G.save.rapidBest}`;
      if (data.newBest && this.results.length > 0) data.post = { mode: "rapid", day: null, score: this.score, reads: this.results.length };
    }
    settle(this, this.levelBefore);
    data.xp = G.save.xp - this.xpStart;
    data.coins = G.save.coins - this.coinsStart;
    this.time.delayedCall(700, () => goTo(this, "Results", data));
  }

  private quit(): void {
    this.over = true;
    goTo(this, this.mode.kind === "career" ? "Career" : "Menu");
  }
}
