// Colours and text styles for the whole game.

import type Phaser from "phaser";

export const W = 1280;
export const H = 720;

/**
 * Backing-store pixels per game unit. The game is laid out at 1280 x 720, but
 * the canvas is drawn at the size it is actually shown on screen (window size x
 * devicePixelRatio), so lines and text stay sharp instead of being stretched.
 */
export const RES = typeof window === "undefined" ? 1
  : Math.min(3, Math.max(1, Math.ceil(2 * window.devicePixelRatio * Math.min(window.innerWidth / W, window.innerHeight / H)) / 2));

/** Zoom a scene's camera so the 1280 x 720 layout fills the high-resolution canvas. */
export function crisp(scene: Phaser.Scene): void {
  scene.cameras.main.setZoom(RES).centerOn(W / 2, H / 2);
}

export const C = {
  bg: 0x0b1410,
  panel: 0x13221a,
  panelHi: 0x1b3125,
  selected: 0x2b5a40,
  edge: 0x2b4a38,
  text: 0xf1f7f2,
  muted: 0x9db5a6,
  accent: 0x34d399,
  gold: 0xfacc15,
  exact: 0x22c55e,
  near: 0xf59e0b,
  miss: 0xef4444,
  boss: 0xa855f7,
};

export const hex = (c: number) => `#${c.toString(16).padStart(6, "0")}`;

export const DISPLAY = "Bungee, Impact, sans-serif";
export const BODY = "Inter, system-ui, sans-serif";

type Style = Phaser.Types.GameObjects.Text.TextStyle;

export function title(size: number, color = C.text): Style {
  return { fontFamily: DISPLAY, fontSize: `${size}px`, color: hex(color), resolution: RES };
}

export type Weight = "400" | "600" | "800";

export function body(size: number, color = C.text, weight: Weight = "600"): Style {
  return { fontFamily: BODY, fontSize: `${size}px`, color: hex(color), fontStyle: weight === "400" ? "normal" : weight, resolution: RES };
}

/** Colour for a band, from cold (speculative) to hot (sitter). */
export const BAND_COLORS = [0x60a5fa, 0x2dd4bf, 0xa3e635, 0xfb923c, 0xf43f5e];

export const GRADE_STYLE = {
  exact: { label: "SPOT ON!", color: C.exact },
  near: { label: "CLOSE!", color: C.near },
  miss: { label: "MISREAD", color: C.miss },
  timeout: { label: "TOO SLOW", color: C.miss },
} as const;
