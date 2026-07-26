import React from "react";
import {Composition, Still} from "remotion";
import {CommonsIntroduction, CommonsPoster} from "./CommonsIntroduction";
import {DURATION, FPS, HEIGHT, WIDTH} from "./theme";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="CommonsIntroduction"
      component={CommonsIntroduction}
      durationInFrames={DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Still id="CommonsPoster" component={CommonsPoster} width={WIDTH} height={HEIGHT} />
  </>
);
