import { defineConfig, type Plugin } from "vite";

// GitHub Pages can't send security headers, so the built page carries its
// Content-Security-Policy in a <meta> tag. Everything is same-origin; blob: is
// for the icon SVGs (see ui/icons.ts) and data: for Phaser's generated
// textures. Dev builds skip it, since Vite's hot reload needs inline scripts
// and a websocket.
const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self' data: blob:",
  "media-src 'self' data: blob:",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

const csp = (): Plugin => ({
  name: "csp",
  apply: "build",
  transformIndexHtml: (html) =>
    html.replace(/(<meta charset[^>]*>)/, `$1\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`),
});

// Relative base so the build works from any sub-path (GitHub Pages serves the
// game from /pitchsense/).
export default defineConfig({
  base: "./",
  // Phaser gets a chunk of its own: it's most of the download, and it only
  // changes when the engine is upgraded, so browsers keep it cached.
  build: { chunkSizeWarningLimit: 1600, rollupOptions: { output: { manualChunks: { phaser: ["phaser"] } } } },
  plugins: [csp()],
});
