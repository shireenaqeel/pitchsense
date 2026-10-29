import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { G } from "../state";
import { BALLS, buy, equip, PITCHES, type Item } from "../systems/cosmetics";
import { currentLevel, settle } from "../ui/common";
import { inline } from "../ui/icons";
import { body, C, crisp, H, title, W } from "../ui/theme";
import { backButton, Button, panel } from "../ui/widgets";

/** Spend coins on pitch themes and balls. */
export class ShopScene extends Phaser.Scene {
  private layer!: Phaser.GameObjects.Container;
  private coins?: Phaser.GameObjects.Container;

  constructor() {
    super("Shop");
  }

  create(): void {
    crisp(this);
    this.cameras.main.fadeIn(250);
    this.add.rectangle(W / 2, H / 2, W, H, C.bg);
    backButton(this);
    this.add.text(W / 2, 44, "KIT ROOM", title(34, C.accent)).setOrigin(0.5);
    this.layer = this.add.container(0, 0);
    this.draw();
  }

  private draw(): void {
    this.layer.removeAll(true);
    this.coins?.destroy();
    this.coins = inline(this, W - 40, 44, [{ icon: "coin" }, ` ${G.save.coins}`], 24, C.gold, 1, "800");
    this.layer.add(this.add.text(60, 110, "PITCHES", title(16, C.muted)).setOrigin(0, 0.5));
    PITCHES.forEach((p, i) => this.card(p, 60 + i * 236, 134, () => {
      const g = this.add.graphics();
      g.fillStyle(p.stand, 1).fillRoundedRect(0, 0, 200, 110, 10);
      g.fillStyle(p.grass, 1).fillRect(14, 12, 172, 86);
      for (let k = 0; k < 86; k += 20) g.fillStyle(p.stripe, 1).fillRect(14, 12 + k, 172, 10);
      g.lineStyle(2, p.line, 1).strokeRect(14, 12, 172, 86).strokeRect(64, 12, 72, 26);
      g.fillStyle(p.home, 1).fillCircle(80, 70, 7);
      g.fillStyle(p.away, 1).fillCircle(110, 52, 7).fillCircle(125, 64, 7);
      g.fillStyle(p.keeper, 1).fillCircle(100, 22, 7);
      return g;
    }));
    this.layer.add(this.add.text(60, 420, "BALLS", title(16, C.muted)).setOrigin(0, 0.5));
    BALLS.forEach((b, i) => this.card(b, 60 + i * 236, 444, () => {
      const g = this.add.graphics();
      g.fillStyle(0x0f1d15, 1).fillRoundedRect(0, 0, 200, 110, 10);
      g.fillStyle(b.trail, 0.25).fillCircle(70, 55, 14).fillCircle(84, 55, 18);
      g.fillStyle(b.fill, 1).fillCircle(110, 55, 26);
      g.lineStyle(3, b.trim, 1).strokeCircle(110, 55, 26);
      g.fillStyle(b.trim, 1).fillCircle(110, 55, 9);
      return g;
    }));
  }

  private card(item: Item, x: number, y: number, art: () => Phaser.GameObjects.Graphics): void {
    const s = G.save;
    const owned = s.owned.includes(item.id);
    const equipped = s.equipped[item.kind] === item.id;
    this.layer.add(panel(this, x, y, 220, 252));
    const g = art();
    g.setPosition(x + 10, y + 12);
    this.layer.add(g);
    this.layer.add(this.add.text(x + 110, y + 146, item.name, body(16, C.text, "800")).setOrigin(0.5));
    this.layer.add(owned ? this.add.text(x + 110, y + 170, equipped ? "Equipped" : "Owned", body(14, C.muted)).setOrigin(0.5)
      : inline(this, x + 110, y + 170, [{ icon: "coin" }, ` ${item.price}`], 14, C.gold, 0.5));
    const label = equipped ? "In use" : owned ? "Use" : "Buy";
    const b = new Button(this, x + 110, y + 218, { w: 180, h: 44, label, size: 16, color: owned ? C.panelHi : C.accent,
      icon: equipped ? "check" : undefined }, () => {
      if (equipped) return;
      const levelBefore = currentLevel();
      if (!owned) {
        const r = buy(s, item);
        if (r === "poor") {
          sfx.miss();
          this.cameras.main.shake(120, 0.004);
          return;
        }
        sfx.coin();
      }
      equip(s, item);
      settle(this, levelBefore);
      this.draw();
    });
    b.setEnabled(!equipped && (owned || s.coins >= item.price));
    this.layer.add(b);
  }
}
