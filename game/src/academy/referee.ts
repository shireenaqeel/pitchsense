// Referee's Eye: drawn match situations where the player makes the referee's
// call. Pure data like the curriculum, drawn with the same Diagram, and each
// call points back at the Academy lesson that teaches it.

import { away, ball, home, keeper, pass, ref, run, shot, type Mark, type View } from "./curriculum";

export interface RefCall {
  id: string;
  view: View;
  /** What happens, read before the call. */
  situation: string;
  marks: Mark[];
  q: string;
  options: string[];
  answer: number;
  why: string;
  /** The Academy lesson behind the call. */
  lesson: string;
}

const LINE = (x: number): Mark => ({ kind: "line", x, label: "Offside line" });
const BOX: Mark = { kind: "zone", x: [102, 120], y: [18, 62], tone: "danger" };
/** A flat back four across the pitch at depth x, plus their keeper. */
const BACK_FOUR = (x: number): Mark[] => [away(x, 22), away(x, 34), away(x, 46), away(x, 58), keeper()];

const ONSIDE_OFFSIDE = ["Onside: play on", "Offside: free kick to the defenders"];

export const REF_CALLS: RefCall[] = [
  {
    id: "level",
    view: "half",
    situation: "As the pass is played, the striker is exactly level with the last outfield defender. They run through and score.",
    marks: [...BACK_FOUR(100), LINE(100), home(84, 40, "Passer"), home(100, 50, "Striker"),
      pass([85, 40], [110, 46]), run([100, 50], [109, 46])],
    q: "Your call?",
    options: ONSIDE_OFFSIDE,
    answer: 0,
    why: "Level with the second-to-last defender counts as onside, and that's what matters at the moment of the pass.",
    lesson: "offside",
  },
  {
    id: "beyond",
    view: "half",
    situation: "As the pass is played, the striker is already two yards past the last outfield defender, and runs on to it.",
    marks: [...BACK_FOUR(100), LINE(100), home(84, 40, "Passer"), home(103, 50, "Striker"),
      pass([85, 40], [110, 47]), run([103, 50], [109, 47])],
    q: "Your call?",
    options: ONSIDE_OFFSIDE,
    answer: 1,
    why: "Past the second-to-last defender and past the ball when the pass is played, and then playing it: that's offside.",
    lesson: "offside",
  },
  {
    id: "own-half",
    view: "full",
    situation: "When the pass is played the striker is still in their own half, and every defender is in the other half. The striker sprints clear.",
    marks: [away(64, 24), away(63, 40), away(64, 56), keeper(), home(45, 30, "Passer"), home(57, 46, "Striker"),
      { kind: "line", x: 60, label: "Halfway line" }, pass([46, 30], [82, 44]), run([57, 46], [81, 44])],
    q: "Your call?",
    options: ONSIDE_OFFSIDE,
    answer: 0,
    why: "You can't be offside in your own half, however far ahead of you the defenders are.",
    lesson: "offside",
  },
  {
    id: "throw-in",
    view: "half",
    situation: "A throw-in goes straight to a striker who is standing past the last defender.",
    marks: [away(104, 22), away(103, 34), away(104, 46), away(103, 58), keeper(), LINE(103),
      home(98, 1, "Throw-in"), home(110, 12, "Striker"), pass([98.5, 1.5], [109.5, 11.5])],
    q: "Your call?",
    options: ONSIDE_OFFSIDE,
    answer: 0,
    why: "There's no offside straight from a throw-in, a corner or a goal kick.",
    lesson: "offside",
  },
  {
    id: "not-involved",
    view: "half",
    situation: "One attacker is standing offside on the far side but never moves towards the ball. The striker, who was onside, scores.",
    marks: [...BACK_FOUR(100), LINE(100), home(108, 14, "Not involved"), home(85, 46, "Passer"), home(99, 46, "Striker"),
      pass([86, 46], [109, 44]), run([99, 46], [108, 44]), shot([108, 44], [120.5, 41])],
    q: "Does the goal stand?",
    options: ["Yes, the goal stands", "No, it's offside"],
    answer: 0,
    why: "Being in an offside position isn't an offence until the player gets involved. This one never touched the ball, blocked the keeper or challenged anyone.",
    lesson: "offside",
  },
  {
    id: "cutback",
    view: "half",
    situation: "The winger pulls the ball back from the byline. The striker is past the defenders, but behind the ball.",
    marks: [away(104, 30), away(105, 42), away(106, 54), keeper(), home(116, 62, "Winger"), ball(116.6, 61.4),
      home(108, 40, "Striker"), pass([116.6, 61.4], [108.6, 41])],
    q: "Your call?",
    options: ONSIDE_OFFSIDE,
    answer: 0,
    why: "A player level with or behind the ball can't be offside. A pass backwards from the byline is safe.",
    lesson: "offside",
  },
  {
    id: "penalty",
    view: "half",
    situation: "Inside the box, the defender clips the attacker's heels and they go down.",
    marks: [BOX, home(110, 32, "Tripped"), away(110.6, 34.5), keeper()],
    q: "What do you give?",
    options: ["A penalty", "A free kick on the edge of the box", "A corner"],
    answer: 0,
    why: "A foul by a defender inside their own penalty area is a penalty, wherever in the box it happens.",
    lesson: "fouls",
  },
  {
    id: "edge",
    view: "half",
    situation: "The defender trips the attacker a yard outside the penalty area.",
    marks: [BOX, home(99, 44, "Tripped"), away(99.4, 46.5), keeper(), { kind: "ring", at: [99, 44] }],
    q: "What do you give?",
    options: ["A penalty", "A direct free kick", "An indirect free kick"],
    answer: 1,
    why: "Outside the box, a trip is a direct free kick. The lines belong to the box, so only a foul on or inside the line is a penalty.",
    lesson: "fouls",
  },
  {
    id: "advantage",
    view: "half",
    situation: "The attacker is fouled, but the ball runs on to a teammate who is clear on goal.",
    marks: [home(84, 30, "Fouled"), away(84.5, 32.5), pass([85, 30], [98, 46]), home(98, 46, "Clear"),
      away(104, 28), away(103, 54), keeper(), ref(90, 40)],
    q: "What do you do?",
    options: ["Stop play: free kick", "Play advantage, and book the defender later if needed"],
    answer: 1,
    why: "Stopping play would help the team that fouled. Play advantage, and the card can still come at the next stoppage.",
    lesson: "advantage",
  },
  {
    id: "back-pass",
    view: "half",
    situation: "A defender deliberately passes back to their keeper with their foot, and the keeper picks it up.",
    marks: [away(100, 40, "Defender"), pass([100, 40], [115, 40], "Back-pass"), keeper(116, 40)],
    q: "What do you give?",
    options: ["Nothing: play on", "An indirect free kick to the attackers", "A penalty"],
    answer: 1,
    why: "A keeper may not handle a deliberate kick from a teammate. It's an indirect free kick where it happened.",
    lesson: "freekicks",
  },
  {
    id: "corner",
    view: "half",
    situation: "A defender's clearance hits their own teammate and goes over their own goal line, wide of the post.",
    marks: [away(110, 56), away(113, 60), pass([110, 56], [120, 66]), keeper()],
    q: "What's the restart?",
    options: ["A goal kick", "A corner"],
    answer: 1,
    why: "A defender touched it last before it crossed their goal line, so the attackers get a corner.",
    lesson: "restarts",
  },
  {
    id: "goal-kick",
    view: "half",
    situation: "The striker's shot flies wide of the post and over the goal line.",
    marks: [home(104, 30, "Striker"), shot([104, 30], [120.5, 33]), keeper()],
    q: "What's the restart?",
    options: ["A goal kick", "A corner"],
    answer: 0,
    why: "An attacker touched it last before it crossed the goal line, so the defenders restart with a goal kick.",
    lesson: "restarts",
  },
  {
    id: "eight-seconds",
    view: "half",
    situation: "The keeper catches a cross and holds on to the ball. The referee's hand counts down from five and gets to zero, past eight seconds.",
    marks: [keeper(116, 38), ref(104, 52, "Counting"), { kind: "board", at: [108, 62], lines: ["8 SECONDS"], tone: "gold" }],
    q: "What do you give?",
    options: ["An indirect free kick", "A corner to the other team", "Nothing: keepers can hold it"],
    answer: 1,
    why: "Since 2025, a keeper who holds the ball for more than eight seconds gives away a corner.",
    lesson: "freekicks",
  },
  {
    id: "arm-up",
    view: "half",
    situation: "Inside the box, a defender jumps with both arms raised above their head, and the cross hits an arm.",
    marks: [BOX, away(110, 42, "Arms up"), home(111, 46), home(104, 76, "Cross"), pass([104.5, 75.5], [110, 42.5])],
    q: "What do you give?",
    options: ["A penalty", "Play on: it was an accident"],
    answer: 0,
    why: "Arms above the head make the body unnaturally bigger, so it's handball even if the defender didn't mean it. Inside the box, that's a penalty.",
    lesson: "aim",
  },
  {
    id: "arm-tucked",
    view: "half",
    situation: "A shot from two yards away hits the defender's arm, which is tucked in against their side.",
    marks: [BOX, home(108, 40, "Shooter"), away(110, 40, "Arm tucked in"), shot([108, 40], [109.8, 40]), keeper()],
    q: "What do you give?",
    options: ["A penalty", "Play on"],
    answer: 1,
    why: "The arm wasn't making the body bigger, and there was no time to move it. That's not handball.",
    lesson: "aim",
  },
  {
    id: "dogso",
    view: "half",
    situation: "The attacker is clean through on goal outside the box, and the last defender drags them down from behind.",
    marks: [home(96, 40, "Through"), away(95, 41.5, "Last defender"), keeper(), run([90, 40], [96, 40])],
    q: "Which card?",
    options: ["A yellow card", "A red card", "No card, just the free kick"],
    answer: 1,
    why: "Fouling to stop an obvious goal-scoring chance outside the box is a sending-off.",
    lesson: "fouls",
  },
  {
    id: "shirt-off",
    view: "half",
    situation: "A player scores and pulls their shirt off over their head to celebrate.",
    marks: [home(110, 40, "Scorer"), ball(120.4, 38), keeper(119, 44)],
    q: "Which card?",
    options: ["No card", "A yellow card", "A red card"],
    answer: 1,
    why: "Taking the shirt off to celebrate is a caution, even after a great goal. The goal still counts.",
    lesson: "fouls",
  },
  {
    id: "var-toe",
    view: "box",
    situation: "A goal is scored. VAR checks and finds the scorer's toe was past the last defender when the pass was played.",
    marks: [{ kind: "line", x: 106, label: "Offside line" }, away(106, 36), home(106.7, 28, "A toe off"), keeper()],
    q: "What happens?",
    options: ["The goal stands: it's too close to call", "The goal is ruled out for offside"],
    answer: 1,
    why: "Offside is a matter of fact, not judgement, so VAR measures it. A toe past the line is offside.",
    lesson: "var",
  },
];

/** A round's worth of calls: `n` different ones, picked with `rand`. */
export function pickCalls(rand: () => number, n = 8): RefCall[] {
  const pool = [...REF_CALLS];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, n);
}
