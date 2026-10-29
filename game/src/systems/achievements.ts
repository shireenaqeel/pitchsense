// Achievements: each is a predicate over the save, checked after every round.

import type { IconName } from "../ui/icons";
import { LESSONS } from "../academy/curriculum";
import type { SaveData } from "./save";

export interface Achievement {
  id: string;
  icon: IconName;
  name: string;
  desc: string;
  check: (s: SaveData) => boolean;
}

export const ACHIEVEMENT_COINS = 50;

const SITTER = 4;

export const ACHIEVEMENTS: Achievement[] = [
  { id: "first_lesson", icon: "book", name: "Back to School", desc: "Finish your first Academy lesson",
    check: (s) => s.academy.length >= 1 },
  { id: "literate", icon: "cap", name: "Football Literate", desc: "Finish every Academy lesson",
    check: (s) => LESSONS.every((l) => s.academy.includes(l.id)) },
  { id: "whistle", icon: "whistle", name: "Ref's Eye", desc: "A perfect round of Referee's Eye",
    check: (s) => s.refBest >= 8 },
  { id: "ahead", icon: "next", name: "Ahead of the Play", desc: "Score 600 in What Happens Next?",
    check: (s) => s.nextBest >= 600 },
  { id: "first_read", icon: "eye", name: "First Read", desc: "Read your first chance",
    check: (s) => s.stats.reads >= 1 },
  { id: "hat_trick", icon: "hat", name: "Hat-trick", desc: "Three exact reads in a row",
    check: (s) => s.stats.bestCombo >= 3 },
  { id: "on_fire", icon: "flame", name: "On Fire", desc: "Eight exact reads in a row",
    check: (s) => s.stats.bestCombo >= 8 },
  { id: "speed_demon", icon: "zap", name: "Speed Demon", desc: "An exact read in under 2 seconds",
    check: (s) => s.stats.fastestExactMs !== null && s.stats.fastestExactMs < 2000 },
  { id: "sitter_spotter", icon: "goal", name: "Sitter Spotter", desc: "Call 5 sitters exactly",
    check: (s) => s.stats.bandExact[SITTER] >= 5 },
  { id: "screamer_sense", icon: "curve", name: "Screamer Sense", desc: "Exact reads on 10 long-range shots",
    check: (s) => (s.stats.conceptExact["Long range"] ?? 0) >= 10 },
  { id: "header_hero", icon: "head", name: "Header Hero", desc: "Exact reads on 10 headers",
    check: (s) => (s.stats.conceptExact["Header"] ?? 0) >= 10 },
  { id: "centurion", icon: "badge", name: "Centurion", desc: "Read 100 chances",
    check: (s) => s.stats.reads >= 100 },
  { id: "clean_sheet", icon: "shield", name: "Clean Sheet", desc: "Finish a career match without losing a heart",
    check: (s) => s.stats.flawlessMatches >= 1 },
  { id: "perfectionist", icon: "star", name: "Perfectionist", desc: "Three stars on a career match",
    check: (s) => s.stats.threeStarMatches >= 1 },
  { id: "giant_killer", icon: "crown", name: "Giant Killer", desc: "Beat The Model in a final",
    check: (s) => s.stats.bossesBeaten >= 1 },
  { id: "seen_it_all", icon: "trophy", name: "Seen It All", desc: "Win all six trophies",
    check: (s) => s.trophies.length >= 6 },
  { id: "rapid_1000", icon: "stopwatch", name: "Rapid Thousand", desc: "Score 1,000 in Rapid Fire",
    check: (s) => s.rapidBest >= 1000 },
  { id: "regular", icon: "calendar", name: "Regular", desc: "Play the daily three days running",
    check: (s) => s.daily.bestStreak >= 3 },
  { id: "instinct", icon: "target", name: "Striker's Instinct", desc: "Three stars on every striker puzzle",
    check: (s) => Object.keys(s.puzzles).length >= 8 && Object.values(s.puzzles).every((v) => v >= 3) },
  { id: "kit_man", icon: "shirt", name: "Kit Man", desc: "Buy something from the shop",
    check: (s) => s.stats.purchases >= 1 },
];

/** Unlock everything newly earned, pay out coins, and return what unlocked. */
export function unlockNew(save: SaveData): Achievement[] {
  const fresh = ACHIEVEMENTS.filter((a) => !save.achievements.includes(a.id) && a.check(save));
  for (const a of fresh) {
    save.achievements.push(a.id);
    save.coins += ACHIEVEMENT_COINS;
  }
  return fresh;
}
