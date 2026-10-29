import Phaser from "phaser";

import { G } from "../state";
import { conceptScores } from "../systems/adaptive";
import { ACHIEVEMENTS } from "../systems/achievements";
import { icon } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, bar, panel } from "../ui/widgets";

/** Trophies, achievements, and a scouting report on each concept. */
export class TrophyScene extends Phaser.Scene {
  constructor() {
    super("Trophies");
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this);
    this.add.text(W / 2, 44, "TROPHY ROOM", title(34, C.gold)).setOrigin(0.5);
    const s = G.save;

    // Trophy cabinet.
    panel(this, 40, 96, 1200, 120);
    G.data.career.forEach((w, i) => {
      const x = 40 + 100 + i * 200;
      const won = s.trophies.includes(w.name);
      icon(this, x, 140, "trophy", 44, won ? C.gold : 0x334155);
      this.add.text(x, 186, w.name, body(13, won ? C.gold : C.muted)).setOrigin(0.5);
    });

    // Achievements.
    panel(this, 40, 232, 740, 468);
    this.add.text(64, 262, `ACHIEVEMENTS  ${s.achievements.length}/${ACHIEVEMENTS.length}`, title(16, C.accent)).setOrigin(0, 0.5);
    ACHIEVEMENTS.forEach((a, i) => {
      const col = i % 2;
      const row = Math.floor(i / 2);
      const x = 64 + col * 360;
      const y = 302 + row * 44;
      const got = s.achievements.includes(a.id);
      icon(this, x + 16, y, got ? a.icon : "lock", 24, got ? C.gold : 0x475569);
      this.add.text(x + 42, y - 9, a.name, body(15, got ? C.text : C.muted, "800")).setOrigin(0, 0.5);
      this.add.text(x + 42, y + 11, a.desc, body(12, C.muted, "400")).setOrigin(0, 0.5);
    });

    // Scouting report: the adaptive engine's view of you.
    panel(this, 800, 232, 440, 468);
    this.add.text(824, 262, "SCOUTING REPORT", title(16, C.accent)).setOrigin(0, 0.5);
    this.add.text(824, 288, "Average read per concept. Rapid Fire serves your weak spots more.", body(12, C.muted, "400")).setOrigin(0, 0.5);
    const scores = conceptScores(s.concepts);
    const concepts = G.data.meta.concepts;
    concepts.forEach((c, i) => {
      const y = 322 + i * 36;
      const v = scores[c];
      const n = s.concepts[c]?.attempts ?? 0;
      this.add.text(824, y, c, body(14)).setOrigin(0, 0.5);
      const color = v === undefined ? C.muted : v >= 75 ? C.exact : v >= 50 ? C.near : C.miss;
      bar(this, 980, y - 6, 170, 12, color)(v === undefined ? 0 : v / 100);
      this.add.text(1216, y, v === undefined ? "—" : `${Math.round(v)} (${n})`, body(12, C.muted)).setOrigin(1, 0.5);
    });
    const ranked = Object.entries(scores).filter(([c]) => (s.concepts[c]?.attempts ?? 0) >= 3).sort((a, b) => a[1] - b[1]);
    const note = ranked.length ? `Work on: ${ranked[0][0]} · Strongest: ${ranked[ranked.length - 1][0]}` : "Play a few rounds to get a report.";
    this.add.text(1020, 680, note, body(13, C.gold)).setOrigin(0.5);
  }
}
