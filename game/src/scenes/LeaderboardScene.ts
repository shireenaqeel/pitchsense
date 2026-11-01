import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { G } from "../state";
import {
  type BoardMode, type BoardRow, cleanName, CONFIG, fetchBoard, MAX_NAME, type PendingScore, postScore,
} from "../systems/leaderboard";
import { dailyNumber, dateKey } from "../systems/rng";
import { writeSave, browserStore } from "../systems/save";
import { icon } from "../ui/icons";
import { body, BODY, C, crisp, H, hex, title, W } from "../ui/theme";
import { backButton, Button, panel } from "../ui/widgets";

const ROW_H = 44;
const LIST_W = 640;
const SIDE_W = 380;

// Runs posted this session, so coming back to the board can't post one twice.
const posted = new Set<string>();
const postKey = (p: PendingScore) => `${p.mode}:${p.day}:${p.score}:${p.reads}`;

interface LeaderboardData {
  board?: BoardMode;
  post?: PendingScore | null;
}

/** The shared boards: today's Daily Challenge and Rapid Fire of all time. */
export class LeaderboardScene extends Phaser.Scene {
  private board: BoardMode = "daily";
  private post: PendingScore | null = null;
  private list!: Phaser.GameObjects.Container;
  private tabs: Record<BoardMode, Button> = {} as Record<BoardMode, Button>;
  private listX = 0;
  private request = 0;
  private you: { name: string; score: number } | null = null;

  constructor() {
    super("Leaderboard");
  }

  init(d: LeaderboardData): void {
    this.post = d.post && !posted.has(postKey(d.post)) ? d.post : null;
    this.board = d.post?.mode ?? d.board ?? "daily";
    this.you = null;
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this);
    this.add.text(W / 2, 44, "LEADERBOARD", title(34, C.gold)).setOrigin(0.5);

    const today = dateKey(new Date());
    this.tabs.daily = new Button(this, W / 2 - 170, 104, { w: 320, h: 48, label: `Daily #${dailyNumber(today)} · today`,
      icon: "calendar", size: 16 }, () => this.show("daily"));
    this.tabs.rapid = new Button(this, W / 2 + 170, 104, { w: 320, h: 48, label: "Rapid Fire · all time",
      icon: "stopwatch", size: 16 }, () => this.show("rapid"));

    const withPost = this.post !== null && CONFIG !== null;
    this.listX = withPost ? W / 2 - (LIST_W + SIDE_W + 40) / 2 : W / 2 - LIST_W / 2;
    panel(this, this.listX, 148, LIST_W, 540);
    this.list = this.add.container(0, 0);
    if (withPost) this.postPanel(this.listX + LIST_W + 40, 148, this.post!);
    this.show(this.board);
  }

  private show(mode: BoardMode): void {
    this.board = mode;
    this.tabs.daily.setSelected(mode === "daily");
    this.tabs.rapid.setSelected(mode === "rapid");
    this.list.removeAll(true);
    if (!CONFIG) {
      this.note("The leaderboards are offline in this version of the game.");
      return;
    }
    this.note("Loading…");
    const id = ++this.request;
    const day = mode === "daily" ? dateKey(new Date()) : null;
    fetchBoard(CONFIG, mode, day).then(
      (rows) => id === this.request && this.scene.isActive() && this.rows(rows),
      () => id === this.request && this.scene.isActive() && this.note("The leaderboard can't be reached right now. Try again shortly."),
    );
  }

  private note(text: string): void {
    this.list.removeAll(true);
    this.list.add(this.add.text(this.listX + LIST_W / 2, 418, text, {
      ...body(16, C.muted, "400"), align: "center", wordWrap: { width: LIST_W - 80 },
    }).setOrigin(0.5));
  }

  private rows(rows: BoardRow[]): void {
    this.list.removeAll(true);
    if (!rows.length) {
      this.note(this.board === "daily" ? "No scores yet today. Play the Daily Challenge and be the first."
        : "No Rapid Fire scores yet. Set one and be the first.");
      return;
    }
    const x = this.listX;
    this.list.add(this.add.text(x + 32, 178, "#", body(13, C.muted, "800")).setOrigin(0, 0.5));
    this.list.add(this.add.text(x + 84, 178, "PLAYER", body(13, C.muted, "800")).setOrigin(0, 0.5));
    this.list.add(this.add.text(x + LIST_W - 32, 178, this.board === "rapid" ? "SCORE · READS" : "SCORE",
      body(13, C.muted, "800")).setOrigin(1, 0.5));
    let marked = false;
    rows.forEach((r, i) => {
      const y = 222 + i * ROW_H;
      const mine = !marked && this.you !== null && r.name === this.you.name && r.score === this.you.score;
      if (mine) {
        marked = true;
        const hl = this.add.graphics().fillStyle(C.selected, 0.9).fillRoundedRect(x + 16, y - ROW_H / 2 + 3, LIST_W - 32, ROW_H - 6, 10);
        this.list.add(hl);
      }
      const color = i === 0 ? C.gold : C.text;
      if (i < 3) this.list.add(icon(this, x + 40, y, "medal", 22, [C.gold, 0xcbd5e1, 0xd97706][i]));
      else this.list.add(this.add.text(x + 40, y, String(i + 1), body(16, C.muted, "800")).setOrigin(0.5));
      this.list.add(this.add.text(x + 84, y, r.name, body(17, color, mine ? "800" : "600")).setOrigin(0, 0.5));
      const right = this.board === "rapid" ? `${r.score.toLocaleString()} · ${r.reads}` : r.score.toLocaleString();
      this.list.add(this.add.text(x + LIST_W - 32, y, right, title(18, color)).setOrigin(1, 0.5));
    });
  }

  /** The player's score and a name field to post it with. */
  private postPanel(x: number, y: number, p: PendingScore): void {
    panel(this, x, y, SIDE_W, 540);
    const cx = x + SIDE_W / 2;
    this.add.text(cx, y + 40, p.mode === "daily" ? "YOUR DAILY SCORE" : "YOUR NEW BEST", body(13, C.muted, "800")).setOrigin(0.5);
    this.add.text(cx, y + 92, p.score.toLocaleString(), title(48, C.gold)).setOrigin(0.5);
    const label = this.add.text(x + 30, y + 168, "Name on the board", body(14, C.muted, "800")).setOrigin(0, 0.5);

    const field = this.nameField(x + 30, y + 188, SIDE_W - 60, 52);
    const status = this.add.text(cx, y + 330, "", { ...body(15, C.muted, "400"), align: "center", wordWrap: { width: SIDE_W - 60 } })
      .setOrigin(0.5, 0);
    const send = new Button(this, cx, y + 288, { w: SIDE_W - 60, h: 56, label: "Post score", icon: "trophy", size: 18,
      display: true, color: C.accent }, () => void submit());

    let busy = false;
    const submit = async () => {
      if (busy || !CONFIG) return;
      busy = true;
      send.setEnabled(false);
      status.setColor(hex(C.muted)).setText("Posting…");
      const name = cleanName(field.value);
      try {
        await postScore(CONFIG, name, p);
      } catch {
        busy = false;
        send.setEnabled(true);
        status.setColor(hex(C.miss)).setText("That didn't go through. The board may be busy, so try again in a minute.");
        return;
      }
      if (!this.scene.isActive()) return;
      posted.add(postKey(p));
      G.save.playerName = name === "Anonymous" ? "" : name;
      writeSave(browserStore(), G.save);
      sfx.levelUp();
      field.remove();
      label.setVisible(false);
      send.setVisible(false);
      status.setY(y + 168).setColor(hex(C.exact)).setText(`Posted as ${name}.`);
      this.you = { name, score: p.score };
      this.show(p.mode);
    };
    field.addEventListener("keydown", (e) => {
      if (e.key === "Enter") void submit();
    });
  }

  /** An HTML text input laid over the canvas, so phones get their keyboard. */
  private nameField(x: number, y: number, w: number, h: number): HTMLInputElement {
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = MAX_NAME;
    input.placeholder = "Your name";
    input.setAttribute("autocomplete", "nickname");
    input.spellcheck = false;
    input.value = G.save.playerName;
    input.setAttribute("aria-label", "Name on the leaderboard");
    Object.assign(input.style, {
      position: "fixed", boxSizing: "border-box", margin: "0", outline: "none", fontFamily: BODY, fontWeight: "600",
      color: hex(C.text), background: hex(C.panelHi), border: `2px solid ${hex(C.edge)}`, borderRadius: "10px",
      padding: "0 14px", zIndex: "10",
    });
    input.addEventListener("focus", () => (input.style.borderColor = hex(C.accent)));
    input.addEventListener("blur", () => (input.style.borderColor = hex(C.edge)));
    document.body.appendChild(input);

    // Keep it over the same spot of the canvas as the page resizes.
    const place = () => {
      const rect = this.game.canvas.getBoundingClientRect();
      const k = rect.width / W;
      Object.assign(input.style, {
        left: `${rect.left + x * k}px`, top: `${rect.top + y * k}px`, width: `${w * k}px`, height: `${h * k}px`,
        fontSize: `${Math.round(18 * k)}px`,
      });
    };
    place();
    this.scale.on(Phaser.Scale.Events.RESIZE, place);
    window.addEventListener("resize", place);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.scale.off(Phaser.Scale.Events.RESIZE, place);
      window.removeEventListener("resize", place);
      input.remove();
    });
    return input;
  }
}
