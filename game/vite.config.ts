import { defineConfig } from "vite";

// Relative base so the build works from any sub-path (GitHub Pages serves the
// game from /pitchsense/).
export default defineConfig({
  base: "./",
  build: { chunkSizeWarningLimit: 1600 },
});
