import Phaser from "phaser";

import { CURRICULUM, LESSONS } from "../academy/curriculum";
import { G } from "../state";
import { lessonDone, lessonsDone, moduleProgress, nextLesson } from "../systems/academy";
import { icon } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, bar, Button, goTo, panel } from "../ui/widgets";

const COL_W = 286;
const GAP = 12;
const PER_PAGE = 4;

/** The course in two parts, four modules to a page. */
const PAGES = ["Watch a match", "Read the game"];

/** The course-map page that shows a lesson. */
export function academyPage(lessonId: string): number {
  return Math.max(0, Math.floor(CURRICULUM.findIndex((m) => m.lessons.some((l) => l.id === lessonId)) / PER_PAGE));
}

/** The Academy course map: each module a column of lessons, over two pages. */
export class AcademyScene extends Phaser.Scene {
  private page = 0;
  private columns!: Phaser.GameObjects.Container;
  private tabs: Button[] = [];

  constructor() {
    super("Academy");
  }

  init(data: { page?: number }): void {
    const next = nextLesson(G.save);
    this.page = data.page ?? (next ? academyPage(next.id) : 0);
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this);
    this.add.text(W / 2, 40, "ACADEMY", title(34, C.gold)).setOrigin(0.5);

    const s = G.save;
    const done = lessonsDone(s);
    const next = nextLesson(s);
    if (next) {
      const go = () => goTo(this, "Lesson", { id: next.id });
      new Button(this, W - 150, 44, { w: 220, h: 48, label: done ? "Continue" : "Start here", icon: "play", size: 17,
        color: C.accent, display: true }, go);
      this.input.keyboard?.on("keydown-ENTER", go);
    } else {
      this.add.text(W - 40, 44, "Course complete", title(16, C.gold)).setOrigin(1, 0.5);
    }

    this.tabs = PAGES.map((label, i) => new Button(this, W / 2 + (i - 0.5) * 230, 80, {
      w: 220, h: 38, label: `${i + 1}. ${label}`, size: 14,
    }, () => this.showPage(i)));
    this.input.keyboard?.on("keydown-LEFT", () => this.showPage(0));
    this.input.keyboard?.on("keydown-RIGHT", () => this.showPage(1));
    this.columns = this.add.container(0, 0);
    this.showPage(this.page);

    this.add.text(W / 2, 701, `${done} of ${LESSONS.length} lessons done · each one pays XP and coins the first time`,
      body(12, C.muted)).setOrigin(0.5);
  }

  private showPage(page: number): void {
    this.page = page;
    this.tabs.forEach((t, i) => t.setSelected(i === page));
    this.columns.removeAll(true);
    const s = G.save;
    const next = nextLesson(s);
    const first = page * PER_PAGE;
    const modules = CURRICULUM.slice(first, first + PER_PAGE);
    // A short page is centred.
    const left = 40 + ((PER_PAGE - modules.length) * (COL_W + GAP)) / 2;
    const before = this.children.list.length;
    modules.forEach((m, i) => {
      const x = left + i * (COL_W + GAP);
      const y = 108;
      panel(this, x, y, COL_W, 570);
      const prog = moduleProgress(s, m.id);
      const finished = prog.done === prog.total;
      icon(this, x + 34, y + 36, m.icon, 34, finished ? C.gold : C.accent);
      this.add.text(x + 62, y + 26, `MODULE ${first + i + 1}`, body(11, C.muted, "800")).setOrigin(0, 0.5);
      this.add.text(x + 62, y + 46, m.title.toUpperCase(), title(17, finished ? C.gold : C.text)).setOrigin(0, 0.5);
      this.add.text(x + 20, y + 74, m.blurb, { ...body(13, C.muted, "400"), wordWrap: { width: COL_W - 40 } }).setOrigin(0, 0);
      bar(this, x + 20, y + 118, COL_W - 90, 8, finished ? C.gold : C.accent)(prog.done / prog.total);
      this.add.text(x + COL_W - 20, y + 122, `${prog.done}/${prog.total}`, body(12, C.muted, "800")).setOrigin(1, 0.5);

      m.lessons.forEach((l, j) => {
        const isDone = lessonDone(s, l.id);
        const isNext = next?.id === l.id;
        const b = new Button(this, x + COL_W / 2, y + 176 + j * 68, {
          w: COL_W - 30, h: 58, label: l.title, size: 14, align: "left", wrap: COL_W - 100,
          icon: isDone ? "check" : isNext ? "play" : "book",
          iconColor: isDone ? C.accent : isNext ? C.gold : C.muted,
        }, () => goTo(this, "Lesson", { id: l.id }));
        if (isNext) b.setSelected(true);
      });
    });

    // Everything drawn above moves into the page container, so a page switch clears it.
    this.columns.add(this.children.list.slice(before).filter((o) => o !== this.columns));
  }
}
