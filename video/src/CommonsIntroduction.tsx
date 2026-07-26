import React from "react";
import {Audio} from "@remotion/media";
import {AbsoluteFill, Sequence, staticFile} from "remotion";
import {
  ClosingScene,
  CollisionScene,
  ConsoleScene,
  HandoffScene,
  IdentityScene,
  LeaseScene,
  PosterScene,
  ProductScene,
  TopologyScene,
} from "./scenes";
import {COLORS, SCENES} from "./theme";

export const CommonsIntroduction: React.FC = () => (
  <AbsoluteFill style={{background: COLORS.canvas}}>
    <Audio src={staticFile("commons-bed.m4a")} volume={0.88} />
    <Sequence name="01 · Collision" from={SCENES.collision.from} durationInFrames={SCENES.collision.duration}>
      <CollisionScene duration={SCENES.collision.duration} />
    </Sequence>
    <Sequence name="02 · Product" from={SCENES.product.from} durationInFrames={SCENES.product.duration}>
      <ProductScene duration={SCENES.product.duration} />
    </Sequence>
    <Sequence name="03 · Scope and intent" from={SCENES.identity.from} durationInFrames={SCENES.identity.duration}>
      <IdentityScene duration={SCENES.identity.duration} />
    </Sequence>
    <Sequence name="04 · Fenced lease" from={SCENES.lease.from} durationInFrames={SCENES.lease.duration}>
      <LeaseScene duration={SCENES.lease.duration} />
    </Sequence>
    <Sequence name="05 · Handoff" from={SCENES.handoff.from} durationInFrames={SCENES.handoff.duration}>
      <HandoffScene duration={SCENES.handoff.duration} />
    </Sequence>
    <Sequence name="06 · Console" from={SCENES.console.from} durationInFrames={SCENES.console.duration}>
      <ConsoleScene duration={SCENES.console.duration} />
    </Sequence>
    <Sequence name="07 · Deployment model" from={SCENES.topology.from} durationInFrames={SCENES.topology.duration}>
      <TopologyScene duration={SCENES.topology.duration} />
    </Sequence>
    <Sequence name="08 · Close" from={SCENES.closing.from} durationInFrames={SCENES.closing.duration}>
      <ClosingScene duration={SCENES.closing.duration} />
    </Sequence>
  </AbsoluteFill>
);

export const CommonsPoster: React.FC = () => <PosterScene />;
