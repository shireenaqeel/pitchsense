import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { icon, type IconName } from "../ui/icons";
import { body, C, crisp, H, title } from "../ui/theme";

export interface Toast {
  icon: IconName;
  head: string;
  text: string;
  color?: number;
}

/** Sits above every scene and shows achievement and level-up toasts in turn. */
export class OverlayScene extends Phaser.Scene {
  private queue: Toast[] = [];
  private busy = false;

  constructor() {
    super("Overlay");
  }

  create(): void {
    crisp(this);
    this.scene.bringToTop();
    this.game.events.on("toast", (t: Toast) => {
      this.queue.push(t);
      this.next();
    });
    // Other scenes start after this one, so keep it on top as they do.
    this.game.events.on("prestep", () => {
      const scenes = this.scene.manager.getScenes(true);
      if (scenes[scenes.length - 1] !== this) this.scene.bringToTop();
    });
  }

  private next(): void {
    if (this.busy) return;
    const t = this.queue.shift();
    if (!t) return;
    this.busy = true;
    sfx.achievement();
    const w = 420;
    // Bottom-left, over the pitch's halfway line: clear of every scene's HUD and buttons.
    const box = this.add.container(24 + w / 2, H + 60);
    const g = this.add.graphics();
    g.fillStyle(0x000000, 0.4).fillRoundedRect(-w / 2, -34, w, 76, 14);
    g.fillStyle(C.panelHi, 1).fillRoundedRect(-w / 2, -38, w, 76, 14);
    g.lineStyle(3, t.color ?? C.gold, 1).strokeRoundedRect(-w / 2, -38, w, 76, 14);
    box.add(g);
    box.add(icon(this, -w / 2 + 40, 0, t.icon, 34, t.color ?? C.gold));
    box.add(this.add.text(-w / 2 + 76, -16, t.head, title(16, t.color ?? C.gold)).setOrigin(0, 0.5));
    box.add(this.add.text(-w / 2 + 76, 12, t.text, body(14)).setOrigin(0, 0.5));
    this.tweens.add({
      targets: box,
      y: H - 70,
      duration: 380,
      ease: "Back.Out",
      hold: 2200,
      yoyo: true,
      onComplete: () => {
        box.destroy();
        this.busy = false;
        this.next();
      },
    });
  }
}

export function toast(scene: Phaser.Scene, t: Toast): void {
  scene.game.events.emit("toast", t);
}
