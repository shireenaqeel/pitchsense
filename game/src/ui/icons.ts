// One line-icon set for the whole game, in place of emoji. Each icon is a white
// 24 x 24 SVG, baked into a texture at boot and tinted wherever it is used, so
// every icon shares one stroke weight and stays sharp at any resolution.

import Phaser from "phaser";

import { body, type Weight } from "./theme";

const F = 'fill="#fff"';

const PATHS = {
  trophy: '<path d="M8 21h8M12 16.5V21M7 3.5h10V9a5 5 0 0 1-10 0z"/><path d="M7 5.5H3.5v1.5A3.5 3.5 0 0 0 7 10.5M17 5.5h3.5v1.5a3.5 3.5 0 0 1-3.5 3.5"/>',
  coin: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/>',
  model: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1" ' + F + '/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7.5a4 4 0 0 1 8 0V11"/>',
  star: '<path ' + F + ' d="M12 2.8l2.8 5.8 6.4.9-4.6 4.5 1.1 6.4L12 17.4l-5.7 3 1.1-6.4-4.6-4.5 6.4-.9z"/>',
  heart: '<path ' + F + ' d="M12 20.5s-8.5-5-8.5-11A4.6 4.6 0 0 1 12 7a4.6 4.6 0 0 1 8.5 2.5c0 6-8.5 11-8.5 11z"/>',
  heartEmpty: '<path d="M12 20.5s-8.5-5-8.5-11A4.6 4.6 0 0 1 12 7a4.6 4.6 0 0 1 8.5 2.5c0 6-8.5 11-8.5 11z"/>',
  flame: '<path d="M12 21.5c3.9 0 6.8-2.6 6.8-6.5 0-3.5-2.3-5.9-4.2-8.4-.5 1.9-1.5 3-2.8 3.6.1-3.6-1.5-6.1-3.6-7.7.2 3.2-1.5 5.4-2.9 7.3-.8 1.3-1.1 2.8-1.1 5.2 0 3.9 3.9 6.5 7.8 6.5z"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="16" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  stopwatch: '<circle cx="12" cy="13.5" r="8"/><path d="M12 13.5V9.5M10 2.5h4M18.5 6.5L20 5"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4" ' + F + '/>',
  ball: '<circle cx="12" cy="12" r="9.5"/><path ' + F + ' d="M12 7.6l3.3 2.4-1.3 3.9h-4L8.7 10z"/><path d="M12 7.6V2.6M15.3 10l4.7-1.5M14 13.9l2.9 4M10 13.9l-2.9 4M8.7 10L4 8.5"/>',
  boot: '<path d="M5 4h5.5v7l6.8 2.4c1.9.7 3.2 1.9 3.2 3.6V19H5z"/><path d="M5 15.5h15.5M8 19v2M12 19v2M16 19v2"/>',
  head: '<circle cx="9.5" cy="14" r="6"/><circle cx="18" cy="5.5" r="3"/><path d="M14.5 9l1.3-1.3"/>',
  ruler: '<rect x="2.5" y="8" width="19" height="8" rx="1.5"/><path d="M6.5 8v3M10.5 8v4M14.5 8v3M18.5 8v4"/>',
  bag: '<path d="M5 8h14l-1.2 13H6.2z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
  medal: '<circle cx="12" cy="15.5" r="5.5"/><path d="M8.6 11.2L6 3h4l2 5 2-5h4l-2.6 8.2"/>',
  help: '<circle cx="12" cy="12" r="9.5"/><path d="M9.3 9.2a2.8 2.8 0 0 1 5.4 1c0 1.9-2.7 2.3-2.7 4.3"/><circle cx="12" cy="17.6" r=".7" ' + F + '/>',
  sound: '<path ' + F + ' d="M3.5 9h4l5-4v14l-5-4h-4z"/><path d="M16 8.5a5 5 0 0 1 0 7M19 5.5a9 9 0 0 1 0 13"/>',
  mute: '<path ' + F + ' d="M3.5 9h4l5-4v14l-5-4h-4z"/><path d="M16 9l5.5 6M21.5 9L16 15"/>',
  check: '<path d="M4.5 12.5l5 5L19.5 7"/>',
  cross: '<path d="M6 6l12 12M18 6L6 18"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2.5" width="6" height="3.5" rx="1"/><path d="M9 11h6M9 15h4"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  hat: '<path d="M7 17V5.5h10V17"/><path d="M3 17h18M7 13h10"/>',
  zap: '<path ' + F + ' d="M13 2L4.5 13.5h6.5L10 22l8.5-11.5H12z"/>',
  goal: '<path d="M3 19V6h18v13"/><path stroke-width="1.1" d="M3 10.3h18M3 14.6h18M7.5 6v13M12 6v13M16.5 6v13"/>',
  curve: '<path d="M3.5 19.5C6 10 13 5.5 20.5 5"/><path d="M15.5 2.5l5 2.5-2.5 5"/>',
  shield: '<path d="M12 2.5l8 3v6c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10v-6z"/>',
  crown: '<path d="M3 18L4.5 7l5 4.5L12 4.5l2.5 7 5-4.5L21 18z"/><path d="M3 21h18"/>',
  badge: '<circle cx="12" cy="12" r="9.5"/><path d="M8 12.3l2.8 2.8L16.5 9.5"/>',
  shirt: '<path d="M8.5 3L3 6.5l2.2 5 2.8-1.2V21h8V10.3l2.8 1.2 2.2-5L15.5 3c-.6 1.6-1.9 2.8-3.5 2.8S9.1 4.6 8.5 3z"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h14v15H6a2 2 0 0 0-2 2z"/><path d="M4 20a2 2 0 0 0 2 2h14v-4M8 7.5h8M8 11h5"/>',
  cap: '<path d="M2 9.5l10-5 10 5-10 5z"/><path d="M6 11.5v4.8c2.4 2.3 9.6 2.3 12 0v-4.8M22 9.5v6"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  next: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  play: '<path ' + F + ' d="M7 4.5l13 7.5-13 7.5z"/>',
  retry: '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v5h-5"/>',
  link: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  bulb: '<path d="M9 18h6M10 21.5h4M12 2.5a6.5 6.5 0 0 0-3.8 11.8c.6.5 1 1.2 1 2V16h5.6v-.2c0-.8.4-1.5 1-2A6.5 6.5 0 0 0 12 2.5z"/>',
  up: '<path ' + F + ' d="M12 5l8 13H4z"/>',
  down: '<path ' + F + ' d="M12 19L4 6h16z"/>',
  levelUp: '<circle cx="12" cy="12" r="9.5"/><path d="M12 17V7.5M7.5 11.5L12 7l4.5 4.5"/>',
  whistle: '<path d="M3 11.5a5.5 5.5 0 1 0 11 0V8.5h7.5v4L14 13"/><circle cx="8.5" cy="11.5" r="1.6" ' + F + '/><path d="M6 8.5V4.5"/>',
} as const;

export type IconName = keyof typeof PATHS | `bars${0 | 1 | 2 | 3 | 4}`;

/** "Signal" bars for the five chance bands: band i fills i + 1 bars. */
function bars(filled: number): string {
  let out = "";
  for (let i = 0; i < 5; i++) {
    const h = 4 + i * 3.5;
    const x = 2 + i * 4.3;
    out += `<rect x="${x}" y="${21 - h}" width="2.8" height="${h}" rx="0.8" ${i <= filled ? F : 'stroke-width="1.2" opacity="0.45"'}/>`;
  }
  return out;
}

const SVGS: Record<string, string> = {
  ...PATHS,
  bars0: bars(0), bars1: bars(1), bars2: bars(2), bars3: bars(3), bars4: bars(4),
};

/** Texture edge in pixels; large enough to stay sharp when drawn big on a 3x screen. */
const BAKE = 144;

const key = (name: IconName) => `icon.${name}`;

/** Queue every icon on the scene's loader (call from a `preload`). */
export function loadIcons(scene: Phaser.Scene): void {
  for (const [name, inner] of Object.entries(SVGS)) {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" ' +
      `stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
    const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
    scene.load.svg(key(name as IconName), url, { width: BAKE, height: BAKE });
  }
}

/** An icon centred on (x, y), `size` game pixels across, tinted `color`. */
export function icon(scene: Phaser.Scene, x: number, y: number, name: IconName, size: number, color = 0xffffff): Phaser.GameObjects.Image {
  return scene.add.image(x, y, key(name)).setDisplaySize(size, size).setTint(color);
}

/** Icon for chance band `i`. */
export const bandIcon = (i: number): IconName => `bars${Math.max(0, Math.min(4, i)) as 0 | 1 | 2 | 3 | 4}`;

/** A piece of an inline row: plain text, or an icon (optionally its own colour). */
export type Part = string | { icon: IconName; color?: number };

/**
 * Text and icons on one line, e.g. [{icon: "coin"}, " 120"]. `originX` works
 * like a Text's (0 left, 0.5 centre, 1 right); the row is centred on y.
 */
export function inline(
  scene: Phaser.Scene,
  x: number,
  y: number,
  parts: Part[],
  size: number,
  color: number,
  originX = 0,
  weight: Weight = "600",
): Phaser.GameObjects.Container {
  const row = scene.add.container(x, y);
  let cx = 0;
  const iconSize = Math.round(size * 1.2);
  for (const part of parts) {
    if (typeof part === "string") {
      if (!part) continue;
      const t = scene.add.text(cx, 0, part, body(size, color, weight)).setOrigin(0, 0.5);
      row.add(t);
      cx += t.width;
    } else {
      row.add(icon(scene, cx + iconSize / 2, 0, part.icon, iconSize, part.color ?? color));
      cx += iconSize + Math.round(size * 0.3);
    }
  }
  for (const child of row.list) (child as Phaser.GameObjects.Image).x -= cx * originX;
  row.setSize(cx, iconSize);
  return row;
}

/** A row of `max` stars with the first `n` lit. */
export function starRow(scene: Phaser.Scene, x: number, y: number, n: number, size: number, max = 3,
  on = 0xfacc15, off = 0x475569): Phaser.GameObjects.Container {
  const gap = size * 1.08;
  const row = scene.add.container(x, y);
  for (let i = 0; i < max; i++) row.add(icon(scene, (i - (max - 1) / 2) * gap, 0, "star", size, i < n ? on : off));
  return row;
}
