import Phaser from "phaser";

import { type Lesson, LESSONS, lessonById, type Mark, moduleOf, type View } from "../academy/curriculum";
import { Diagram } from "../academy/Diagram";
import { sfx } from "../audio/sfx";
import { HALF, PitchView, type Viewport } from "../pitch/PitchView";
import { G } from "../state";
import { completeLesson, LESSON_COINS, LESSON_XP } from "../systems/academy";
import { ballSkin, pitchTheme } from "../systems/cosmetics";
import { confetti, currentLevel, settle } from "../ui/common";
import { icon, inline } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, Button, floatText, goTo, panel } from "../ui/widgets";
import { academyPage } from "./AcademyScene";

const PANEL_X = 760;
const PANEL_W = 490;
const TEXT_X = PANEL_X + 24;
const TEXT_W = PANEL_W - 48;

/** Where each kind of diagram sits on screen: [ox, oy, scale, viewport]. */
const VIEWS: Record<View, [number, number, number, Viewport]> = {
  full: [40 + (680 - 80 * 4.4) / 2, 140, 4.4, { xMin: 0, yMin: 0, yMax: 80 }],
  half: [40, 158, 8.5, HALF],
  box: [40, 190, 680 / 60, { xMin: 84, yMin: 10, yMax: 70 }],
};

/** One Academy lesson: step through the picture, then answer a question. */
export class LessonScene extends Phaser.Scene {
  private lesson!: Lesson;
  private step = 0;
  private diagram!: Diagram;
  private side!: Phaser.GameObjects.Container;
  private buttons: Button[] = [];
  private dots!: Phaser.GameObjects.Graphics;

  constructor() {
    super("Lesson");
  }

  init(data: { id: string }): void {
    this.lesson = lessonById(data.id) ?? LESSONS[0];
    this.step = 0;
    this.buttons = [];
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this, "Academy", { page: academyPage(this.lesson.id) });
    const mod = moduleOf(this.lesson.id)!;
    const n = LESSONS.indexOf(this.lesson) + 1;
    this.add.text(190, 30, `${mod.title.toUpperCase()} · LESSON ${n} OF ${LESSONS.length}`, body(12, C.muted, "800")).setOrigin(0, 0.5);
    this.add.text(190, 60, this.lesson.title, title(26, C.gold)).setOrigin(0, 0.5);

    const [ox, oy, s, view] = VIEWS[this.lesson.view];
    const theme = pitchTheme(G.save);
    const pitch = new PitchView(this, ox, oy, s, theme, ballSkin(G.save), view);
    this.diagram = new Diagram(this, pitch, theme);

    panel(this, PANEL_X, 104, PANEL_W, 600);
    this.dots = this.add.graphics();
    this.side = this.add.container(0, 0);

    this.input.keyboard?.on("keydown-RIGHT", () => this.forward());
    this.input.keyboard?.on("keydown-SPACE", () => this.forward());
    this.input.keyboard?.on("keydown-LEFT", () => this.backward());
    this.showStep(true);
  }

  // --------------------------------------------------------------- steps --
  private clearSide(): void {
    this.side.removeAll(true);
    this.buttons.forEach((b) => b.destroy());
    this.buttons = [];
  }

  /** Marks on screen at step i: everything since the last step that cleared. */
  private marksUpTo(i: number): Mark[] {
    let marks: Mark[] = [];
    for (const st of this.lesson.steps.slice(0, i + 1)) {
      if (st.clear) marks = [];
      marks = marks.concat(st.marks ?? []);
    }
    return marks;
  }

  private drawDots(active: number): void {
    const total = this.lesson.steps.length + 1; // the quiz is the last dot
    const g = this.dots.clear();
    for (let i = 0; i < total; i++) {
      const x = TEXT_X + 6 + i * 22;
      g.fillStyle(i === active ? C.gold : i < active ? C.accent : 0x334155, 1).fillCircle(x, 134, i === active ? 6 : 5);
    }
  }

  private showStep(fresh: boolean): void {
    this.clearSide();
    const steps = this.lesson.steps;
    const st = steps[this.step];
    if (fresh) {
      // Moving forward adds this step's marks; anything else redraws the picture.
      if (st.clear || this.step === 0) this.diagram.clear();
      this.diagram.draw(st.marks ?? []);
      if ((st.marks ?? []).length) sfx.select();
    } else {
      this.diagram.clear();
      this.diagram.draw(this.marksUpTo(this.step), false);
    }
    this.drawDots(this.step);
    this.side.add(this.add.text(PANEL_X + PANEL_W - 24, 134, `${this.step + 1} / ${steps.length}`, body(12, C.muted, "800")).setOrigin(1, 0.5));

    const text = this.add.text(TEXT_X, 166, st.text, { ...body(17, C.text, "400"), wordWrap: { width: TEXT_W }, lineSpacing: 7 });
    text.setAlpha(0);
    this.tweens.add({ targets: text, alpha: 1, duration: 250 });
    this.side.add(text);
    this.links(480);

    if (this.step > 0) {
      this.buttons.push(new Button(this, PANEL_X + 94, 662, { w: 140, h: 52, label: "Back", icon: "back", size: 16 }, () => this.backward()));
    }
    const last = this.step === steps.length - 1;
    this.buttons.push(new Button(this, PANEL_X + PANEL_W - 164, 662, {
      w: 280, h: 52, label: last ? "Check yourself" : "Next", icon: last ? "help" : "next", size: 18, display: true, color: C.accent,
    }, () => this.forward()));
  }

  /** "Read more" links, from `y` down. They open in a new tab. */
  private links(y: number): void {
    const links = this.lesson.links.slice(0, 4);
    if (!links.length) return;
    this.side.add(this.add.text(TEXT_X, y, "READ MORE", title(12, C.muted)).setOrigin(0, 0.5));
    links.forEach((l, i) => {
      const ry = y + 26 + i * 24;
      const row = inline(this, TEXT_X, ry, [{ icon: "link", color: 0x60a5fa }, l.label], 14, 0x93c5fd);
      const hit = this.add.zone(TEXT_X + row.width / 2, ry, row.width, 22).setInteractive({ useHandCursor: true });
      hit.on("pointerover", () => row.setAlpha(0.7));
      hit.on("pointerout", () => row.setAlpha(1));
      hit.on("pointerdown", () => window.open(l.url, "_blank", "noopener"));
      this.side.add([row, hit]);
    });
  }

  private forward(): void {
    if (this.step < 0) return; // on the quiz
    if (this.step < this.lesson.steps.length - 1) {
      this.step += 1;
      this.showStep(true);
    } else {
      this.quiz();
    }
  }

  private backward(): void {
    if (this.step <= 0) return;
    this.step -= 1;
    this.showStep(false);
  }

  // ---------------------------------------------------------------- quiz --
  private quiz(): void {
    this.step = -1;
    this.clearSide();
    this.drawDots(this.lesson.steps.length);
    const q = this.lesson.quiz;
    this.side.add(this.add.text(TEXT_X, 166, "CHECK YOURSELF", title(16, C.accent)).setOrigin(0, 0.5));
    const qt = this.add.text(TEXT_X, 190, q.q, { ...body(18, C.text, "800"), wordWrap: { width: TEXT_W }, lineSpacing: 5 });
    this.side.add(qt);
    const top = Math.max(300, 190 + qt.height + 50);
    const keys = ["ONE", "TWO", "THREE", "FOUR"];
    const options = q.options.map((o, i) => {
      const b = new Button(this, PANEL_X + PANEL_W / 2, top + i * 72, {
        w: PANEL_W - 40, h: 62, label: o, key: String(i + 1), align: "left", size: 15, wrap: PANEL_W - 120,
      }, () => answer(i));
      this.buttons.push(b);
      return b;
    });
    const tried = new Set<number>();
    const answer = (i: number) => {
      if (tried.has(i) || tried.has(q.answer)) return;
      tried.add(i);
      if (i === q.answer) {
        options[i].setColor(C.exact).setSelected(true);
        options.forEach((b, j) => j !== i && b.setEnabled(false));
        this.time.delayedCall(350, () => this.passed());
      } else {
        sfx.miss();
        options[i].setColor(0x5b1d1d).setEnabled(false);
        this.cameras.main.shake(120, 0.003);
        const hint = this.add.text(TEXT_X, top + q.options.length * 72 - 10, "Not quite. Have another look at the picture and try again.",
          { ...body(14, C.near, "400"), wordWrap: { width: TEXT_W } });
        this.side.add(hint);
        this.tweens.add({ targets: hint, alpha: { from: 0, to: 1 }, duration: 200 });
      }
    };
    keys.slice(0, q.options.length).forEach((k, i) => this.input.keyboard?.on(`keydown-${k}`, () => this.step === -1 && answer(i)));
  }

  private passed(): void {
    sfx.exact();
    const levelBefore = currentLevel();
    const first = completeLesson(G.save, this.lesson.id);
    settle(this, levelBefore);
    this.clearSide();
    this.step = -2;
    const q = this.lesson.quiz;

    this.side.add(icon(this, TEXT_X + 18, 168, "check", 34, C.exact));
    this.side.add(this.add.text(TEXT_X + 48, 168, "SPOT ON", title(26, C.exact)).setOrigin(0, 0.5));
    if (first) {
      const reward = inline(this, PANEL_X + PANEL_W - 24, 168, [`+${LESSON_XP} XP  +${LESSON_COINS} `, { icon: "coin" }], 15, C.gold, 1, "800");
      this.side.add(reward);
      confetti(this, PANEL_X + PANEL_W / 2, 200, [C.gold, C.accent, 0xffffff], 60);
      sfx.coin();
      floatText(this, PANEL_X + PANEL_W / 2, 240, "LESSON COMPLETE", C.gold, 24);
    }
    const why = this.add.text(TEXT_X, 204, q.why, { ...body(16, C.text, "400"), wordWrap: { width: TEXT_W }, lineSpacing: 6 });
    this.side.add(why);

    // The one sentence to keep.
    const ty = 204 + why.height + 28;
    const box = this.add.graphics();
    box.fillStyle(C.panelHi, 1).fillRoundedRect(TEXT_X - 8, ty, TEXT_W + 16, 10, 12);
    this.side.add(box);
    this.side.add(icon(this, TEXT_X + 14, ty + 26, "bulb", 22, C.gold));
    this.side.add(this.add.text(TEXT_X + 34, ty + 26, "REMEMBER", title(12, C.gold)).setOrigin(0, 0.5));
    const take = this.add.text(TEXT_X + 8, ty + 46, this.lesson.takeaway, { ...body(16, C.text, "800"), wordWrap: { width: TEXT_W - 16 }, lineSpacing: 4 });
    this.side.add(take);
    box.clear().fillStyle(C.panelHi, 1).fillRoundedRect(TEXT_X - 8, ty, TEXT_W + 16, take.height + 62, 12);
    this.links(Math.max(ty + take.height + 90, 480));

    const i = LESSONS.indexOf(this.lesson);
    const next = LESSONS[i + 1];
    this.buttons.push(new Button(this, PANEL_X + 104, 662, { w: 160, h: 52, label: "Academy", icon: "book", size: 16 },
      () => goTo(this, "Academy", { page: academyPage(this.lesson.id) })));
    const go = next ? () => goTo(this, "Lesson", { id: next.id }) : () => goTo(this, "Career");
    this.buttons.push(new Button(this, PANEL_X + PANEL_W - 159, 662, {
      w: 270, h: 52, label: next ? "Next lesson" : "Play World Tour", icon: next ? "next" : "trophy", size: 18, display: true, color: C.accent,
    }, go));
    this.input.keyboard?.once("keydown-ENTER", go);
  }
}
