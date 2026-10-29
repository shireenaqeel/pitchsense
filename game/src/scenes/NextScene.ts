import Phaser from "phaser";

import type { Mark, Pt } from "../academy/curriculum";
import { Diagram } from "../academy/Diagram";
import { sfx } from "../audio/sfx";
import { ACTOR, CALLS, KEEPER, type Moment, TEAMMATE } from "../data/types";
import { HALF_X, PitchView } from "../pitch/PitchView";
import { G } from "../state";
import { ballSkin, pitchTheme } from "../systems/cosmetics";
import { commonCall, judgeNext, NEXT_EXACT, pickMoments } from "../systems/next";
import { confetti, currentLevel, settle } from "../ui/common";
import { icon, type IconName, inline } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, bar, Button, goTo, panel } from "../ui/widgets";
import { VIEWS } from "./LessonScene";

const PANEL_X = 760;
const PANEL_W = 490;
const TEXT_X = PANEL_X + 24;
const TEXT_W = PANEL_W - 48;
const KEYS = ["ONE", "TWO", "THREE", "FOUR"];
const CALL_ICONS: IconName[] = ["goal", "next", "curve", "boot"];
const DID = ["shot", "passed", "crossed", "dribbled"];

/** What Happens Next?: real moments from 360 matches; call the player's next action. */
export class NextScene extends Phaser.Scene {
  private moments: Moment[] = [];
  private i = 0;
  private score = 0;
  private answered = true;
  private pitch!: PitchView;
  private diagram!: Diagram;
  private side!: Phaser.GameObjects.Container;
  private buttons: Button[] = [];
  private progress!: Phaser.GameObjects.Text;

  constructor() {
    super("Next");
  }

  init(): void {
    this.moments = pickMoments(G.data.moments, Math.random);
    this.i = 0;
    this.score = 0;
    this.buttons = [];
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this, "ReadMatch");
    this.add.text(190, 30, "READ THE MATCH · REAL MOVES", body(12, C.muted, "800")).setOrigin(0, 0.5);
    this.add.text(190, 60, "WHAT HAPPENS NEXT?", title(26, C.gold)).setOrigin(0, 0.5);
    this.progress = this.add.text(PANEL_X + PANEL_W, 60, "", body(15, C.text, "800")).setOrigin(1, 0.5);

    const [ox, oy, s, view] = VIEWS.half;
    const theme = pitchTheme(G.save);
    this.pitch = new PitchView(this, ox, oy, s, theme, ballSkin(G.save), view);
    this.diagram = new Diagram(this, this.pitch, theme);
    panel(this, PANEL_X, 104, PANEL_W, 600);
    this.side = this.add.container(0, 0);
    KEYS.forEach((k, n) => this.input.keyboard?.on(`keydown-${k}`, () => this.answer(n)));
    this.input.keyboard?.on("keydown-ENTER", () => this.answered && this.i < this.moments.length && this.advance());
    this.show();
  }

  private clearSide(): void {
    this.side.removeAll(true);
    this.buttons.forEach((b) => b.destroy());
    this.buttons = [];
  }

  /** Arrows along a ball path, keeping only the part on the visible half. */
  private path(points: [number, number][], style: (k: number) => "pass" | "run" | "shot" | "trail"): Mark[] {
    const marks: Mark[] = [];
    for (let k = 0; k + 1 < points.length; k++) {
      const [from, to] = [points[k], points[k + 1]];
      if (from[0] < HALF_X || to[0] < HALF_X) continue;
      marks.push({ kind: "arrow", from: from as Pt, to: [Math.min(to[0], 120.5), to[1]], style: style(k) });
    }
    return marks;
  }

  private show(): void {
    this.clearSide();
    this.pitch.clear();
    this.answered = false;
    const m = this.moments[this.i];
    this.progress.setText(`Moment ${this.i + 1} of ${this.moments.length} · ${this.score} pts`);

    // How the move got here, then everyone the camera saw at the moment of the decision.
    const players: Mark[] = m.frame.filter(([x]) => x >= HALF_X).map(([x, y, kind]) => ({
      kind: "player", at: [x, y], side: kind === TEAMMATE || kind === ACTOR ? "home" : kind === KEEPER ? "keeper" : "away",
    }));
    this.diagram.draw([
      ...this.path(m.before, () => "trail"),
      ...players,
      { kind: "ring", at: [m.x, m.y] },
      { kind: "ball", at: [Math.min(m.x + 0.8, 120), m.y] },
    ]);
    sfx.select();

    const match = G.data.meta.matches[String(m.match)];
    if (match) {
      this.side.add(this.add.text(TEXT_X, 136, `${match.tournament.toUpperCase()} · ${match.stage.toUpperCase()}`, title(13, C.muted)).setOrigin(0, 0.5));
      this.side.add(this.add.text(TEXT_X, 162, `${match.home} vs ${match.away} · ${m.minute}'`, body(16, C.text, "800")).setOrigin(0, 0.5));
    }
    const lead = this.add.text(TEXT_X, 196, `${m.player} (${m.team}) has the ball in the ring. Blue dots are teammates, red are opponents, yellow is the keeper.`,
      { ...body(16, C.text, "400"), wordWrap: { width: TEXT_W }, lineSpacing: 6 });
    this.side.add(lead);
    this.side.add(this.add.text(TEXT_X, lead.y + lead.height + 28, "What happens next?", title(20, C.accent)).setOrigin(0, 0.5));
    CALLS.forEach((label, n) => {
      this.buttons.push(new Button(this, PANEL_X + 24 + 108 + (n % 2) * 226, 452 + Math.floor(n / 2) * 76, {
        w: 214, h: 64, label, key: String(n + 1), icon: CALL_ICONS[n], size: 17,
      }, () => this.answer(n)));
    });
  }

  private answer(n: number): void {
    if (this.answered || n >= CALLS.length) return;
    this.answered = true;
    const m = this.moments[this.i];
    const { verdict, points } = judgeNext(m, n);
    this.score += points;
    if (verdict === "exact") sfx.exact();
    else if (verdict === "common") sfx.select();
    else sfx.miss();
    this.progress.setText(`Moment ${this.i + 1} of ${this.moments.length} · ${this.score} pts`);

    // Play out what really happened: the decision first, then the rest of the move.
    this.diagram.draw(this.path(m.after, (k) => (k > 0 ? "pass" : m.call === 0 ? "shot" : m.call === 3 ? "run" : "pass")));
    if (m.outcome === "goal") this.time.delayedCall(700, () => this.pitch.rippleNet());

    this.clearSide();
    const color = verdict === "exact" ? C.exact : verdict === "common" ? C.near : C.miss;
    const head = verdict === "exact" ? "SPOT ON" : verdict === "common" ? "GOOD INSTINCT" : "NOT THIS TIME";
    this.side.add(icon(this, TEXT_X + 16, 136, verdict === "miss" ? "cross" : "check", 30, color));
    this.side.add(this.add.text(TEXT_X + 42, 136, head, title(22, color)).setOrigin(0, 0.5));
    this.side.add(this.add.text(PANEL_X + PANEL_W - 24, 136, `+${points}`, title(22, color)).setOrigin(1, 0.5));

    const ending = m.outcome === "goal" ? "The move ended in a goal." : m.outcome === "shot" ? "The move ended in a shot."
      : "The move didn't end in a shot.";
    let text = `${m.player} ${DID[m.call]}. ${ending}`;
    if (verdict === "common") text += `\n\nYou called what most players do from there, so half points.`;
    const said = this.add.text(TEXT_X, 170, text, { ...body(16, C.text, "400"), wordWrap: { width: TEXT_W }, lineSpacing: 6 });
    this.side.add(said);

    // How often real players make each call from this part of the pitch.
    let y = said.y + said.height + 32;
    this.side.add(this.add.text(TEXT_X, y, "FROM THIS SPOT, REAL PLAYERS…", title(13, C.muted)).setOrigin(0, 0.5));
    const common = commonCall(m.rates);
    const before = this.children.list.length;
    CALLS.forEach((label, k) => {
      y += 34;
      const hl = k === m.call;
      this.side.add(icon(this, TEXT_X + 10, y, CALL_ICONS[k], 20, hl ? C.gold : C.muted));
      this.side.add(this.add.text(TEXT_X + 30, y, label, body(15, hl ? C.gold : C.text, hl ? "800" : "600")).setOrigin(0, 0.5));
      const fill = bar(this, TEXT_X + 120, y - 5, 250, 10, hl ? C.gold : k === common ? C.accent : 0x64748b);
      fill(m.rates[k]);
      this.side.add(this.add.text(TEXT_X + TEXT_W, y, `${Math.round(100 * m.rates[k])}%`, body(14, C.muted, "800")).setOrigin(1, 0.5));
    });
    // The bars are drawn straight onto the scene; move them into the panel so the next moment clears them.
    this.side.add(this.children.list.slice(before).filter((o) => o !== this.side));

    const last = this.i === this.moments.length - 1;
    this.buttons.push(new Button(this, PANEL_X + PANEL_W / 2, 662, {
      w: PANEL_W - 40, h: 52, label: last ? "See your score" : "Next moment", icon: "next", size: 18, display: true, color: C.accent,
    }, () => this.advance()));
  }

  private advance(): void {
    this.i += 1;
    if (this.i < this.moments.length) this.show();
    else this.finish();
  }

  private finish(): void {
    this.clearSide();
    this.pitch.clear();
    const s = G.save;
    const levelBefore = currentLevel();
    const best = this.score > s.nextBest;
    s.nextBest = Math.max(s.nextBest, this.score);
    const xp = Math.round(this.score / 8);
    const coins = Math.round(this.score / 20);
    s.xp += xp;
    s.coins += coins;
    settle(this, levelBefore);

    const max = this.moments.length * NEXT_EXACT;
    this.progress.setText("");
    this.side.add(this.add.text(PANEL_X + PANEL_W / 2, 170, `${this.score}`, title(64, C.gold)).setOrigin(0.5));
    this.side.add(this.add.text(PANEL_X + PANEL_W / 2, 226, `OUT OF ${max}${best ? " · NEW BEST" : ""}`, title(16, C.accent)).setOrigin(0.5));
    this.side.add(inline(this, PANEL_X + PANEL_W / 2, 264, [`+${xp} XP  +${coins} `, { icon: "coin" }], 15, C.gold, 0.5, "800"));
    if (this.score >= max * 0.75) confetti(this, PANEL_X + PANEL_W / 2, 200, [C.gold, C.accent, 0xffffff], 80);
    this.side.add(this.add.text(TEXT_X, 320,
      "Every moment was real, from a match at Euro 2020, the 2022 World Cup or Euro 2024. " +
      "Players don't always make the common call, and that's often where the goals come from.",
      { ...body(15, C.muted, "400"), wordWrap: { width: TEXT_W }, lineSpacing: 6 }));
    this.buttons.push(new Button(this, PANEL_X + 104, 662, { w: 160, h: 52, label: "Back", icon: "back", size: 16 },
      () => goTo(this, "ReadMatch")));
    this.buttons.push(new Button(this, PANEL_X + PANEL_W - 159, 662, {
      w: 270, h: 52, label: "Play again", icon: "retry", size: 18, display: true, color: C.accent,
    }, () => this.scene.restart()));
  }
}
