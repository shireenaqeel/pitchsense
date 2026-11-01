import Phaser from "phaser";

import type { Meta, Moment, Puzzle, Shot, World } from "../data/types";
import { G } from "../state";
import { loadIcons } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { Button } from "../ui/widgets";

/** Loads the exported data with a progress bar and bakes the tiny textures. */
export class BootScene extends Phaser.Scene {
  private failed = false;

  constructor() {
    super("Boot");
  }

  preload(): void {
    crisp(this);
    this.add.text(W / 2, H / 2 - 60, "PITCHSENSE", title(56, C.accent)).setOrigin(0.5);
    this.add.text(W / 2, H / 2 + 40, "Loading 7,500 real shots…", body(16, C.muted)).setOrigin(0.5);
    const g = this.add.graphics();
    this.load.on("progress", (v: number) => {
      g.clear();
      g.fillStyle(0x000000, 0.5).fillRoundedRect(W / 2 - 200, H / 2, 400, 14, 7);
      g.fillStyle(C.accent, 1).fillRoundedRect(W / 2 - 200, H / 2, Math.max(14, 400 * v), 14, 7);
    });
    // The moments are optional: without them only What Happens Next? is unavailable.
    this.load.on("loaderror", (file: Phaser.Loader.File) => {
      if (file.key !== "moments") this.failed = true;
    });

    this.load.json("shots", "data/shots.json");
    this.load.json("career", "data/career.json");
    this.load.json("puzzles", "data/puzzles.json");
    this.load.json("meta", "data/meta.json");
    this.load.json("moments", "data/moments.json");
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
    if (this.failed || !shots) {
      this.loadFailed();
      return;
    }
    G.setData(shots, this.cache.json.get("career") as World[], this.cache.json.get("puzzles") as Puzzle[],
      this.cache.json.get("meta") as Meta, (this.cache.json.get("moments") as Moment[] | undefined) ?? []);
    G.load();

    this.scene.launch("Overlay");
    const fonts = document.fonts ? Promise.all([document.fonts.load("40px Bungee"), document.fonts.load("800 16px Inter")]) : Promise.resolve();
    void fonts.catch(() => undefined).then(() => this.scene.start("Menu"));
  }

  /** The data didn't arrive (a dropped connection, usually): say so and offer a retry. */
  private loadFailed(): void {
    this.children.removeAll(true);
    this.add.text(W / 2, H / 2 - 110, "KICK-OFF DELAYED", title(48, C.gold)).setOrigin(0.5);
    this.add.text(W / 2, H / 2 - 30, "The match data didn't load. Check your connection, then try again.",
      body(18, C.muted, "400")).setOrigin(0.5);
    new Button(this, W / 2, H / 2 + 60, { w: 280, h: 58, label: "Try again", size: 18, display: true, color: C.accent },
      () => location.reload());
  }
}
