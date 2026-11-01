// Academy progress: which lessons are done, what to do next, and the reward
// for finishing a lesson the first time.

import { CURRICULUM, LESSONS, type Lesson } from "../academy/curriculum";
import type { SaveData } from "./save";

export const LESSON_XP = 60;
export const LESSON_COINS = 25;

export function lessonDone(save: SaveData, id: string): boolean {
  return save.academy.includes(id);
}

/** Mark a lesson done; the first time pays XP and coins. Returns whether it was new. */
export function completeLesson(save: SaveData, id: string): boolean {
  if (lessonDone(save, id) || !LESSONS.some((l) => l.id === id)) return false;
  save.academy.push(id);
  save.xp += LESSON_XP;
  save.coins += LESSON_COINS;
  return true;
}

/** The first unfinished lesson in course order, if any. */
export function nextLesson(save: SaveData): Lesson | undefined {
  return LESSONS.find((l) => !lessonDone(save, l.id));
}

export function moduleProgress(save: SaveData, moduleId: string): { done: number; total: number } {
  const lessons = CURRICULUM.find((m) => m.id === moduleId)?.lessons ?? [];
  return { done: lessons.filter((l) => lessonDone(save, l.id)).length, total: lessons.length };
}

/** Lessons finished, counting only ones still in the course (a save can outlive a lesson). */
export function lessonsDone(save: SaveData): number {
  return LESSONS.filter((l) => lessonDone(save, l.id)).length;
}

export function academyComplete(save: SaveData): boolean {
  return lessonsDone(save) === LESSONS.length;
}
