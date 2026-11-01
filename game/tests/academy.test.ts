import { describe, expect, it } from "vitest";

import { CONCEPT_NOTES, CURRICULUM, LESSONS, lessonById, type Mark, type Pt, REASON_LESSONS } from "../src/academy/curriculum";
import { ACHIEVEMENTS, unlockNew } from "../src/systems/achievements";
import { academyComplete, completeLesson, LESSON_COINS, LESSON_XP, lessonsDone, moduleProgress, nextLesson } from "../src/systems/academy";
import { defaultSave, mergeSave } from "../src/systems/save";

// The concept tags written by `python -m pitchsense.export_game` (meta.json).
const GAME_CONCEPTS = ["Close range", "Long range", "Tight angle", "Header", "One-on-one", "Under pressure",
  "Crowded box", "From cross", "Through ball", "Standard chance"];

function points(m: Mark): Pt[] {
  if (m.kind === "arrow") return [m.from, m.to];
  if (m.kind === "cone") return [m.from];
  if (m.kind === "zone") return [[m.x[0], m.y[0]], [m.x[1], m.y[1]]];
  if (m.kind === "line") return [[m.x, 40]];
  return [m.at];
}

describe("curriculum", () => {
  it("has unique lesson ids and at least one step each", () => {
    expect(new Set(LESSONS.map((l) => l.id)).size).toBe(LESSONS.length);
    for (const l of LESSONS) expect(l.steps.length).toBeGreaterThan(0);
  });

  it("has a valid answer for every quiz", () => {
    for (const l of LESSONS) {
      expect(l.quiz.options.length, l.id).toBeGreaterThanOrEqual(2);
      expect(l.quiz.options.length, l.id).toBeLessThanOrEqual(4);
      expect(l.quiz.answer, l.id).toBeGreaterThanOrEqual(0);
      expect(l.quiz.answer, l.id).toBeLessThan(l.quiz.options.length);
    }
  });

  it("links only to https pages", () => {
    for (const l of LESSONS) for (const link of l.links) expect(link.url, l.id).toMatch(/^https:\/\//);
  });

  it("draws every mark on the pitch", () => {
    for (const l of LESSONS) {
      for (const m of l.steps.flatMap((s) => s.marks ?? [])) {
        for (const [x, y] of points(m)) {
          // Shots may finish a yard beyond the goal line.
          expect(x, `${l.id} ${m.kind}`).toBeGreaterThanOrEqual(0);
          expect(x, `${l.id} ${m.kind}`).toBeLessThanOrEqual(121);
          expect(y, `${l.id} ${m.kind}`).toBeGreaterThanOrEqual(0);
          expect(y, `${l.id} ${m.kind}`).toBeLessThanOrEqual(80);
        }
        if (m.kind === "spot") expect([0, 1, 2, 3, 4]).toContain(m.band);
      }
    }
  });

  it("keeps the zoomed views' marks inside what they show", () => {
    const xMin = { half: 60, box: 84, full: 0 };
    for (const l of LESSONS) {
      for (const m of l.steps.flatMap((s) => s.marks ?? [])) {
        for (const [x] of points(m)) expect(x, `${l.id} ${m.kind}`).toBeGreaterThanOrEqual(xMin[l.view]);
      }
    }
  });

  it("keeps every step short enough for the lesson panel", () => {
    for (const l of LESSONS) for (const st of l.steps) expect(st.text.length, l.id).toBeLessThanOrEqual(400);
  });

  it("gives every board at least one line, and a real line to highlight", () => {
    for (const l of LESSONS) {
      for (const m of l.steps.flatMap((s) => s.marks ?? [])) {
        if (m.kind !== "board") continue;
        expect(m.lines.length, l.id).toBeGreaterThan(0);
        expect(m.hl ?? 0, l.id).toBeLessThan(m.lines.length);
      }
    }
  });

  it("explains every concept the game tags, with a real lesson", () => {
    for (const c of GAME_CONCEPTS) {
      expect(CONCEPT_NOTES[c], c).toBeDefined();
      expect(lessonById(CONCEPT_NOTES[c].lesson), c).toBeDefined();
    }
  });
});

describe("reason lessons", () => {
  it("points every model reason at a real lesson", () => {
    // The reason names written by `explain.reasons`.
    for (const r of ["Goalkeeper", "Angle", "Bodies in the way", "Space to shoot", "Distance", "Header", "The final ball",
      "First time", "Pressure", "One-on-one"]) {
      expect(lessonById(REASON_LESSONS[r]), r).toBeDefined();
    }
  });
});

describe("academy progress", () => {
  it("pays for a lesson once", () => {
    const save = defaultSave();
    expect(completeLesson(save, "aim")).toBe(true);
    expect(save.xp).toBe(LESSON_XP);
    expect(save.coins).toBe(LESSON_COINS);
    expect(completeLesson(save, "aim")).toBe(false);
    expect(save.xp).toBe(LESSON_XP);
    expect(completeLesson(save, "no-such-lesson")).toBe(false);
  });

  it("walks the course in order", () => {
    const save = defaultSave();
    expect(nextLesson(save)?.id).toBe(LESSONS[0].id);
    completeLesson(save, LESSONS[0].id);
    expect(nextLesson(save)?.id).toBe(LESSONS[1].id);
    const first = CURRICULUM[0];
    expect(moduleProgress(save, first.id)).toEqual({ done: 1, total: first.lessons.length });
  });

  it("unlocks Back to School and Football Literate", () => {
    const save = defaultSave();
    completeLesson(save, LESSONS[0].id);
    expect(unlockNew(save).map((a) => a.id)).toContain("first_lesson");
    for (const l of LESSONS) completeLesson(save, l.id);
    expect(academyComplete(save)).toBe(true);
    expect(nextLesson(save)).toBeUndefined();
    expect(unlockNew(save).map((a) => a.id)).toContain("literate");
    expect(ACHIEVEMENTS.some((a) => a.id === "literate")).toBe(true);
  });

  it("loads an old save without the academy field", () => {
    const old = { ...defaultSave() } as Record<string, unknown>;
    delete old.academy;
    expect(mergeSave(defaultSave(), old).academy).toEqual([]);
  });
});

describe("lesson count", () => {
  it("ignores lessons a save remembers but the course no longer has", () => {
    const save = defaultSave();
    save.academy = [LESSONS[0].id, "a-lesson-that-was-removed"];
    expect(lessonsDone(save)).toBe(1);
    expect(academyComplete(save)).toBe(false);
  });
});
