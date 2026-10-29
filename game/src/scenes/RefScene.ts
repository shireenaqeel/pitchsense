import Phaser from "phaser";

import { lessonById } from "../academy/curriculum";
import { Diagram } from "../academy/Diagram";
import { pickCalls, type RefCall } from "../academy/referee";
import { sfx } from "../audio/sfx";
import { PitchView } from "../pitch/PitchView";
import { G } from "../state";
import { ballSkin, pitchTheme } from "../systems/cosmetics";
import { confetti, currentLevel, settle } from "../ui/common";
import { icon, inline } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, Button, goTo, panel } from "../ui/widgets";
import { VIEWS } from "./LessonScene";

export const REF_ROUND = 8;
const XP_PER_CALL = 15;
const COINS_PER_CALL = 5;

const PANEL_X = 760;
const PANEL_W = 490;
const TEXT_X = PANEL_X + 24;
const TEXT_W = PANEL_W - 48;
const KEYS = ["ONE", "TWO", "THREE"];

/** Referee's Eye: a round of drawn situations, each one the referee's call. */
export class RefScene extends Phaser.Scene {
  private calls: RefCall[] = [];
  private i = 0;
  private right = 0;
  private missed: string[] = [];
  private answered = false;
  private pitch?: PitchView;
  private side!: Phaser.GameObjects.Container;
  private buttons: Button[] = [];
  private progress!: Phaser.GameObjects.Text;

  constructor() {
    super("Referee");
  }

  init(): void {
    this.calls = pickCalls(Math.random, REF_ROUND);
    this.i = 0;
    this.right = 0;
    this.missed = [];
    this.buttons = [];
    this.pitch = undefined;
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this, "ReadMatch");
    this.add.text(190, 30, "READ THE MATCH · DRAWN SCENARIOS", body(12, C.muted, "800")).setOrigin(0, 0.5);
    this.add.text(190, 60, "REFEREE'S EYE", title(26, C.gold)).setOrigin(0, 0.5);
    this.progress = this.add.text(PANEL_X + PANEL_W, 60, "", body(15, C.text, "800")).setOrigin(1, 0.5);
    panel(this, PANEL_X, 104, PANEL_W, 600);
    this.side = this.add.container(0, 0);
    KEYS.forEach((k, n) => this.input.keyboard?.on(`keydown-${k}`, () => this.answer(n)));
    this.input.keyboard?.on("keydown-ENTER", () => this.answered && this.advance());
    this.show();
  }

  private clearSide(): void {
    this.side.removeAll(true);
    this.buttons.forEach((b) => b.destroy());
    this.buttons = [];
  }

  private show(): void {
    this.clearSide();
    this.answered = false;
    const call = this.calls[this.i];
    this.progress.setText(`Call ${this.i + 1} of ${this.calls.length} · ${this.right} right`);

    // Each situation picks its own view, so the pitch is rebuilt every time.
    this.pitch?.destroy();
    const [ox, oy, s, view] = VIEWS[call.view];
    const theme = pitchTheme(G.save);
    this.pitch = new PitchView(this, ox, oy, s, theme, ballSkin(G.save), view);
    new Diagram(this, this.pitch, theme).draw(call.marks);
    sfx.select();

    this.side.add(this.add.text(TEXT_X, 136, "THE SITUATION", title(13, C.muted)).setOrigin(0, 0.5));
    const sit = this.add.text(TEXT_X, 156, call.situation, { ...body(17, C.text, "400"), wordWrap: { width: TEXT_W }, lineSpacing: 6 });
    const q = this.add.text(TEXT_X, 156 + sit.height + 22, call.q, title(20, C.accent));
    this.side.add([sit, q]);
    const top = Math.max(360, q.y + q.height + 52);
    call.options.forEach((o, n) => {
      this.buttons.push(new Button(this, PANEL_X + PANEL_W / 2, top + n * 70, {
        w: PANEL_W - 40, h: 60, label: o, key: String(n + 1), align: "left", size: 15, wrap: PANEL_W - 120,
      }, () => this.answer(n)));
    });
  }

  private answer(n: number): void {
    const call = this.calls[this.i];
    if (this.answered || n >= call.options.length) return;
    this.answered = true;
    const ok = n === call.answer;
    if (ok) {
      this.right += 1;
      sfx.exact();
    } else {
      sfx.miss();
      this.cameras.main.shake(120, 0.003);
      if (!this.missed.includes(call.lesson)) this.missed.push(call.lesson);
    }
    this.progress.setText(`Call ${this.i + 1} of ${this.calls.length} · ${this.right} right`);
    // Clicks are already ignored once answered, so the buttons keep their full colour.
    this.buttons.forEach((b, k) => {
      if (k === call.answer) b.setColor(C.exact);
      else if (k === n) b.setColor(0x5b1d1d);
    });

    // The verdict replaces the question; the chosen and right answers stay visible.
    this.side.removeAll(true);
    this.buttons.forEach((b, k) => b.setVisible(k === call.answer || k === n).setY(k === call.answer ? 196 : 266));
    const y = ok ? 250 : 320;
    this.side.add(icon(this, TEXT_X + 16, 136, ok ? "check" : "cross", 30, ok ? C.exact : C.miss));
    this.side.add(this.add.text(TEXT_X + 42, 136, ok ? "RIGHT CALL" : "NOT QUITE", title(22, ok ? C.exact : C.miss)).setOrigin(0, 0.5));
    const why = this.add.text(TEXT_X, y, call.why, { ...body(16, C.text, "400"), wordWrap: { width: TEXT_W }, lineSpacing: 6 });
    this.side.add(why);
    const lesson = lessonById(call.lesson);
    if (lesson) {
      this.side.add(inline(this, TEXT_X, why.y + why.height + 26, [{ icon: "book", color: C.gold }, ` The Academy: ${lesson.title}`],
        14, C.muted));
    }
    const last = this.i === this.calls.length - 1;
    this.buttons.push(new Button(this, PANEL_X + PANEL_W / 2, 662, {
      w: PANEL_W - 40, h: 52, label: last ? "See your score" : "Next call", icon: "next", size: 18, display: true, color: C.accent,
    }, () => this.advance()));
  }

  private advance(): void {
    if (this.i < this.calls.length - 1) {
      this.i += 1;
      this.show();
    } else {
      this.finish();
    }
  }

  private finish(): void {
    this.clearSide();
    this.answered = false;
    this.pitch?.clear();
    const s = G.save;
    const levelBefore = currentLevel();
    const best = this.right > s.refBest;
    s.refBest = Math.max(s.refBest, this.right);
    const xp = this.right * XP_PER_CALL;
    const coins = this.right * COINS_PER_CALL;
    s.xp += xp;
    s.coins += coins;
    settle(this, levelBefore);

    this.progress.setText("");
    this.side.add(this.add.text(PANEL_X + PANEL_W / 2, 170, `${this.right} / ${this.calls.length}`, title(64, C.gold)).setOrigin(0.5));
    this.side.add(this.add.text(PANEL_X + PANEL_W / 2, 226, best ? "RIGHT CALLS · NEW BEST" : "RIGHT CALLS", title(16, C.accent)).setOrigin(0.5));
    this.side.add(inline(this, PANEL_X + PANEL_W / 2, 264, [`+${xp} XP  +${coins} `, { icon: "coin" }], 15, C.gold, 0.5, "800"));
    if (this.right === this.calls.length) confetti(this, PANEL_X + PANEL_W / 2, 200, [C.gold, C.accent, 0xffffff], 80);

    if (this.missed.length) {
      this.side.add(this.add.text(TEXT_X, 318, "BRUSH UP ON", title(13, C.muted)).setOrigin(0, 0.5));
      this.missed.slice(0, 3).forEach((id, k) => {
        const l = lessonById(id)!;
        this.buttons.push(new Button(this, PANEL_X + PANEL_W / 2, 364 + k * 62, {
          w: PANEL_W - 40, h: 52, label: l.title, icon: "book", iconColor: C.gold, align: "left", size: 15,
        }, () => goTo(this, "Lesson", { id })));
      });
    } else {
      this.side.add(this.add.text(PANEL_X + PANEL_W / 2, 360, "A perfect round. The fourth official\nwould like a word about your future.",
        { ...body(16, C.text, "400"), align: "center" }).setOrigin(0.5));
    }
    this.buttons.push(new Button(this, PANEL_X + 104, 662, { w: 160, h: 52, label: "Back", icon: "back", size: 16 },
      () => goTo(this, "ReadMatch")));
    this.buttons.push(new Button(this, PANEL_X + PANEL_W - 159, 662, {
      w: 270, h: 52, label: "Play again", icon: "retry", size: 18, display: true, color: C.accent,
    }, () => this.scene.restart()));
  }
}
