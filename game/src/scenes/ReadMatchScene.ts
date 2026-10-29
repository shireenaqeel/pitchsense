import Phaser from "phaser";

import { REF_CALLS } from "../academy/referee";
import { G } from "../state";
import { NEXT_EXACT, NEXT_ROUND } from "../systems/next";
import { icon, type IconName } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, Button, goTo, panel } from "../ui/widgets";
import { REF_ROUND } from "./RefScene";

const CARD_W = 500;
const CARD_H = 470;

/** Read the Match: pick drawn referee calls or real "what happens next" moments. */
export class ReadMatchScene extends Phaser.Scene {
  constructor() {
    super("ReadMatch");
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this);
    this.add.text(W / 2, 44, "READ THE MATCH", title(34, C.gold)).setOrigin(0.5);
    this.add.text(W / 2, 84, "Two ways to practise watching football: make the referee's call, or read a real move.",
      body(15, C.muted)).setOrigin(0.5);

    const s = G.save;
    const hasMoments = G.data.moments.length > 0;
    this.card(W / 2 - CARD_W - 20, "whistle", 0x14b8a6, "REFEREE'S EYE", "DRAWN SCENARIOS",
      "Offside or onside? Penalty or free kick? Play on, or a card? Each situation is drawn on the pitch. " +
      "Make the call, then see the rule behind it, and which Academy lesson teaches it.",
      `${REF_CALLS.length} situations · ${REF_ROUND} a round · best ${s.refBest}/${REF_ROUND}`,
      () => goTo(this, "Referee"));
    this.card(W / 2 + 20, "eye", 0x8b5cf6, "WHAT HAPPENS NEXT?", "REAL MOVES",
      "Real moments from Euro 2020, the 2022 World Cup and Euro 2024, with every player the camera could see. " +
      "The ball is at a player's feet in the final third: shoot, pass, cross or dribble? Then watch what really happened.",
      hasMoments ? `${G.data.moments.length} moments · ${NEXT_ROUND} a round · best ${s.nextBest}/${NEXT_ROUND * NEXT_EXACT}`
        : "Run the export to add the real moments",
      hasMoments ? () => goTo(this, "Next") : null);
  }

  private card(x: number, glyph: IconName, color: number, name: string, kind: string, text: string, foot: string,
    go: (() => void) | null): void {
    const y = 130;
    panel(this, x, y, CARD_W, CARD_H);
    icon(this, x + CARD_W / 2, y + 70, glyph, 64, color);
    this.add.text(x + CARD_W / 2, y + 138, kind, body(12, color, "800")).setOrigin(0.5);
    this.add.text(x + CARD_W / 2, y + 168, name, title(28, C.text)).setOrigin(0.5);
    this.add.text(x + CARD_W / 2, y + 206, text, {
      ...body(15, C.muted, "400"), align: "center", wordWrap: { width: CARD_W - 70 }, lineSpacing: 6,
    }).setOrigin(0.5, 0);
    this.add.text(x + CARD_W / 2, y + 352, foot, body(13, C.muted, "800")).setOrigin(0.5);
    const b = new Button(this, x + CARD_W / 2, y + 410, { w: 260, h: 56, label: "Play", icon: "play", size: 18,
      display: true, color: go ? C.accent : C.panelHi }, go ?? (() => undefined));
    if (!go) b.setEnabled(false);
  }
}
