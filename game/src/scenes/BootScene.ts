import Phaser from "phaser";

import type { Meta, Puzzle, Shot, World } from "../data/types";
import { G } from "../state";
import { loadIcons } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";

/** Loads the exported data with a progress bar and bakes the tiny textures. */
export class BootScene extends Phaser.Scene {
  constructor() {
    super("Boot");
  }

  preload(): void {
    crisp(this);
    this.add.text(W / 2, H / 2 - 60, "PITCHSENSE", title(56, C.accent)).setOrigin(0.5);
    const label = this.add.text(W / 2, H / 2 + 40, "Loading 7,500 real shots…", body(16, C.muted)).setOrigin(0.5);
    const g = this.add.graphics();
    this.load.on("progress", (v: number) => {
      g.clear();
      g.fillStyle(0x000000, 0.5).fillRoundedRect(W / 2 - 200, H / 2, 400, 14, 7);
      g.fillStyle(C.accent, 1).fillRoundedRect(W / 2 - 200, H / 2, Math.max(14, 400 * v), 14, 7);
    });
    this.load.on("loaderror", () => label.setText("Could not load the game data. Run `python -m pitchsense.export_game`."));

    this.load.json("shots", "data/shots.json");
    this.load.json("career", "data/career.json");
    this.load.json("puzzles", "data/puzzles.json");
    this.load.json("meta", "data/meta.json");
    loadIcons(this);
  }

  create(): void {
    const g = this.make.graphics({}, false);
    g.fillStyle(0xffffff, 1).fillCircle(16, 16, 16);
    g.generateTexture("dot", 32, 32);
    g.clear();
    g.fillStyle(0xffffff, 1).fillRect(0, 0, 8, 14);
    g.generateTexture("confetti", 8, 14);
    g.destroy();

    const shots = this.cache.json.get("shots") as Shot[] | undefined;
    if (!shots) return;
    G.setData(shots, this.cache.json.get("career") as World[], this.cache.json.get("puzzles") as Puzzle[],
      this.cache.json.get("meta") as Meta);
    G.load();

    this.scene.launch("Overlay");
    const fonts = document.fonts ? Promise.all([document.fonts.load("40px Bungee"), document.fonts.load("800 16px Inter")]) : Promise.resolve();
    void fonts.catch(() => undefined).then(() => this.scene.start("Menu"));
  }
}
