import {Easing, interpolate, spring} from "remotion";

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;
export const DURATION = 1650;

export const COLORS = {
  ink: "#082f31",
  inkSoft: "#476466",
  teal: "#0c6161",
  tealDark: "#063d3e",
  aqua: "#6fb9b8",
  aquaSoft: "#e9f4f3",
  canvas: "#b8dddd",
  yellow: "#ffc91c",
  yellowSoft: "#fff3b8",
  coral: "#ff786b",
  coralSoft: "#ffe1dc",
  blue: "#cde4f8",
  blueDark: "#356b91",
  pink: "#ed69b7",
  pinkSoft: "#f8d9ec",
  paper: "#f7fbfa",
  white: "#ffffff",
  line: "#dce9e7",
  lineStrong: "#c8dcda",
  muted: "#789091",
} as const;

export const FONT = '"Avenir Next", Avenir, "Helvetica Neue", Arial, sans-serif';
export const MONO = '"SFMono-Regular", Consolas, "Liberation Mono", monospace';
export const WEIGHT = {
  regular: 400,
  medium: 500,
  semibold: 600,
} as const;

export const SCENES = {
  collision: {from: 0, duration: 165},
  product: {from: 165, duration: 135},
  identity: {from: 300, duration: 210},
  lease: {from: 510, duration: 240},
  handoff: {from: 750, duration: 210},
  console: {from: 960, duration: 270},
  topology: {from: 1230, duration: 210},
  closing: {from: 1440, duration: 210},
} as const;

export const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));

export const fadeIn = (frame: number, from = 0, duration = 18) =>
  interpolate(frame, [from, from + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

export const rise = (frame: number, from = 0, distance = 28) => {
  const progress = spring({
    frame: frame - from,
    fps: FPS,
    config: {damping: 18, stiffness: 125, mass: 0.9},
  });
  return {
    opacity: clamp(progress),
    transform: `translateY(${(1 - progress) * distance}px)`,
  };
};

export const slide = (frame: number, from = 0, distance = 80) => {
  const progress = spring({
    frame: frame - from,
    fps: FPS,
    config: {damping: 20, stiffness: 105, mass: 1},
  });
  return {
    opacity: clamp(progress),
    transform: `translateX(${(1 - progress) * distance}px)`,
  };
};

export const sceneOpacity = (frame: number, duration: number) =>
  interpolate(frame, [0, 12, duration - 12, duration], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

export const typeText = (text: string, frame: number, start: number, speed = 1.7) => {
  const count = Math.floor(Math.max(0, frame - start) * speed);
  return text.slice(0, count);
};
