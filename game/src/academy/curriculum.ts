// The Academy: football from zero, then how to read a chance. Pure data, no
// Phaser, so it can be checked by the tests.
//
// Every diagram is drawn in StatsBomb yards on the same pitch as the game:
// 120 x 80, the blue team attacking the goal at x = 120 (the top of the
// screen), y running across from the left touchline (0) to the right (80).

import type { IconName } from "../ui/icons";

/** A point in StatsBomb yards: [x along the pitch, y across it]. */
export type Pt = [number, number];

export type View = "full" | "half" | "box";

export type Tone = "accent" | "gold" | "danger" | "info";

export type Mark =
  /** Blue attacks up the screen; red defends the top goal; keeper is red's keeper. */
  | { kind: "player"; at: Pt; side: "home" | "away" | "keeper"; label?: string }
  | { kind: "ball"; at: Pt }
  /** A pass (solid), a run without the ball (dashed) or a shot (thick). */
  | { kind: "arrow"; from: Pt; to: Pt; style: "pass" | "run" | "shot"; label?: string }
  | { kind: "zone"; x: [number, number]; y: [number, number]; tone?: Tone; label?: string }
  /** A dashed line straight across the pitch at depth x. */
  | { kind: "line"; x: number; label?: string }
  /** The shooting cone: from the ball to both posts. */
  | { kind: "cone"; from: Pt }
  /** A pulsing ring that points at a spot. */
  | { kind: "ring"; at: Pt; label?: string }
  /** A dot in a chance band's colour. */
  | { kind: "spot"; at: Pt; band: number; label?: string };

export interface Step {
  text: string;
  marks?: Mark[];
  /** Wipe the diagram before drawing this step's marks. */
  clear?: boolean;
}

export interface Quiz {
  q: string;
  options: string[];
  answer: number;
  why: string;
}

export interface Link {
  label: string;
  url: string;
}

export interface Lesson {
  id: string;
  title: string;
  view: View;
  steps: Step[];
  quiz: Quiz;
  takeaway: string;
  links: Link[];
}

export interface Module {
  id: string;
  title: string;
  blurb: string;
  icon: IconName;
  lessons: Lesson[];
}

const IFAB = (law: string, slug: string): Link => ({ label: `Laws of the Game: ${law}`, url: `https://www.theifab.com/laws/latest/${slug}/` });
const WIKI = (label: string, page: string): Link => ({ label: `Wikipedia: ${label}`, url: `https://en.wikipedia.org/wiki/${page}` });
const STATSBOMB_XG: Link = { label: "StatsBomb: xG explained", url: "https://statsbomb.com/soccer-metrics/expected-goals-xg-explained/" };

const home = (x: number, y: number, label?: string): Mark => ({ kind: "player", at: [x, y], side: "home", label });
const away = (x: number, y: number, label?: string): Mark => ({ kind: "player", at: [x, y], side: "away", label });
const keeper = (x = 119, y = 40): Mark => ({ kind: "player", at: [x, y], side: "keeper" });
const ball = (x: number, y: number): Mark => ({ kind: "ball", at: [x, y] });
const pass = (from: Pt, to: Pt, label?: string): Mark => ({ kind: "arrow", from, to, style: "pass", label });
const run = (from: Pt, to: Pt, label?: string): Mark => ({ kind: "arrow", from, to, style: "run", label });
const shot = (from: Pt, to: Pt, label?: string): Mark => ({ kind: "arrow", from, to, style: "shot", label });

/** Both teams lined up in their own halves for kick-off. */
const KICK_OFF: Mark[] = [
  { kind: "player", at: [2, 40], side: "home" },
  home(20, 12), home(18, 30), home(18, 50), home(20, 68),
  home(40, 12), home(38, 30), home(38, 50), home(40, 68),
  home(57, 36), home(56, 50),
  keeper(118, 40),
  away(100, 12), away(102, 30), away(102, 50), away(100, 68),
  away(80, 12), away(82, 30), away(82, 50), away(80, 68),
  away(68, 32), away(66, 48),
  ball(60, 40),
];

/** A 4-3-3 with each position named. */
const FOUR_THREE_THREE: Mark[] = [
  home(2, 40, "GK"),
  home(22, 12, "LB"), home(19, 31, "CB"), home(19, 49, "CB"), home(22, 68, "RB"),
  home(42, 24, "CM"), home(35, 40, "DM"), home(42, 56, "CM"),
  home(70, 13, "LW"), home(76, 40, "ST"), home(70, 67, "RW"),
];

const BOX: Mark = { kind: "zone", x: [102, 120], y: [18, 62], tone: "danger", label: "Penalty area" };

/** A corner from the right: the taker, the box, both sets of players. */
const CORNER: Mark[] = [
  home(119.3, 79, "Corner"), ball(119.6, 79.4),
  home(110, 44), home(108, 38), home(112, 34),
  away(113, 42), away(111, 37), away(114, 47),
  keeper(119, 41),
];

export const CURRICULUM: Module[] = [
  {
    id: "basics",
    title: "The Basics",
    blurb: "The pitch, the rules, and how a match works.",
    icon: "ball",
    lessons: [
      {
        id: "aim",
        title: "The aim of the game",
        view: "full",
        steps: [
          {
            text: "Football is two teams of eleven, each trying to put the ball in the other team's goal.\n\nIn every diagram here your team is blue, attacking the goal at the top. Red defends it.",
            marks: KICK_OFF,
          },
          {
            text: "A goal counts when the whole ball crosses the goal line, between the posts and under the crossbar.\n\nWhoever scores more goals wins. If the score is level at the end, it's a draw.",
            clear: true,
            marks: [home(107, 38, "Shooter"), keeper(119, 42), ball(108, 38), shot([108, 38], [121, 37.5], "Goal!")],
          },
          {
            text: "Only the goalkeeper may handle the ball, and only inside their own penalty area.\n\nEveryone else plays with feet, head and body. Handball is a foul when a player handles on purpose, or makes their body unnaturally bigger with an arm. A ball that just hits an arm by accident usually isn't.",
            clear: true,
            marks: [{ kind: "zone", x: [102, 120], y: [18, 62], tone: "info", label: "Keeper may use hands" }, keeper(118, 40)],
          },
        ],
        quiz: {
          q: "When is a goal scored?",
          options: ["When the ball touches the goal line", "When the whole ball crosses the line between the posts", "When the ball hits the crossbar"],
          answer: 1,
          why: "All of the ball has to be over the line. If any part of it is still on the line, play goes on.",
        },
        takeaway: "Two teams of eleven. Get the whole ball over the line and into the goal.",
        links: [IFAB("The players", "the-players"), WIKI("Association football", "Association_football")],
      },
      {
        id: "pitch",
        title: "Know the pitch",
        view: "full",
        steps: [
          {
            text: "The halfway line splits the pitch in two. Every match, and every restart after a goal, kicks off from the spot in the middle of the centre circle.",
            marks: [{ kind: "line", x: 60, label: "Halfway line" }, { kind: "ring", at: [60, 40], label: "Centre spot" }],
          },
          {
            text: "The big rectangle at each end is the penalty area, usually just called 'the box'. It's 18 yards deep.\n\nIf a defender fouls an attacker inside it, the attackers get a penalty.",
            clear: true,
            marks: [BOX],
          },
          {
            text: "Inside it is the six-yard box. Most goals are scored somewhere between here and the penalty spot.",
            marks: [{ kind: "zone", x: [114, 120], y: [30, 50], tone: "gold", label: "Six-yard box" }],
          },
          {
            text: "The penalty spot is 12 yards from the goal. The arc on the edge of the box (the 'D') keeps everyone 10 yards back while a penalty is taken.",
            marks: [{ kind: "ring", at: [108, 40], label: "Penalty spot" }],
          },
          {
            text: "Real pitches are roughly 105 × 68 metres. The data in this game, from StatsBomb, measures every pitch as 120 × 80 yards, so that's the scale for every distance you'll see.",
          },
        ],
        quiz: {
          q: "How far is the penalty spot from the goal line?",
          options: ["6 yards", "12 yards", "18 yards"],
          answer: 1,
          why: "6 yards is the edge of the six-yard box, and 18 yards is the edge of the penalty area.",
        },
        takeaway: "The box is 18 yards deep, the six-yard box 6, and the penalty spot sits 12 yards out.",
        links: [IFAB("The field of play", "the-field-of-play"), WIKI("Football pitch", "Football_pitch")],
      },
      {
        id: "match",
        title: "How a match works",
        view: "full",
        steps: [
          {
            text: "A match is two halves of 45 minutes. At the end of each half the referee adds stoppage time to make up for injuries, substitutions and goal celebrations.",
            marks: KICK_OFF,
          },
          {
            text: "In a league, or a tournament's group stage, a draw is fine: a win is worth 3 points and a draw 1.\n\nAt the World Cup, each team plays three group games, and the best go through to the knockouts. Since 2026 there are 48 teams, so there's an extra knockout round, the round of 32.",
          },
          {
            text: "Knockout games need a winner. Level after 90 minutes usually means 30 minutes of extra time, then a penalty shoot-out. (Recent Copa Américas went straight to penalties before the final.)",
            clear: true,
            marks: [{ kind: "ring", at: [108, 40], label: "Shoot-out" }, keeper(119.5, 40)],
          },
          {
            text: "World Tour follows that road exactly: three group games, then the round of 16, quarter-final, semi-final and final.\n\nThe shots are real, from six tournaments: two World Cups, two Euros, the Copa América and the Africa Cup of Nations.",
          },
        ],
        quiz: {
          q: "A World Cup knockout game is 1–1 after 90 minutes. What happens?",
          options: ["It's a draw and both teams go through", "Extra time, then penalties if it's still level", "A replay a few days later"],
          answer: 1,
          why: "A knockout needs a winner: 30 minutes of extra time first, then a penalty shoot-out if it's still level.",
        },
        takeaway: "Two halves of 45. Groups allow draws; knockouts go to extra time and penalties.",
        links: [
          IFAB("Duration of the match", "the-duration-of-the-match"),
          WIKI("Penalty shoot-out", "Penalty_shoot-out_(association_football)"),
          WIKI("FIFA World Cup", "FIFA_World_Cup"),
          WIKI("Africa Cup of Nations", "Africa_Cup_of_Nations"),
        ],
      },
      {
        id: "restarts",
        title: "When the ball goes out",
        view: "half",
        steps: [
          {
            text: "When the whole ball crosses a touchline (the long sides), the team that didn't touch it last takes a throw-in: both hands, from behind the head.",
            marks: [home(90, 1.2, "Throw-in"), ball(90.6, 0.8), pass([90, 1.5], [97, 12]), home(97, 13)],
          },
          {
            text: "Over the goal line, it depends who touched it last.\n\nIf an attacker did, the defending team restarts with a goal kick from anywhere in their six-yard box. The ball is live as soon as it's kicked, so many teams just pass it short to a defender.",
            clear: true,
            marks: [keeper(115, 34), ball(115.5, 33.4), pass([115, 34], [86, 16], "Goal kick")],
          },
          {
            text: "If a defender touched it last, the attackers get a corner, taken from the corner nearest where the ball went out.\n\nCorners are a chance to whip the ball into a crowded box.",
            clear: true,
            marks: [...CORNER, pass([119, 78], [111, 41])],
          },
        ],
        quiz: {
          q: "A defender is the last to touch the ball before it goes over their own goal line, wide of the goal. What's the restart?",
          options: ["Goal kick", "Corner kick", "Throw-in"],
          answer: 1,
          why: "Last touch by the defenders over their own goal line gives the attackers a corner. Last touch by an attacker gives a goal kick.",
        },
        takeaway: "Out of the side: throw-in. Out of the end: goal kick or corner, depending on who touched it last.",
        links: [IFAB("The throw-in", "the-throw-in"), IFAB("The corner kick", "the-corner-kick"),
          WIKI("Glossary of football terms", "Glossary_of_association_football_terms")],
      },
      {
        id: "fouls",
        title: "Fouls, free kicks and penalties",
        view: "half",
        steps: [
          {
            text: "Tripping, pushing, holding or kicking an opponent is a foul. The other team gets a free kick from where it happened, and opponents must stand 10 yards (9.15 m) away.",
            marks: [home(95, 37, "Free kick"), ball(96, 38), away(105, 35), away(105, 37), away(105, 39), away(105, 41), keeper(119, 41)],
          },
          {
            text: "Free kicks near the box are dangerous: the taker can shoot straight at goal. That's why defenders line up in a 'wall' across the most direct route.",
            marks: [shot([96, 38], [120.5, 43.2], "Over the wall")],
          },
          {
            text: "If a defender fouls an attacker inside their own penalty area, it's a penalty: a free shot from 12 yards with only the keeper to beat. About three in every four are scored.",
            clear: true,
            marks: [BOX, home(107, 40, "Penalty taker"), ball(108, 40), keeper(119.6, 40), shot([108, 40], [120.5, 37])],
          },
          {
            text: "The referee can also show cards. A yellow card is a caution. A second yellow, or a straight red for serious foul play, sends the player off, and their team plays on with one player fewer.",
          },
        ],
        quiz: {
          q: "A defender trips an attacker inside the defender's own penalty area. What's given?",
          options: ["A free kick on the edge of the box", "A penalty", "A corner"],
          answer: 1,
          why: "A foul by a defender inside their own penalty area is a penalty, wherever in the box it happens.",
        },
        takeaway: "Foul outside the box: free kick. Foul inside your own box: penalty.",
        links: [IFAB("Fouls and misconduct", "fouls-and-misconduct"), IFAB("Free kicks", "free-kicks"),
          IFAB("The penalty kick", "the-penalty-kick"), WIKI("Misconduct and cards", "Misconduct_(association_football)")],
      },
      {
        id: "offside",
        title: "Offside, made simple",
        view: "half",
        steps: [
          {
            text: "Offside stops attackers from just waiting next to the goal.\n\nIt's judged at the moment a teammate plays or touches the ball, not when the ball arrives.",
            marks: [home(86, 40, "Passer"), ball(87, 40), away(100, 24), away(101, 37), away(100, 50), away(99, 63), keeper(118, 40), home(98, 46, "Striker")],
          },
          {
            text: "Draw a line across the pitch at the second-to-last defender. That's usually the last outfield defender, because the keeper is normally the very last. This is the offside line.\n\nTo be offside you must be past this line and past the ball. Arms don't count, but feet, head and body do.",
            marks: [{ kind: "line", x: 101, label: "Offside line" }],
          },
          {
            text: "Here the striker is behind the line when the pass is played, so they're onside, free to run through on goal. Being exactly level with the line also counts as onside.",
            marks: [pass([87, 40], [109, 44]), run([98, 46], [108, 44])],
          },
          {
            text: "If the striker had already been past the line when the pass was played, they would be offside, and the defenders get a free kick.\n\nYou can't be offside in your own half, or straight from a throw-in, corner or goal kick.",
            clear: true,
            marks: [home(86, 40, "Passer"), ball(87, 40), away(100, 24), away(101, 37), away(100, 50), away(99, 63), keeper(118, 40),
              { kind: "line", x: 101, label: "Offside line" }, home(105, 30, "Offside!"), pass([87, 40], [106, 31])],
          },
          {
            text: "Standing in an offside position isn't an offence on its own. It only counts if that player gets involved: plays the ball, blocks the keeper's view, or challenges for it.\n\nThat's why the assistant referee sometimes waits before raising the flag, or never raises it at all.",
            clear: true,
            marks: [home(86, 40, "Passer"), ball(87, 40), away(100, 24), away(101, 37), away(100, 50), away(99, 63), keeper(118, 40),
              { kind: "line", x: 101, label: "Offside line" }, home(108, 14, "Not involved"), home(98, 44, "Onside"), pass([87, 40], [109, 42]), run([98, 44], [108, 42])],
          },
        ],
        quiz: {
          q: "When the pass is played, the striker is a yard behind the last outfield defender, and the keeper is on the goal line. Offside?",
          options: ["Yes, because they then run past the defender", "No, they were onside when the ball was played", "Only if they score"],
          answer: 1,
          why: "Offside is judged when the pass is played. Behind or level with the second-to-last defender at that moment is onside, even if the striker then runs past them.",
        },
        takeaway: "At the moment of the pass, be level with or behind the second-to-last defender.",
        links: [IFAB("Offside", "offside"), WIKI("Offside", "Offside_(association_football)")],
      },
    ],
  },
  {
    id: "team",
    title: "The Team",
    blurb: "Who plays where, and what they're there to do.",
    icon: "shirt",
    lessons: [
      {
        id: "positions",
        title: "Defenders, midfielders, forwards",
        view: "full",
        steps: [
          {
            text: "Every team has one goalkeeper (GK) and ten outfield players, usually arranged in three lines: defenders, midfielders and forwards.",
            marks: FOUR_THREE_THREE,
          },
          {
            text: "Defenders stop the other team scoring. Centre-backs (CB) guard the middle. Full-backs (LB, RB) defend the wings, and often run forward to cross too.",
            marks: [{ kind: "zone", x: [10, 29], y: [0, 80], tone: "info", label: "Defence" }],
          },
          {
            text: "Midfielders link defence to attack. A defensive midfielder (DM) shields the back line. Central midfielders (CM) pass, tackle and run box to box.",
            marks: [{ kind: "zone", x: [30, 50], y: [0, 80], tone: "accent", label: "Midfield" }],
          },
          {
            text: "Forwards create and score. Wingers (LW, RW) attack down the sides, and the striker (ST), or centre-forward, takes the most shots. In this game you'll mostly be reading strikers' chances.",
            marks: [{ kind: "zone", x: [62, 84], y: [0, 80], tone: "gold", label: "Attack" }],
          },
        ],
        quiz: {
          q: "Whose main job is to score goals?",
          options: ["The full-back", "The striker", "The defensive midfielder"],
          answer: 1,
          why: "Everyone can score, but the striker, or centre-forward, is there to take the chances.",
        },
        takeaway: "Keeper, then defence, midfield and attack, from back to front.",
        links: [WIKI("Positions", "Association_football_positions"), IFAB("The players", "the-players")],
      },
      {
        id: "keeper",
        title: "The goalkeeper",
        view: "box",
        steps: [
          {
            text: "The keeper is the last line of defence, and the only player allowed to use their hands, inside their own box.\n\nThe shaded triangle is the shooting cone: everywhere the ball can go and still end up in the goal.",
            marks: [home(104, 46, "Shooter"), ball(104.6, 45.6), { kind: "cone", from: [104.6, 45.6] }, keeper(119.5, 40)],
          },
          {
            text: "A keeper who steps out towards the shooter covers more of that cone. Same shooter, same goal, but much less of it to aim at.",
            clear: true,
            marks: [home(104, 46, "Shooter"), ball(104.6, 45.6), { kind: "cone", from: [104.6, 45.6] }, run([119.5, 40], [114.2, 42.2], "Steps out"), keeper(114, 42.3)],
          },
          {
            text: "That's why one-on-ones are rarely as easy as they look: the keeper rushes out and the goal shrinks.\n\nNear the byline, keepers hug the near post, so the angle is tiny.",
            clear: true,
            marks: [home(116.5, 58, "Tight angle"), ball(116.8, 57.4), { kind: "cone", from: [116.8, 57.4] }, keeper(119.3, 44.6)],
          },
        ],
        quiz: {
          q: "Why does a keeper rush out towards a striker?",
          options: ["To make the goal look smaller", "Because the rules say they must", "To get the ball back faster"],
          answer: 0,
          why: "Moving towards the shooter covers more of the shooting cone, so there's less goal to aim at.",
        },
        takeaway: "A keeper off their line shrinks the goal. Position is half of goalkeeping.",
        links: [WIKI("Goalkeeper", "Goalkeeper_(association_football)")],
      },
      {
        id: "formations",
        title: "Formations",
        view: "full",
        steps: [
          {
            text: "Formations are written from back to front, not counting the keeper. A 4-4-2 has four defenders, four midfielders and two strikers: solid and simple.",
            marks: [home(2, 40), home(22, 12), home(19, 31), home(19, 49), home(22, 68),
              home(42, 12), home(39, 31), home(39, 49), home(42, 68), home(66, 32), home(66, 48)],
          },
          {
            text: "A 4-3-3 has three midfielders and three forwards, with wingers high and wide to stretch the defence.",
            clear: true,
            marks: FOUR_THREE_THREE.map((m) => (m.kind === "player" ? { ...m, label: undefined } : m)),
          },
          {
            text: "A 3-5-2 uses three centre-backs, plus wing-backs who cover the whole flank, defending and attacking.\n\nTeams shift shape during a game, but the formation tells you where they want their players.",
            clear: true,
            marks: [home(2, 40), home(20, 22), home(18, 40), home(20, 58),
              home(46, 6), home(40, 27), home(35, 40), home(40, 53), home(46, 74), home(66, 32), home(66, 48)],
          },
        ],
        quiz: {
          q: "In a 4-3-3, how many defenders are there?",
          options: ["Three", "Four", "Five"],
          answer: 1,
          why: "The numbers go from the back: four defenders, three midfielders, three forwards. The keeper isn't counted.",
        },
        takeaway: "Read a formation from the back: defenders, midfielders, forwards.",
        links: [WIKI("Formations", "Formation_(association_football)")],
      },
    ],
  },
  {
    id: "attack",
    title: "Building Attacks",
    blurb: "How teams turn possession into chances.",
    icon: "curve",
    lessons: [
      {
        id: "passes",
        title: "Crosses, cutbacks and through balls",
        view: "half",
        steps: [
          {
            text: "Most goals come straight after one last pass, the assist. How the ball arrives decides how good the chance is.\n\nA cross is played from wide into the box, often in the air. It's hard to control, and it's usually met with a header while defenders jump too.",
            marks: [home(104, 73, "Winger"), ball(104.5, 72.5), pass([104.5, 72.5], [112, 42], "Cross"), home(112, 43), away(112.5, 40.5), away(110, 47), keeper(119, 41)],
          },
          {
            text: "A cutback is pulled back from near the byline, along the ground. The shooter faces the goal while the defenders are running back towards their own net. It's one of the best passes in football.",
            clear: true,
            marks: [home(117, 63, "Winger"), ball(117.3, 62.5), pass([117.3, 62.5], [108, 42], "Cutback"), run([99, 39], [107.5, 41.5]), home(99, 39),
              away(114, 43), away(115, 49), away(112, 53), keeper(119, 45)],
          },
          {
            text: "A through ball is played into the space behind the defence for a teammate to run onto. It often leaves the striker one-on-one with the keeper.",
            clear: true,
            marks: [home(80, 40, "Passer"), ball(81, 40), away(96, 22), away(97, 34), away(96, 46), away(95, 58), keeper(118, 40),
              home(93, 50, "Striker"), run([93, 50], [109, 45]), pass([81, 40], [110, 44], "Through ball")],
          },
        ],
        quiz: {
          q: "Which pass goes into the space behind the defence for a teammate to run onto?",
          options: ["A cross", "A cutback", "A through ball"],
          answer: 2,
          why: "A through ball splits the defence. A cross comes in from wide, and a cutback is pulled back from the byline.",
        },
        takeaway: "Cutbacks and through balls make cleaner chances than crosses.",
        links: [WIKI("Cross", "Cross_(association_football)"), WIKI("Assist", "Assist_(football)")],
      },
      {
        id: "counter",
        title: "Counter-attacks and pressing",
        view: "full",
        steps: [
          {
            text: "When a team loses the ball with lots of its players upfield, the other side can counter-attack: break forward fast before the defence gets back into shape.",
            marks: [away(30, 20), away(27, 46), away(40, 62), away(46, 30), away(50, 52), away(24, 66), away(76, 30), away(79, 52), keeper(118, 40),
              home(35, 40, "Wins it"), ball(36, 40), home(55, 18), home(58, 62)],
          },
          {
            text: "Counters create good chances because few defenders are left between the ball and the goal. Fast breaks often end one-on-one with the keeper.",
            marks: [pass([36, 40], [72, 20]), run([55, 18], [95, 30]), shot([96, 31], [120.5, 38])],
          },
          {
            text: "Pressing is the opposite idea: defend by closing opponents down high up the pitch, to win the ball close to their goal, where a shot is only seconds away.",
            clear: true,
            marks: [keeper(118, 40), away(108, 28, "On the ball"), ball(108.6, 28.6), away(106, 52), away(99, 70), away(96, 13),
              home(97, 28), home(95, 47), home(89, 62), run([97, 28], [105.5, 29]), run([95, 47], [104, 40]), run([89, 62], [100, 57])],
          },
        ],
        quiz: {
          q: "Why do counter-attacks often lead to good chances?",
          options: ["The referee gives more time", "Fewer defenders are back between the ball and the goal", "Goals on the break count double"],
          answer: 1,
          why: "The defending team was caught upfield, so there's space and fewer bodies in the way.",
        },
        takeaway: "Space wins: catch a team out of shape, or win the ball near their goal.",
        links: [WIKI("Counter-attack", "Counter-attack"), WIKI("Pressing", "Pressing_(association_football)")],
      },
      {
        id: "setpieces",
        title: "Set pieces",
        view: "half",
        steps: [
          {
            text: "Set pieces are restarts the attacking team can rehearse: corners, free kicks and penalties. A big share of tournament goals come from them.",
            marks: CORNER,
          },
          {
            text: "From a corner the taker aims for the near post, the far post or around the penalty spot, while attackers make runs to shake off their markers. Many end as headers, which are hard to score.",
            marks: [pass([119, 78], [114, 45], "Near post"), pass([119, 78], [113, 33], "Far post"), run([108, 38], [112.5, 34])],
          },
          {
            text: "A penalty is the best chance in football: about three in four go in.\n\nThe xG model in this game leaves penalties out, because they would swamp every other shot, so you'll never be asked to rate one.",
            clear: true,
            marks: [{ kind: "ring", at: [108, 40], label: "12 yards" }, home(107, 40), ball(108, 40), keeper(119.6, 40)],
          },
        ],
        quiz: {
          q: "Which set piece gives the best chance of a goal?",
          options: ["A corner", "A penalty", "A free kick from 30 yards"],
          answer: 1,
          why: "Roughly three in four penalties are scored. Corners and long free kicks are far lower.",
        },
        takeaway: "Set pieces are rehearsed chances. Penalties are the best of them.",
        links: [WIKI("Penalty kick", "Penalty_kick_(association_football)"), IFAB("The corner kick", "the-corner-kick")],
      },
    ],
  },
  {
    id: "chances",
    title: "Reading a Chance",
    blurb: "Expected goals, and everything the game tests you on.",
    icon: "target",
    lessons: [
      {
        id: "xg",
        title: "What is xG?",
        view: "half",
        steps: [
          {
            text: "Expected goals (xG) is the chance a shot goes in, judged before the ball is struck.\n\nIt comes from history: of all the shots taken from a similar spot, in a similar situation, how many were scored?",
            marks: [{ kind: "spot", at: [114, 40], band: 4, label: "Tap-in" }, { kind: "spot", at: [91, 40], band: 0, label: "Long shot" }],
          },
          {
            text: "An xG of 0.30 means about 30 of every 100 shots like it go in.\n\nA tap-in from a few yards can be above 0.50. A strike from 30 yards is often below 0.05.",
          },
          {
            text: "xG rates the chance, not the finish. A brilliant goal from a poor chance is still a poor chance. That's how a team can lose a match while creating more xG.",
          },
          {
            text: "The model in this game learned from about 45,000 real shots, looking at where each was taken and where every player stood. Its rating is the MODEL answer you're trying to match.",
          },
        ],
        quiz: {
          q: "A chance has an xG of 0.10. What does that mean?",
          options: ["It was 10 yards out", "About 1 in 10 shots like it are scored", "The player scores 10% of their shots"],
          answer: 1,
          why: "xG is about the chance, not the player: about 10 in every 100 shots like this one end up in the net.",
        },
        takeaway: "xG rates the chance, not the finish: goals per 100 shots like it.",
        links: [WIKI("Expected goals", "Expected_goals"), STATSBOMB_XG],
      },
      {
        id: "distance",
        title: "Distance and angle",
        view: "half",
        steps: [
          {
            text: "Distance is the biggest single factor. The closer you are, the less time the keeper has to react, and the less room the ball has to drift wide.",
            marks: [{ kind: "spot", at: [110, 40], band: 3, label: "10 yards" }, { kind: "spot", at: [96, 40], band: 0, label: "24 yards" }],
          },
          {
            text: "Angle matters too. Draw lines from the ball to each post: the gap between them is how much goal you can aim at. From the middle you see all of it.",
            clear: true,
            marks: [home(107.5, 40), ball(108, 40), { kind: "cone", from: [108, 40] }, keeper(119.3, 40)],
          },
          {
            text: "Out wide, even very close up, the goal shrinks to a sliver, and the keeper covers it by standing at the near post. Central beats wide.",
            clear: true,
            marks: [home(116, 60, "By the byline"), ball(116.3, 59.4), { kind: "cone", from: [116.3, 59.4] }, keeper(119.4, 44.4)],
          },
        ],
        quiz: {
          q: "Which is usually the better chance?",
          options: ["10 yards out, straight in front of goal", "6 yards out, right by the byline", "They're about the same"],
          answer: 0,
          why: "Closer helps, but by the byline there's barely any goal to aim at. Central and close is the best of both.",
        },
        takeaway: "Close and central. Every step closer counts, but only if you can see the goal.",
        links: [WIKI("Expected goals", "Expected_goals"), STATSBOMB_XG],
      },
      {
        id: "bodies",
        title: "Bodies, pressure and headers",
        view: "box",
        steps: [
          {
            text: "Every defender standing in the shooting cone can block the shot. Count the bodies between the ball and the goal: an empty cone is a big chance.",
            marks: [home(99.5, 39, "Shooter"), ball(100, 39), { kind: "cone", from: [100, 39] }, away(106, 39), away(108, 41.5), away(110, 37), keeper(119.3, 40)],
          },
          {
            text: "Pressure matters too. A defender right on the shooter takes away the time to set their feet and pick a corner, so more of those shots miss.",
            marks: [away(99, 36.6, "Pressure")],
          },
          {
            text: "Headers are much harder than shots with the foot: less power, harder to aim, and usually from a cross with defenders jumping too. From the same spot, a header is a much worse chance.",
            clear: true,
            marks: [pass([108, 69], [112, 42], "Cross"), home(112, 42.5, "Header"), away(112.6, 40.3), keeper(119, 41)],
          },
        ],
        quiz: {
          q: "Same spot, same defenders. Which is the better chance?",
          options: ["A header", "A shot with the foot", "No difference"],
          answer: 1,
          why: "With the foot you get more power and more control over where the ball goes.",
        },
        takeaway: "Count the bodies in the cone, check the pressure, and mark headers down.",
        links: [WIKI("Header", "Header_(association_football)"), STATSBOMB_XG],
      },
      {
        id: "bands",
        title: "The five chance bands",
        view: "half",
        steps: [
          {
            text: "In the game you call each chance as one of five bands, from cold to hot. The xG model makes its call too, and you score by matching it.",
            marks: [
              { kind: "spot", at: [88, 40], band: 0, label: "Speculative" },
              { kind: "spot", at: [100, 56], band: 1, label: "Half chance" },
              { kind: "spot", at: [105, 30], band: 2, label: "Good chance" },
              { kind: "spot", at: [109, 46], band: 3, label: "Big chance" },
              { kind: "spot", at: [115, 39], band: 4, label: "Sitter" },
            ],
          },
          {
            text: "Speculative: under 5%. Half chance: 5–12%. Good chance: 12–25%. Big chance: 25–50%. Sitter: 50% or more.",
          },
          {
            text: "Read the picture the way the model does: distance, angle, bodies in the cone, pressure, head or foot.\n\nAfter every shot it tells you what helped and what hurt. That's where the real learning happens.",
          },
        ],
        quiz: {
          q: "A shot that goes in about 1 time in 3 belongs in which band?",
          options: ["Good chance", "Big chance", "Sitter"],
          answer: 1,
          why: "One in three is about 33%, which falls in Big chance (25–50%).",
        },
        takeaway: "Under 5, 5–12, 12–25, 25–50, 50+: five bands, cold to hot.",
        links: [STATSBOMB_XG],
      },
      {
        id: "psxg",
        title: "After the strike",
        view: "box",
        steps: [
          {
            text: "Once the ball is struck we know more: where it's going. Post-shot xG rates the shot itself, for shots on target only. A strike into the corner is far harder to save than one at the keeper.",
            marks: [home(103.5, 40, "Shooter"), ball(104, 40), keeper(119.3, 40), shot([104, 40], [120.4, 43.5], "Corner: high"), shot([104, 40], [120.4, 40.5], "At keeper: low")],
          },
          {
            text: "Comparing the two tells a story. If post-shot xG is higher than xG, the shooter finished better than the chance. If a keeper keeps saving high post-shot shots, they're having a great day.",
          },
        ],
        quiz: {
          q: "Which shots get a post-shot xG?",
          options: ["Every shot", "Only shots on target", "Only goals"],
          answer: 1,
          why: "Post-shot xG needs to know where the ball was heading in the goal, so it only exists for shots on target.",
        },
        takeaway: "xG rates the chance; post-shot xG rates the strike.",
        links: [STATSBOMB_XG, WIKI("Expected goals", "Expected_goals")],
      },
    ],
  },
];

export const LESSONS: Lesson[] = CURRICULUM.flatMap((m) => m.lessons);

export function lessonById(id: string): Lesson | undefined {
  return LESSONS.find((l) => l.id === id);
}

export function moduleOf(id: string): Module | undefined {
  return CURRICULUM.find((m) => m.lessons.some((l) => l.id === id));
}

/** For each shot concept the game tags: a one-line note and the lesson that explains it. */
export const CONCEPT_NOTES: Record<string, { note: string; lesson: string }> = {
  "Close range": { note: "Close range: the keeper has little time, and the ball little room to go wide.", lesson: "distance" },
  "Long range": { note: "Long range: most shots from outside the box are speculative.", lesson: "distance" },
  "Tight angle": { note: "Tight angle: only a sliver of goal to aim at.", lesson: "distance" },
  Header: { note: "Header: much harder to score than the same chance on the foot.", lesson: "bodies" },
  "One-on-one": { note: "One-on-one: a big chance, but the keeper coming out shrinks the goal.", lesson: "keeper" },
  "Under pressure": { note: "Under pressure: no time to set the feet or pick a corner.", lesson: "bodies" },
  "Crowded box": { note: "Crowded box: every body in the cone can block the shot.", lesson: "bodies" },
  "From cross": { note: "From a cross: hard to control, and often met with a header.", lesson: "passes" },
  "Through ball": { note: "Through ball: in behind the defence, often one-on-one.", lesson: "passes" },
  "Standard chance": { note: "Nothing unusual: the rating comes mostly from distance and angle.", lesson: "xg" },
};

/** The lesson behind each reason the model gives for a rating (`explain.reasons`). */
export const REASON_LESSONS: Record<string, string> = {
  Goalkeeper: "keeper",
  "One-on-one": "keeper",
  Angle: "distance",
  Distance: "distance",
  "Bodies in the way": "bodies",
  "Space to shoot": "bodies",
  Pressure: "bodies",
  Header: "bodies",
  "The final ball": "passes",
  "First time": "passes",
};
