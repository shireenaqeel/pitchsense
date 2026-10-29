// Every sound is synthesised with WebAudio, so the game ships no audio files.

import { G } from "../state";

let ctx: AudioContext | null = null;
let noiseBuffer: AudioBuffer | null = null;

function audio(): AudioContext | null {
  if (G.save.settings.muted) return null;
  try {
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

function noise(ac: AudioContext): AudioBuffer {
  if (noiseBuffer) return noiseBuffer;
  noiseBuffer = ac.createBuffer(1, ac.sampleRate * 2, ac.sampleRate);
  const d = noiseBuffer.getChannelData(0);
  let brown = 0;
  for (let i = 0; i < d.length; i++) {
    brown = (brown + 0.02 * (Math.random() * 2 - 1)) / 1.02;
    d[i] = brown * 3.5;
  }
  return noiseBuffer;
}

function tone(freq: number, dur: number, type: OscillatorType = "sine", vol = 0.15, delay = 0, slideTo?: number): void {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime + delay;
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
  gain.gain.setValueAtTime(vol, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
  osc.connect(gain).connect(ac.destination);
  osc.start(t);
  osc.stop(t + dur + 0.02);
}

function rumble(dur: number, vol: number, cutoff: number, attack = 0.3): void {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime;
  const src = ac.createBufferSource();
  src.buffer = noise(ac);
  src.loop = true;
  const filter = ac.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = cutoff;
  const gain = ac.createGain();
  gain.gain.setValueAtTime(0.001, t);
  gain.gain.exponentialRampToValueAtTime(vol, t + attack);
  gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
  src.connect(filter).connect(gain).connect(ac.destination);
  src.start(t);
  src.stop(t + dur + 0.05);
}

export const sfx = {
  click: () => tone(660, 0.06, "square", 0.05),
  hover: () => tone(880, 0.03, "sine", 0.03),
  select: () => tone(440, 0.12, "triangle", 0.12, 0, 880),
  tick: () => tone(1200, 0.04, "square", 0.04),
  kick: () => {
    tone(140, 0.15, "sine", 0.4, 0, 50);
    rumble(0.12, 0.3, 2500, 0.005);
  },
  whistle: () => {
    for (let i = 0; i < 2; i++) tone(2900, 0.18, "sine", 0.08, i * 0.22, 2750);
  },
  goal: () => {
    rumble(2.6, 0.5, 900, 0.25);
    [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.25, "triangle", 0.1, 0.15 + i * 0.09));
  },
  groan: () => rumble(1.2, 0.25, 400, 0.2),
  save: () => {
    tone(220, 0.1, "square", 0.08);
    rumble(0.9, 0.2, 700, 0.1);
  },
  exact: () => [784, 988, 1175].forEach((f, i) => tone(f, 0.14, "triangle", 0.1, i * 0.06)),
  near: () => [523, 659].forEach((f, i) => tone(f, 0.14, "triangle", 0.08, i * 0.07)),
  miss: () => tone(200, 0.3, "sawtooth", 0.06, 0, 110),
  combo: (n: number) => tone(500 + n * 80, 0.12, "square", 0.06),
  levelUp: () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.22, "triangle", 0.12, i * 0.1)),
  achievement: () => [880, 1109, 1319].forEach((f, i) => tone(f, 0.2, "sine", 0.1, i * 0.08)),
  bossHit: () => {
    tone(90, 0.2, "sawtooth", 0.2, 0, 40);
    rumble(0.25, 0.25, 1200, 0.01);
  },
  heartLost: () => tone(330, 0.35, "square", 0.08, 0, 110),
  coin: () => [1319, 1760].forEach((f, i) => tone(f, 0.08, "square", 0.05, i * 0.05)),
};
