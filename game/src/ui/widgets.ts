// Small reusable UI pieces drawn with Phaser graphics.

import Phaser from "phaser";

import { sfx } from "../audio/sfx";
import { icon, type IconName } from "./icons";
import { body, C, hex, title } from "./theme";

export interface ButtonOpts {
  w: number;
  h: number;
  label: string;
  sub?: string;
  color?: number;
  size?: number;
  /** Small keycap shown at the left, e.g. "1". */
  key?: string;
  align?: "center" | "left";
  display?: boolean;
  /** Icon drawn before the label (or alone, if the label is empty). */
  icon?: IconName;
  iconColor?: number;
  /** Wrap the label onto more lines past this width. */
  wrap?: number;
}

/** A rounded button with hover, press and disabled states. (x, y) is its centre. */
export class Button extends Phaser.GameObjects.Container {
  private bg: Phaser.GameObjects.Graphics;
  readonly label: Phaser.GameObjects.Text;
  private sub?: Phaser.GameObjects.Text;
  private glyph?: Phaser.GameObjects.Image;
  private color: number;
  private enabled = true;
  private selected = false;

  constructor(scene: Phaser.Scene, x: number, y: number, private opts: ButtonOpts, onClick: () => void) {
    super(scene, x, y);
    this.color = opts.color ?? C.panelHi;
    this.bg = scene.add.graphics();
    this.add(this.bg);

    const left = opts.align === "left";
    const size = opts.size ?? 20;
    const style = opts.display ? title(size) : body(size, C.text, "800");
    if (opts.wrap) Object.assign(style, { wordWrap: { width: opts.wrap }, lineSpacing: 2 });
    const ly = opts.sub ? -11 : 0;
    this.label = scene.add.text(0, ly, opts.label, style).setOrigin(left ? 0 : 0.5, 0.5);
    this.add(this.label);
    let textX = left ? -opts.w / 2 + (opts.key ? 58 : 20) : 0;
    if (opts.icon) {
      const is = Math.round(size * 1.25);
      const gap = opts.label ? Math.round(size * 0.5) : 0;
      // Centred buttons centre the icon and label together.
      const start = left ? textX : -(is + gap + this.label.width) / 2;
      this.glyph = icon(scene, start + is / 2, ly, opts.icon, is, opts.iconColor ?? C.text);
      this.add(this.glyph);
      textX = start + is + gap;
      this.label.setOrigin(0, 0.5);
    }
    this.label.setX(textX);
    if (opts.sub) {
      this.sub = scene.add.text(textX, 14, opts.sub, body(13, C.muted, "400")).setOrigin(left || opts.icon ? 0 : 0.5, 0.5);
      if (opts.icon && !left) this.sub.setOrigin(0.5, 0.5).setX(0);
      this.add(this.sub);
    }
    if (opts.key) {
      const kx = -opts.w / 2 + 28;
      const cap = scene.add.graphics();
      cap.fillStyle(0x000000, 0.35).fillRoundedRect(kx - 14, -14, 28, 28, 6);
      this.add(cap);
      this.add(scene.add.text(kx, 0, opts.key, body(15, C.muted, "800")).setOrigin(0.5));
    }
    this.draw(false);

    this.setSize(opts.w, opts.h);
    this.setInteractive({ useHandCursor: true });
    this.on("pointerover", () => {
      if (!this.enabled) return;
      this.draw(true);
      sfx.hover();
      scene.tweens.add({ targets: this, scale: 1.03, duration: 90 });
    });
    this.on("pointerout", () => {
      this.draw(false);
      scene.tweens.add({ targets: this, scale: 1, duration: 90 });
    });
    this.on("pointerdown", () => this.press(onClick));
    scene.add.existing(this);
  }

  press(onClick: () => void): void {
    if (!this.enabled) return;
    sfx.click();
    this.scene.tweens.add({ targets: this, scale: 0.95, duration: 60, yoyo: true });
    onClick();
  }

  private draw(hover: boolean): void {
    const { w, h } = this.opts;
    // Selected keeps the fill (so coloured labels stay readable) and gets a bright frame.
    const fill = this.selected ? C.selected : this.color;
    this.bg.clear();
    this.bg.fillStyle(0x000000, 0.35).fillRoundedRect(-w / 2, -h / 2 + 4, w, h, 12);
    this.bg.fillStyle(fill, this.enabled ? 1 : 0.4).fillRoundedRect(-w / 2, -h / 2, w, h, 12);
    const edge = this.selected ? 0xffffff : hover ? 0xffffff : C.edge;
    this.bg.lineStyle(this.selected ? 3 : 2, edge, hover || this.selected ? 0.95 : 0.8).strokeRoundedRect(-w / 2, -h / 2, w, h, 12);
  }

  setEnabled(on: boolean): this {
    this.enabled = on;
    this.setAlpha(on ? 1 : 0.55);
    this.draw(false);
    return this;
  }

  setSelected(on: boolean): this {
    this.selected = on;
    this.draw(false);
    return this;
  }

  setIcon(name: IconName): this {
    this.glyph?.setTexture(`icon.${name}`);
    return this;
  }

  setColor(color: number): this {
    this.color = color;
    this.draw(false);
    return this;
  }
}

/** A rounded panel; (x, y) is its top-left corner. */
export function panel(
  scene: Phaser.Scene,
  x: number,
  y: number,
  w: number,
  h: number,
  color = C.panel,
  alpha = 0.95,
): Phaser.GameObjects.Graphics {
  const g = scene.add.graphics();
  g.fillStyle(0x000000, 0.3).fillRoundedRect(x, y + 5, w, h, 16);
  g.fillStyle(color, alpha).fillRoundedRect(x, y, w, h, 16);
  g.lineStyle(2, C.edge, 0.9).strokeRoundedRect(x, y, w, h, 16);
  return g;
}

/** Text that pops up, drifts and fades: "+120", "COMBO x3", damage numbers. */
export function floatText(scene: Phaser.Scene, x: number, y: number, text: string, color: number, size = 28): void {
  const t = scene.add.text(x, y, text, title(size, color)).setOrigin(0.5).setDepth(50).setScale(0.4);
  t.setStroke("#000000", 6);
  scene.tweens.add({ targets: t, scale: 1, duration: 180, ease: "Back.Out" });
  scene.tweens.add({ targets: t, y: y - 60, alpha: 0, delay: 500, duration: 700, onComplete: () => t.destroy() });
}

/** Fade the camera out, then start another scene. */
export function goTo(scene: Phaser.Scene, key: string, data?: object): void {
  scene.input.enabled = false;
  scene.cameras.main.fadeOut(220, 11, 20, 16);
  scene.cameras.main.once(Phaser.Cameras.Scene2D.Events.FADE_OUT_COMPLETE, () => scene.scene.start(key, data));
}

/** Stars as text, for small labels; big star displays use `starRow`. */
export function stars(n: number, max = 3): string {
  return "★".repeat(n) + "☆".repeat(Math.max(0, max - n));
}

/** A horizontal progress bar; returns a setter for 0..1. */
export function bar(
  scene: Phaser.Scene,
  x: number,
  y: number,
  w: number,
  h: number,
  color: number,
): (v: number, c?: number) => void {
  const g = scene.add.graphics();
  return (v: number, c = color) => {
    const f = Phaser.Math.Clamp(v, 0, 1);
    g.clear();
    g.fillStyle(0x000000, 0.45).fillRoundedRect(x, y, w, h, h / 2);
    if (f > 0) g.fillStyle(c, 1).fillRoundedRect(x, y, Math.max(h, w * f), h, h / 2);
  };
}

export function backButton(scene: Phaser.Scene, to = "Menu", data?: object): Button {
  const b = new Button(scene, 90, 44, { w: 140, h: 44, label: "Back", size: 16, icon: "back" }, () => goTo(scene, to, data));
  scene.input.keyboard?.on("keydown-ESC", () => goTo(scene, to, data));
  return b;
}

export { hex };
