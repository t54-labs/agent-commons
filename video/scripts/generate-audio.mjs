import fs from "node:fs";

const outputPath = process.argv[2];
if (!outputPath) {
  throw new Error("Usage: node generate-audio.mjs <output.wav>");
}

const SAMPLE_RATE = 48_000;
const DURATION_SECONDS = 55;
const TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS;
const BPM = 96;
const BEAT = 60 / BPM;
const BAR = BEAT * 4;
const TAU = Math.PI * 2;

const left = new Float32Array(TOTAL_SAMPLES);
const right = new Float32Array(TOTAL_SAMPLES);

const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const midiToFrequency = (midi) => 440 * 2 ** ((midi - 69) / 12);

let noiseState = 0x54c0ffee;
const random = () => {
  noiseState = (1664525 * noiseState + 1013904223) >>> 0;
  return noiseState / 0x1_0000_0000;
};

const panGains = (pan) => {
  const angle = ((clamp(pan, -1, 1) + 1) * Math.PI) / 4;
  return [Math.cos(angle), Math.sin(angle)];
};

const addStereoSample = (index, value, pan = 0) => {
  if (index < 0 || index >= TOTAL_SAMPLES) return;
  const [leftGain, rightGain] = panGains(pan);
  left[index] += value * leftGain;
  right[index] += value * rightGain;
};

const padEnvelope = (time, duration) => {
  const attack = clamp(time / 0.55);
  const release = clamp((duration - time) / 1.15);
  return Math.sin((Math.min(attack, release) * Math.PI) / 2) ** 2;
};

const tonalSample = (instrument, phase, time) => {
  if (instrument === "pad") {
    const drift = Math.sin(TAU * 0.18 * time) * 0.015;
    return (
      Math.sin(phase + drift) * 0.72 +
      Math.sin(phase * 2 + 0.24) * 0.2 +
      Math.sin(phase * 3 + 0.61) * 0.08
    );
  }
  if (instrument === "pluck") {
    return Math.sin(phase) * 0.72 + Math.sin(phase * 2) * 0.2 + Math.sin(phase * 4) * 0.08;
  }
  if (instrument === "bell") {
    return Math.sin(phase) * 0.66 + Math.sin(phase * 2.01) * 0.2 + Math.sin(phase * 3.99) * 0.14;
  }
  return Math.sin(phase) * 0.88 + Math.sin(phase * 2) * 0.12;
};

const addTonalNote = ({start, duration, midi, amplitude, instrument, pan = 0}) => {
  const startIndex = Math.max(0, Math.floor(start * SAMPLE_RATE));
  const endIndex = Math.min(TOTAL_SAMPLES, Math.ceil((start + duration) * SAMPLE_RATE));
  const frequency = midiToFrequency(midi);

  for (let index = startIndex; index < endIndex; index += 1) {
    const time = index / SAMPLE_RATE - start;
    let envelope;
    if (instrument === "pad") {
      envelope = padEnvelope(time, duration);
    } else if (instrument === "pluck") {
      envelope = Math.min(1, time / 0.012) * Math.exp(-time * 5.1);
    } else if (instrument === "bell") {
      envelope = Math.min(1, time / 0.018) * Math.exp(-time * 2.65);
    } else {
      envelope = Math.min(1, time / 0.025) * Math.exp(-time * 2.35);
    }
    const phase = TAU * frequency * time;
    addStereoSample(index, tonalSample(instrument, phase, time) * envelope * amplitude, pan);
  }
};

const addKick = (start, amplitude) => {
  const duration = 0.42;
  const startIndex = Math.floor(start * SAMPLE_RATE);
  const endIndex = Math.min(TOTAL_SAMPLES, Math.ceil((start + duration) * SAMPLE_RATE));
  for (let index = startIndex; index < endIndex; index += 1) {
    const time = index / SAMPLE_RATE - start;
    const phase = TAU * (50 * time + (48 / 24) * (1 - Math.exp(-24 * time)));
    const envelope = Math.exp(-time * 12.5);
    addStereoSample(index, Math.sin(phase) * envelope * amplitude);
  }
};

const addSnare = (start, amplitude) => {
  const duration = 0.24;
  const startIndex = Math.floor(start * SAMPLE_RATE);
  const endIndex = Math.min(TOTAL_SAMPLES, Math.ceil((start + duration) * SAMPLE_RATE));
  let previousNoise = 0;
  for (let index = startIndex; index < endIndex; index += 1) {
    const time = index / SAMPLE_RATE - start;
    const noise = random() * 2 - 1;
    const brightNoise = noise - previousNoise * 0.76;
    previousNoise = noise;
    const envelope = Math.exp(-time * 19);
    const tone = Math.sin(TAU * 182 * time) * 0.2;
    addStereoSample(index, (brightNoise * 0.8 + tone) * envelope * amplitude, 0.05);
  }
};

const addHat = (start, amplitude, pan) => {
  const duration = 0.1;
  const startIndex = Math.floor(start * SAMPLE_RATE);
  const endIndex = Math.min(TOTAL_SAMPLES, Math.ceil((start + duration) * SAMPLE_RATE));
  let previousNoise = 0;
  for (let index = startIndex; index < endIndex; index += 1) {
    const time = index / SAMPLE_RATE - start;
    const noise = random() * 2 - 1;
    const brightNoise = noise - previousNoise * 0.92;
    previousNoise = noise;
    addStereoSample(index, brightNoise * Math.exp(-time * 48) * amplitude, pan);
  }
};

const chords = [
  {pad: [50, 54, 57, 61, 64], arp: [62, 69, 66, 73, 69, 66, 73, 76], bass: 38},
  {pad: [49, 52, 57, 59], arp: [61, 69, 64, 71, 69, 64, 71, 76], bass: 45},
  {pad: [47, 50, 54, 57], arp: [59, 66, 62, 69, 66, 62, 69, 74], bass: 35},
  {pad: [43, 47, 50, 54], arp: [55, 62, 59, 66, 62, 59, 66, 71], bass: 43},
];

const barCount = Math.ceil(DURATION_SECONDS / BAR);
for (let bar = 0; bar < barCount; bar += 1) {
  const start = bar * BAR;
  const chordIndex = bar === barCount - 1 ? 0 : bar % chords.length;
  const chord = chords[chordIndex];
  const isIntro = bar < 2;
  const isOutro = bar >= 19;
  const padAmplitude = isIntro || isOutro ? 0.014 : 0.018;
  const padPans = [-0.42, -0.2, 0, 0.2, 0.42];

  chord.pad.forEach((midi, index) => {
    addTonalNote({
      start,
      duration: Math.min(BAR + 0.62, DURATION_SECONDS - start),
      midi,
      amplitude: padAmplitude,
      instrument: "pad",
      pan: padPans[index] ?? 0,
    });
  });

  if (bar >= 1 && bar <= 20) {
    chord.arp.forEach((midi, step) => {
      addTonalNote({
        start: start + step * (BEAT / 2),
        duration: 0.56,
        midi,
        amplitude: isOutro ? 0.022 : 0.028,
        instrument: "pluck",
        pan: step % 2 === 0 ? -0.23 : 0.23,
      });
    });
  }

  if (bar >= 2 && bar <= 19) {
    addTonalNote({start, duration: 1.05, midi: chord.bass, amplitude: 0.05, instrument: "bass", pan: -0.05});
    addTonalNote({start: start + BEAT * 2, duration: 0.86, midi: chord.bass + 7, amplitude: 0.034, instrument: "bass", pan: 0.05});
  }
}

const melody = [
  [0, 66, 1],
  [1, 69, 1],
  [2, 71, 2],
  [4, 69, 1],
  [5.5, 66, 0.5],
  [6, 64, 2],
  [8, 62, 1],
  [9, 64, 1],
  [10, 66, 2],
  [12, 69, 1],
  [13, 67, 1],
  [14, 66, 2],
];

for (const startBeat of [28, 68]) {
  melody.forEach(([offset, midi, beats], index) => {
    addTonalNote({
      start: (startBeat + offset) * BEAT,
      duration: beats * BEAT + 0.45,
      midi,
      amplitude: startBeat > 60 ? 0.035 : 0.04,
      instrument: "bell",
      pan: index % 2 === 0 ? -0.14 : 0.14,
    });
  });
}

const totalBeats = Math.floor(DURATION_SECONDS / BEAT);
for (let beatIndex = 0; beatIndex <= totalBeats; beatIndex += 1) {
  const time = beatIndex * BEAT;
  const beatInBar = beatIndex % 4;
  const fullRhythm = time >= 15 && time < 47.5;
  const lightRhythm = time >= 5 && time < 51;

  if (lightRhythm && (beatInBar === 0 || beatInBar === 2)) {
    addKick(time, fullRhythm ? 0.12 : 0.085);
  }
  if (fullRhythm && (beatInBar === 1 || beatInBar === 3)) {
    addSnare(time, 0.052);
  }
}

for (let halfBeat = 0; halfBeat * (BEAT / 2) < DURATION_SECONDS; halfBeat += 1) {
  const baseTime = halfBeat * (BEAT / 2);
  if (baseTime < 9 || baseTime >= 49.5) continue;
  const swing = halfBeat % 2 === 1 ? 0.035 : 0;
  const accent = halfBeat % 4 === 0 ? 1 : 0.72;
  addHat(baseTime + swing, 0.014 * accent, halfBeat % 2 === 0 ? -0.3 : 0.3);
}

addTonalNote({start: 52.5, duration: 2.5, midi: 74, amplitude: 0.038, instrument: "bell", pan: -0.12});
addTonalNote({start: 53.1, duration: 1.9, midi: 69, amplitude: 0.03, instrument: "bell", pan: 0.12});

const delayA = Math.round(SAMPLE_RATE * 0.19);
const delayB = Math.round(SAMPLE_RATE * 0.37);
const mixedSample = (channel, opposite, index) => {
  let value = channel[index];
  if (index >= delayA) value += opposite[index - delayA] * 0.12;
  if (index >= delayB) value += channel[index - delayB] * 0.075;
  const time = index / SAMPLE_RATE;
  const fadeIn = clamp(time / 1.1);
  const fadeOut = clamp((DURATION_SECONDS - time) / 3.4);
  return Math.tanh(value * 1.08) * Math.min(fadeIn, fadeOut);
};

let peak = 0;
for (let index = 0; index < TOTAL_SAMPLES; index += 1) {
  peak = Math.max(
    peak,
    Math.abs(mixedSample(left, right, index)),
    Math.abs(mixedSample(right, left, index)),
  );
}
const masterGain = Math.min(2.4, 0.76 / Math.max(peak, 0.001));

const dataBytes = TOTAL_SAMPLES * 2 * 2;
const wav = Buffer.allocUnsafe(44 + dataBytes);
wav.write("RIFF", 0);
wav.writeUInt32LE(36 + dataBytes, 4);
wav.write("WAVE", 8);
wav.write("fmt ", 12);
wav.writeUInt32LE(16, 16);
wav.writeUInt16LE(1, 20);
wav.writeUInt16LE(2, 22);
wav.writeUInt32LE(SAMPLE_RATE, 24);
wav.writeUInt32LE(SAMPLE_RATE * 4, 28);
wav.writeUInt16LE(4, 32);
wav.writeUInt16LE(16, 34);
wav.write("data", 36);
wav.writeUInt32LE(dataBytes, 40);

let offset = 44;
for (let index = 0; index < TOTAL_SAMPLES; index += 1) {
  const leftValue = clamp(mixedSample(left, right, index) * masterGain, -1, 1);
  const rightValue = clamp(mixedSample(right, left, index) * masterGain, -1, 1);
  wav.writeInt16LE(Math.round(leftValue * 32767), offset);
  wav.writeInt16LE(Math.round(rightValue * 32767), offset + 2);
  offset += 4;
}

fs.writeFileSync(outputPath, wav);
console.log(`Generated ${DURATION_SECONDS}s melodic score at ${BPM} BPM in D major (peak ${peak.toFixed(3)}).`);
