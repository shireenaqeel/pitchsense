// Fonts ship with the game rather than coming from Google, so a visit makes no
// third-party requests.
import "@fontsource/bungee/latin-400.css";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-800.css";
import Phaser from "phaser";

import { AcademyScene } from "./scenes/AcademyScene";
import { BootScene } from "./scenes/BootScene";
import { CareerScene } from "./scenes/CareerScene";
import { LeaderboardScene } from "./scenes/LeaderboardScene";
import { LessonScene } from "./scenes/LessonScene";
import { MenuScene } from "./scenes/MenuScene";
import { NextScene } from "./scenes/NextScene";
import { OverlayScene } from "./scenes/OverlayScene";
import { PlayScene } from "./scenes/PlayScene";
import { ReadMatchScene } from "./scenes/ReadMatchScene";
import { RefScene } from "./scenes/RefScene";
import { ResultsScene } from "./scenes/ResultsScene";
import { ShopScene } from "./scenes/ShopScene";
import { StrikerScene } from "./scenes/StrikerScene";
import { TrophyScene } from "./scenes/TrophyScene";
import { C, H, RES, W } from "./ui/theme";

new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game",
  // Drawn at screen resolution; every scene zooms its camera by RES (see `crisp`).
  width: W * RES,
  height: H * RES,
  backgroundColor: C.bg,
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  render: { antialias: true, roundPixels: false },
  scene: [BootScene, MenuScene, AcademyScene, LessonScene, CareerScene, PlayScene, ResultsScene, StrikerScene,
    ReadMatchScene, RefScene, NextScene, TrophyScene, ShopScene, LeaderboardScene, OverlayScene],
});
