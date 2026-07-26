import React, {CSSProperties, PropsWithChildren} from "react";
import {LucideIcon} from "lucide-react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {COLORS, FONT, MONO, WEIGHT, fadeIn, rise, sceneOpacity, slide, typeText} from "./theme";

export const BrandMark: React.FC<{compact?: boolean; light?: boolean}> = ({compact = false, light = false}) => (
  <div style={{display: "flex", alignItems: "center", gap: compact ? 12 : 18}}>
    <div
      style={{
        position: "relative",
        width: compact ? 34 : 50,
        height: compact ? 34 : 50,
        overflow: "hidden",
        flex: `0 0 ${compact ? 34 : 50}px`,
        background: COLORS.white,
        border: `1px solid ${light ? "rgba(255,255,255,.36)" : "rgba(8,47,49,.16)"}`,
        borderRadius: "50%",
      }}
    >
      <div style={{position: "absolute", inset: "0 0 0 50%", background: light ? COLORS.tealDark : COLORS.ink}} />
    </div>
    <span
      style={{
        color: light ? COLORS.white : COLORS.ink,
        fontFamily: FONT,
        fontSize: compact ? 24 : 38,
        fontWeight: WEIGHT.medium,
      }}
    >
      Commons
    </span>
  </div>
);

export const GridBackdrop: React.FC<{dark?: boolean}> = ({dark = false}) => (
  <AbsoluteFill
    style={{
      backgroundColor: dark ? COLORS.tealDark : COLORS.paper,
      backgroundImage: `linear-gradient(${dark ? "rgba(255,255,255,.045)" : "rgba(8,47,49,.055)"} 1px, transparent 1px), linear-gradient(90deg, ${dark ? "rgba(255,255,255,.045)" : "rgba(8,47,49,.055)"} 1px, transparent 1px)`,
      backgroundSize: "72px 72px",
    }}
  />
);

export const SceneCanvas: React.FC<
  PropsWithChildren<{duration: number; dark?: boolean; label: string; accent?: string; contentStyle?: CSSProperties}>
> = ({duration, dark = false, label, accent = COLORS.yellow, contentStyle, children}) => {
  const frame = useCurrentFrame();
  const opacity = sceneOpacity(frame, duration);
  const bar = interpolate(frame, [0, duration], [0, 100], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});

  return (
    <AbsoluteFill style={{opacity, overflow: "hidden", fontFamily: FONT, fontWeight: WEIGHT.regular, color: dark ? COLORS.white : COLORS.ink}}>
      <GridBackdrop dark={dark} />
      <div style={{position: "absolute", inset: "0 auto 0 0", width: 18, background: accent}} />
      <div
        style={{
          position: "absolute",
          top: 52,
          right: 70,
          display: "flex",
          alignItems: "center",
          gap: 12,
          color: dark ? "rgba(255,255,255,.68)" : COLORS.muted,
          fontSize: 18,
          fontWeight: WEIGHT.medium,
          textTransform: "uppercase",
        }}
      >
        <span style={{width: 34, height: 3, background: accent}} />
        {label}
      </div>
      <div style={{position: "absolute", inset: "82px 86px 78px 104px", ...contentStyle}}>{children}</div>
      <div style={{position: "absolute", right: 86, bottom: 39, left: 104, height: 2, background: dark ? "rgba(255,255,255,.13)" : COLORS.line}}>
        <div style={{height: "100%", width: `${bar}%`, background: accent}} />
      </div>
    </AbsoluteFill>
  );
};

export const SceneHeading: React.FC<{
  eyebrow?: string;
  title: React.ReactNode;
  body?: React.ReactNode;
  light?: boolean;
  delay?: number;
  maxWidth?: number;
}> = ({eyebrow, title, body, light = false, delay = 0, maxWidth = 860}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{maxWidth}}>
      {eyebrow ? (
        <div style={{...rise(frame, delay), marginBottom: 20, color: light ? COLORS.aqua : COLORS.teal, fontSize: 22, fontWeight: WEIGHT.semibold, textTransform: "uppercase"}}>
          {eyebrow}
        </div>
      ) : null}
      <div style={{...rise(frame, delay + 5, 42), color: light ? COLORS.white : COLORS.ink, fontSize: 76, fontWeight: WEIGHT.medium, lineHeight: 1.08}}>{title}</div>
      {body ? (
        <div style={{...rise(frame, delay + 12), maxWidth: 760, marginTop: 24, color: light ? "#b9dcda" : COLORS.inkSoft, fontSize: 29, lineHeight: 1.38}}>{body}</div>
      ) : null}
    </div>
  );
};

export const Panel: React.FC<PropsWithChildren<{style?: CSSProperties; tone?: "paper" | "dark" | "yellow" | "blue" | "coral"}>> = ({style, tone = "paper", children}) => {
  const palette = {
    paper: {background: COLORS.white, border: COLORS.line, color: COLORS.ink},
    dark: {background: COLORS.tealDark, border: COLORS.teal, color: COLORS.white},
    yellow: {background: COLORS.yellowSoft, border: "#efd15b", color: COLORS.ink},
    blue: {background: "#eaf5ff", border: "#beddf8", color: COLORS.ink},
    coral: {background: COLORS.coralSoft, border: "#ffc1b7", color: COLORS.ink},
  }[tone];
  return (
    <div
      style={{
        boxSizing: "border-box",
        background: palette.background,
        border: `1px solid ${palette.border}`,
        borderRadius: 6,
        color: palette.color,
        boxShadow: "0 22px 54px rgba(24,92,92,.12)",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Pill: React.FC<PropsWithChildren<{tone?: "teal" | "yellow" | "coral" | "blue" | "muted"; style?: CSSProperties}>> = ({tone = "muted", style, children}) => {
  const palette = {
    teal: {background: COLORS.tealDark, color: COLORS.white, border: COLORS.tealDark},
    yellow: {background: COLORS.yellowSoft, color: COLORS.ink, border: "#efd15b"},
    coral: {background: COLORS.coralSoft, color: "#8c3b34", border: "#ffc1b7"},
    blue: {background: COLORS.blue, color: COLORS.blueDark, border: "#aed3ef"},
    muted: {background: COLORS.aquaSoft, color: COLORS.inkSoft, border: COLORS.line},
  }[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        minHeight: 38,
        gap: 8,
        padding: "5px 13px",
        color: palette.color,
        background: palette.background,
        border: `1px solid ${palette.border}`,
        borderRadius: 3,
        fontSize: 19,
        fontWeight: WEIGHT.medium,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </span>
  );
};

export const IconLabel: React.FC<PropsWithChildren<{icon: LucideIcon; color?: string; size?: number; style?: CSSProperties}>> = ({icon: Icon, color = COLORS.teal, size = 24, style, children}) => (
  <div style={{display: "flex", alignItems: "center", gap: 10, color, ...style}}>
    <Icon size={size} strokeWidth={2} />
    <span>{children}</span>
  </div>
);

export const TerminalPanel: React.FC<{
  title: string;
  command: string;
  output: Array<{text: string; tone?: "normal" | "success" | "warning" | "muted"}>;
  delay?: number;
  style?: CSSProperties;
  typing?: boolean;
}> = ({title, command, output, delay = 0, style, typing = true}) => {
  const frame = useCurrentFrame();
  const visibleCommand = typing ? typeText(command, frame, delay + 12, 2.3) : command;
  return (
    <Panel tone="dark" style={{padding: 0, overflow: "hidden", ...slide(frame, delay), ...style}}>
      <div style={{display: "flex", height: 48, alignItems: "center", justifyContent: "space-between", padding: "0 17px", background: "rgba(255,255,255,.07)", borderBottom: "1px solid rgba(255,255,255,.12)"}}>
        <div style={{display: "flex", gap: 7}}>
          {[COLORS.coral, COLORS.yellow, COLORS.aqua].map((color) => <span key={color} style={{width: 9, height: 9, background: color, borderRadius: "50%"}} />)}
        </div>
        <span style={{color: "#b9dcda", fontFamily: MONO, fontSize: 15}}>{title}</span>
      </div>
      <div style={{minHeight: 165, padding: "20px 22px", fontFamily: MONO, fontSize: 19, lineHeight: 1.55}}>
        <div style={{color: COLORS.yellow}}>$ <span style={{color: COLORS.white}}>{visibleCommand}</span><span style={{opacity: Math.floor(frame / 12) % 2 ? 0 : 1}}>▌</span></div>
        <div style={{display: "grid", gap: 4, marginTop: 14}}>
          {output.map((line, index) => {
            const opacity = fadeIn(frame, delay + 28 + index * 7, 8);
            const color = line.tone === "success" ? "#8de2c9" : line.tone === "warning" ? COLORS.yellow : line.tone === "muted" ? "#86a9a8" : "#dceceb";
            return <div key={`${line.text}-${index}`} style={{opacity, color}}>{line.text}</div>;
          })}
        </div>
      </div>
    </Panel>
  );
};

export const AgentNode: React.FC<{
  handle: string;
  runtime: string;
  status?: string;
  tone?: "teal" | "yellow" | "coral" | "blue";
  icon: LucideIcon;
  delay?: number;
  style?: CSSProperties;
}> = ({handle, runtime, status = "active", tone = "teal", icon: Icon, delay = 0, style}) => {
  const frame = useCurrentFrame();
  const colors = {
    teal: {disc: COLORS.teal, soft: COLORS.aquaSoft},
    yellow: {disc: "#c59600", soft: COLORS.yellowSoft},
    coral: {disc: COLORS.coral, soft: COLORS.coralSoft},
    blue: {disc: COLORS.blueDark, soft: "#eaf5ff"},
  }[tone];
  return (
    <Panel style={{display: "flex", alignItems: "center", gap: 15, padding: 17, background: colors.soft, ...rise(frame, delay), ...style}}>
      <div style={{display: "grid", width: 46, height: 46, flex: "0 0 46px", placeItems: "center", color: COLORS.white, background: colors.disc, borderRadius: "50%"}}><Icon size={24} /></div>
      <div style={{minWidth: 0}}>
        <span style={{display: "block", overflow: "hidden", fontSize: 20, fontWeight: WEIGHT.medium, textOverflow: "ellipsis", whiteSpace: "nowrap"}}>@{handle}</span>
        <span style={{display: "block", marginTop: 3, color: COLORS.inkSoft, fontSize: 15}}>{runtime} · {status}</span>
      </div>
    </Panel>
  );
};

export const FlowLine: React.FC<{progress: number; vertical?: boolean; color?: string; style?: CSSProperties}> = ({progress, vertical = false, color = COLORS.aqua, style}) => (
  <div
    style={{
      position: "relative",
      width: vertical ? 4 : "100%",
      height: vertical ? "100%" : 4,
      overflow: "hidden",
      background: COLORS.line,
      ...style,
    }}
  >
    <div style={{width: vertical ? "100%" : `${progress * 100}%`, height: vertical ? `${progress * 100}%` : "100%", background: color}} />
  </div>
);

export const MetricCard: React.FC<{label: string; value: string; tone: "teal" | "yellow" | "coral" | "blue"; icon: LucideIcon; delay?: number}> = ({label, value, tone, icon: Icon, delay = 0}) => {
  const frame = useCurrentFrame();
  const palette = {
    teal: {background: COLORS.tealDark, color: COLORS.white},
    yellow: {background: COLORS.yellow, color: COLORS.ink},
    coral: {background: COLORS.coralSoft, color: COLORS.ink},
    blue: {background: COLORS.blue, color: COLORS.ink},
  }[tone];
  return (
    <div style={{...rise(frame, delay), minWidth: 190, padding: 22, color: palette.color, background: palette.background, border: `1px solid ${tone === "teal" ? COLORS.tealDark : COLORS.lineStrong}`, borderRadius: 4}}>
      <Icon size={25} />
      <div style={{marginTop: 17, fontSize: 19, fontWeight: WEIGHT.medium}}>{label}</div>
      <span style={{display: "block", marginTop: 10, fontSize: 48, fontWeight: WEIGHT.medium, lineHeight: 1}}>{value}</span>
    </div>
  );
};
