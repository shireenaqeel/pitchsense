import { describe, expect, it } from "vitest";

import { bandBalance, conceptWeights, pickAdaptive, updateProgress } from "../src/systems/adaptive";
import { ACHIEVEMENTS, ACHIEVEMENT_COINS, unlockNew } from "../src/systems/achievements";
import { bossHp, isUnlocked, matchStars, puzzleStars } from "../src/systems/career";
import { buy, equip, PITCHES } from "../src/systems/cosmetics";
import { levelFromXp, rankFor, xpToNext } from "../src/systems/progression";
import { recordDaily, recordMatch, recordRead } from "../src/systems/record";
import { dailyNumber, dailyPicks, isNextDay, mulberry32 } from "../src/systems/rng";
import { defaultSave, loadSave, mergeSave, SAVE_KEY } from "../src/systems/save";
import { comboMultiplier, grade, scoreRound, speedBonus } from "../src/systems/scoring";

describe("scoring", () => {
  it("grades a read against the model's band", () => {
    expect(grade(2, 2)).toBe("exact");
    expect(grade(1, 2)).toBe("near");
    expect(grade(4, 2)).toBe("miss");
    expect(grade(null, 2)).toBe("timeout");
  });

  it("only pays a speed bonus for good reads", () => {
    expect(speedBonus("exact", 0, 10_000)).toBe(25);
    expect(speedBonus("exact", 10_000, 10_000)).toBe(0);
    expect(speedBonus("near", 0, 10_000)).toBe(13);
    expect(speedBonus("miss", 0, 10_000)).toBe(0);
  });

  it("builds, holds and breaks combos", () => {
    let r = scoreRound(3, 3, 5000, 10_000, 0);
    expect(r.combo).toBe(1);
    r = scoreRound(3, 3, 5000, 10_000, r.combo);
    expect(r.combo).toBe(2);
    expect(r.multiplier).toBe(1.25);
    expect(scoreRound(2, 3, 0, 10_000, 2).combo).toBe(2);
    expect(scoreRound(0, 3, 0, 10_000, 5).combo).toBe(0);
    expect(comboMultiplier(6)).toBe(2);
  });

  it("totals base plus speed times the multiplier", () => {
    const r = scoreRound(1, 1, 0, 10_000, 5);
    expect(r).toMatchObject({ base: 100, speed: 25, combo: 6, multiplier: 2, total: 250 });
  });
});

describe("progression", () => {
  it("levels up on the xp curve", () => {
    expect(levelFromXp(0)).toEqual({ level: 1, into: 0, needed: 100 });
    expect(levelFromXp(100).level).toBe(2);
    expect(levelFromXp(100 + xpToNext(2) + 5)).toEqual({ level: 3, into: 5, needed: xpToNext(3) });
  });

  it("promotes rank every five levels and caps at the top", () => {
    expect(rankFor(1)).toBe("Sunday League Scout");
    expect(rankFor(6)).toBe("Academy Scout");
    expect(rankFor(999)).toBe("Legendary Scout");
  });
});

describe("career", () => {
  it("gives stars on base points, none for a lost match", () => {
    expect(matchStars(90, true)).toBe(3);
    expect(matchStars(72, true)).toBe(2);
    expect(matchStars(40, true)).toBe(1);
    expect(matchStars(100, false)).toBe(0);
  });

  it("unlocks levels in order and worlds after their final", () => {
    const sizes = [3, 2];
    expect(isUnlocked({}, sizes, 0, 0)).toBe(true);
    expect(isUnlocked({}, sizes, 0, 1)).toBe(false);
    expect(isUnlocked({ "0-0": 1 }, sizes, 0, 1)).toBe(true);
    expect(isUnlocked({ "0-0": 3, "0-1": 3 }, sizes, 1, 0)).toBe(false);
    expect(isUnlocked({ "0-2": 1 }, sizes, 1, 0)).toBe(true);
  });

  it("scales the boss and rates puzzle spots", () => {
    expect(bossHp(10)).toBe(800);
    expect(puzzleStars(0.5, 0.5)).toBe(3);
    expect(puzzleStars(0.41, 0.5)).toBe(2);
    expect(puzzleStars(0.1, 0.5)).toBe(0);
  });
});

describe("adaptive", () => {
  it("weights weak and unseen concepts higher", () => {
    const p = {};
    updateProgress(p, ["Header"], 0);
    updateProgress(p, ["Long range"], 100);
    const w = conceptWeights(p, ["Header", "Long range", "Tight angle"]);
    expect(w["Header"]).toBeGreaterThan(w["Long range"]);
    expect(w["Tight angle"]).toBe(1.5);
  });

  it("never picks an excluded shot while others remain", () => {
    const rng = mulberry32(1);
    for (let i = 0; i < 50; i++) {
      expect(pickAdaptive([["a"], ["a"], ["a"]], { a: 1 }, rng, undefined, new Set([0, 2]))).toBe(1);
    }
  });

  it("softens big bands", () => {
    const w = bandBalance([0, 0, 0, 0, 4]);
    expect(w[4]).toBeGreaterThan(w[0]);
  });
});

describe("rng and daily", () => {
  it("is deterministic per day and balanced across bands", () => {
    const bands = Array.from({ length: 200 }, (_, i) => i % 5);
    const a = dailyPicks(bands, "2026-10-22");
    expect(dailyPicks(bands, "2026-10-22")).toEqual(a);
    expect(dailyPicks(bands, "2026-10-23")).not.toEqual(a);
    expect(a).toHaveLength(10);
    for (let b = 0; b < 5; b++) expect(a.filter((i) => bands[i] === b)).toHaveLength(2);
  });

  it("numbers days and spots consecutive ones", () => {
    expect(dailyNumber("2026-10-22")).toBe(1);
    expect(isNextDay("2026-10-31", "2026-11-01")).toBe(true);
    expect(isNextDay("2026-10-22", "2026-10-24")).toBe(false);
  });
});

describe("save", () => {
  it("survives missing, corrupt and older saves", () => {
    expect(loadSave(null)).toEqual(defaultSave());
    const bad = { getItem: () => "{nope", setItem: () => {} };
    expect(loadSave(bad)).toEqual(defaultSave());
    const old = { getItem: (k: string) => (k === SAVE_KEY ? JSON.stringify({ xp: 50, coins: "lots" }) : null), setItem: () => {} };
    const s = loadSave(old);
    expect(s.xp).toBe(50);
    expect(s.coins).toBe(0);
    expect(s.stats.bandExact).toHaveLength(5);
  });

  it("keeps free-form maps and nullable fields", () => {
    const merged = mergeSave(defaultSave(), { career: { "0-0": 2 }, stats: { fastestExactMs: 1500 } });
    expect(merged.career).toEqual({ "0-0": 2 });
    expect(merged.stats.fastestExactMs).toBe(1500);
  });
});

describe("recording and achievements", () => {
  it("records a read and unlocks first-read once", () => {
    const save = defaultSave();
    recordRead(save, ["Header"], 4, scoreRound(4, 4, 1500, 10_000, 0), 1500);
    expect(save.stats.exact).toBe(1);
    expect(save.stats.conceptExact["Header"]).toBe(1);
    const fresh = unlockNew(save).map((a) => a.id);
    expect(fresh).toContain("first_read");
    expect(fresh).toContain("speed_demon");
    expect(save.coins).toBeGreaterThanOrEqual(ACHIEVEMENT_COINS * 2);
    expect(unlockNew(save)).toHaveLength(0);
  });

  it("only raises stars and pays a trophy once", () => {
    const save = defaultSave();
    recordMatch(save, 0, 6, 2, false, "World Cup 2018");
    const coins = save.coins;
    recordMatch(save, 0, 6, 1, false, "World Cup 2018");
    expect(save.career["0-6"]).toBe(2);
    expect(save.coins).toBe(coins);
    expect(save.trophies).toEqual(["World Cup 2018"]);
  });

  it("counts the daily once and builds a streak", () => {
    const save = defaultSave();
    expect(recordDaily(save, "2026-10-22", 500)).toBe(true);
    expect(recordDaily(save, "2026-10-22", 900)).toBe(false);
    recordDaily(save, "2026-10-23", 400);
    recordDaily(save, "2026-10-24", 400);
    expect(save.daily.streak).toBe(3);
    recordDaily(save, "2026-10-27", 400);
    expect(save.daily.streak).toBe(1);
    expect(save.daily.bestStreak).toBe(3);
  });

  it("has unique achievement ids", () => {
    expect(new Set(ACHIEVEMENTS.map((a) => a.id)).size).toBe(ACHIEVEMENTS.length);
  });

  it("buys and equips only what you can afford", () => {
    const save = defaultSave();
    const night = PITCHES.find((i) => i.id === "pitch.night")!;
    expect(buy(save, night)).toBe("poor");
    expect(equip(save, night)).toBe(false);
    save.coins = 1000;
    expect(buy(save, night)).toBe("bought");
    expect(equip(save, night)).toBe(true);
    expect(save.equipped.pitch).toBe("pitch.night");
    expect(buy(save, night)).toBe("owned");
  });
});
