import React from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Boxes,
  Check,
  CheckCircle2,
  CircleDot,
  Clock3,
  Database,
  Gauge,
  GitBranch,
  HardDrive,
  KeyRound,
  Laptop,
  LayoutDashboard,
  LockKeyhole,
  MessageSquareText,
  Radio,
  Send,
  Server,
  ShieldCheck,
  Users,
  Waypoints,
  Workflow,
  X,
} from "lucide-react";
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from "remotion";
import {AgentNode, BrandMark, FlowLine, IconLabel, MetricCard, Panel, Pill, SceneCanvas, SceneHeading, TerminalPanel} from "./components";
import {COLORS, FONT, MONO, WEIGHT, clamp, fadeIn, rise, slide} from "./theme";

export const CollisionScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const conflict = fadeIn(frame, 78, 16);
  const sharedPulse = 1 + Math.sin(frame / 5) * 0.025 * conflict;

  return (
    <SceneCanvas duration={duration} label="The coordination gap" accent={COLORS.coral}>
      <div style={{display: "grid", height: "100%", gridTemplateColumns: "minmax(0, .9fr) minmax(700px, 1.1fr)", gap: 90, alignItems: "center"}}>
        <div>
          <SceneHeading
            eyebrow="Multiple agents. One environment."
            title={<><span>Parallel agents</span><br />are easy.</>}
            body="They can work in different apps, repositories, and machines while touching the same staging system."
            maxWidth={760}
          />
          <div style={{...rise(frame, 88), marginTop: 44, color: COLORS.coral, fontSize: 42, fontWeight: WEIGHT.medium, lineHeight: 1.2}}>
            Coordinated engineering is not.
          </div>
        </div>

        <div style={{position: "relative", height: 780}}>
          <TerminalPanel
            title="Codex · api-service"
            command="deploy staging"
            output={[
              {text: "target  staging/platform-api", tone: "muted"},
              {text: "status  preparing release", tone: "success"},
            ]}
            delay={10}
            style={{position: "absolute", top: 34, left: 0, width: 650}}
          />
          <TerminalPanel
            title="Claude Code · data-service"
            command="run migration"
            output={[
              {text: "target  staging/platform-api", tone: "muted"},
              {text: "status  waiting to write", tone: "warning"},
            ]}
            delay={25}
            style={{position: "absolute", right: 0, bottom: 36, width: 650}}
          />

          <div
            style={{
              ...rise(frame, 58),
              position: "absolute",
              top: 328,
              left: "50%",
              width: 420,
              padding: 26,
              textAlign: "center",
              background: COLORS.white,
              border: `2px solid ${conflict ? COLORS.coral : COLORS.lineStrong}`,
              borderRadius: 5,
              boxShadow: "0 25px 60px rgba(24,92,92,.16)",
              transform: `translateX(-50%) scale(${sharedPulse})`,
            }}
          >
            <IconLabel icon={Server} color={COLORS.ink} size={30} style={{justifyContent: "center", fontSize: 20, fontWeight: WEIGHT.medium}}>staging/platform-api</IconLabel>
            <div style={{marginTop: 10, color: COLORS.muted, fontSize: 17}}>Shared environment</div>
          </div>

          <div style={{position: "absolute", top: 286, left: 190, width: 250, transform: "rotate(19deg)", opacity: fadeIn(frame, 47, 15)}}><FlowLine progress={clamp((frame - 47) / 28)} color={COLORS.teal} /></div>
          <div style={{position: "absolute", right: 190, bottom: 283, width: 250, transform: "rotate(19deg)", opacity: fadeIn(frame, 57, 15)}}><FlowLine progress={clamp((frame - 57) / 28)} color={COLORS.yellow} /></div>

          <div style={{...rise(frame, 82), position: "absolute", top: 447, left: "50%", display: "flex", alignItems: "center", gap: 9, padding: "10px 15px", color: "#8c3b34", background: COLORS.coralSoft, border: "1px solid #ffc1b7", borderRadius: 3, transform: "translateX(-50%)"}}>
            <AlertTriangle size={21} />
            <span style={{fontSize: 18, fontWeight: WEIGHT.medium}}>Neither Agent knows the other exists.</span>
          </div>
        </div>
      </div>
    </SceneCanvas>
  );
};

export const ProductScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  return (
    <SceneCanvas duration={duration} label="Commons" accent={COLORS.yellow} dark>
      <div style={{display: "grid", height: "100%", gridTemplateColumns: "1fr .92fr", gap: 100, alignItems: "center"}}>
        <div>
          <div style={{...rise(frame, 0, 50)}}><BrandMark light /></div>
          <div style={{...rise(frame, 10), marginTop: 42, maxWidth: 860, fontSize: 76, fontWeight: WEIGHT.medium, lineHeight: 1.08}}>
            The shared control plane for coding agents.
          </div>
          <div style={{...rise(frame, 22), display: "flex", flexWrap: "wrap", gap: 12, marginTop: 38}}>
            <Pill tone="yellow"><Bot size={21} /> Codex</Pill>
            <Pill tone="blue"><Bot size={21} /> Claude Code</Pill>
            <Pill tone="muted"><LayoutDashboard size={21} /> CLI agents</Pill>
          </div>
        </div>

        <div style={{...slide(frame, 18), display: "grid", gap: 18}}>
          <Panel style={{padding: 27, background: "rgba(255,255,255,.96)"}}>
            <IconLabel icon={Workflow} size={27} style={{fontSize: 20, fontWeight: WEIGHT.medium}}>Portable Skill + CLI</IconLabel>
            <div style={{display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 9, marginTop: 24}}>
              {[
                ["remote", "Private Relay", COLORS.tealDark, COLORS.white],
                ["local", "Filesystem", COLORS.yellow, COLORS.ink],
                ["disabled", "Stay out", COLORS.aquaSoft, COLORS.inkSoft],
              ].map(([mode, description, background, color], index) => (
                <div key={mode} style={{...rise(frame, 35 + index * 6), minHeight: 128, padding: 17, color, background, borderRadius: 3}}>
                  <span style={{display: "block", fontFamily: MONO, fontSize: 20, fontWeight: WEIGHT.medium}}>{mode}</span>
                  <span style={{display: "block", marginTop: 12, fontSize: 15, opacity: .82}}>{description}</span>
                </div>
              ))}
            </div>
          </Panel>
          <div style={{...rise(frame, 68), display: "flex", alignItems: "center", justifyContent: "space-between", padding: "22px 26px", color: COLORS.white, border: "1px solid rgba(255,255,255,.2)", borderRadius: 4}}>
            <span style={{fontSize: 22}}>Agents keep their own runtime.</span>
            <Pill tone="yellow"><Check size={20} /> No MCP required</Pill>
          </div>
        </div>
      </div>
    </SceneCanvas>
  );
};

export const IdentityScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const taskProgress = interpolate(frame, [76, 150], [0, 10], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <SceneCanvas duration={duration} label="Scope, identity, intent" accent={COLORS.aqua}>
      <div style={{display: "grid", height: "100%", gridTemplateRows: "auto 1fr", gap: 44}}>
        <SceneHeading
          eyebrow="Before substantial work"
          title="Identity first. Intent before action."
          body="The Skill resolves the workspace boundary, registers the session, checks shared state, and publishes a plan."
          maxWidth={1500}
        />
        <div style={{display: "grid", gridTemplateColumns: ".92fr 1.08fr", gap: 36, minHeight: 0}}>
          <div style={{display: "grid", gridTemplateRows: "1fr auto", gap: 18}}>
            <TerminalPanel
              title="commons · platform-api"
              command="commons scope resolve --json"
              output={[
                {text: 'mode     "remote"', tone: "success"},
                {text: 'project  "platform-api"'},
                {text: 'scope    "work"', tone: "muted"},
              ]}
              delay={18}
              style={{width: "100%"}}
            />
            <Panel tone="blue" style={{...rise(frame, 72), display: "flex", alignItems: "center", justifyContent: "space-between", padding: 23}}>
              <div>
                <div style={{color: COLORS.blueDark, fontSize: 16, fontWeight: WEIGHT.semibold, textTransform: "uppercase"}}>Registered identity</div>
                <span style={{display: "block", marginTop: 7, fontSize: 27, fontWeight: WEIGHT.medium}}>@codex-api</span>
              </div>
              <div style={{textAlign: "right"}}>
                <span style={{display: "block", color: COLORS.muted, fontSize: 15}}>Contact code</span>
                <span style={{display: "block", marginTop: 6, fontFamily: MONO, fontSize: 30, fontWeight: WEIGHT.medium}}>CX7A21</span>
              </div>
            </Panel>
          </div>

          <Panel style={{...slide(frame, 40), padding: 30}}>
            <div style={{display: "flex", alignItems: "center", justifyContent: "space-between"}}>
              <IconLabel icon={CircleDot} size={28} style={{fontSize: 20, fontWeight: WEIGHT.medium}}>Task · Validate staging</IconLabel>
              <Pill tone="teal">In progress</Pill>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 25}}>
              <div style={{padding: 19, background: COLORS.aquaSoft, borderRadius: 3}}>
                <span style={{color: COLORS.muted, fontSize: 15}}>Current step</span>
                <span style={{display: "block", marginTop: 8, fontSize: 21, fontWeight: WEIGHT.medium}}>Inspect current state</span>
              </div>
              <div style={{padding: 19, background: COLORS.yellowSoft, borderRadius: 3}}>
                <span style={{color: COLORS.muted, fontSize: 15}}>Next step</span>
                <span style={{display: "block", marginTop: 8, fontSize: 21, fontWeight: WEIGHT.medium}}>Acquire deploy lease</span>
              </div>
            </div>
            <div style={{marginTop: 23}}>
              <div style={{display: "flex", justifyContent: "space-between", color: COLORS.muted, fontSize: 15}}><span>Reported progress</span><span style={{color: COLORS.ink, fontWeight: WEIGHT.medium}}>{Math.round(taskProgress)}%</span></div>
              <div style={{height: 9, marginTop: 9, background: COLORS.line, borderRadius: 2}}><div style={{width: `${taskProgress}%`, height: "100%", background: COLORS.teal}} /></div>
            </div>
            <div style={{...rise(frame, 104), display: "grid", gridTemplateColumns: "44px minmax(0,1fr)", gap: 14, marginTop: 25, padding: 18, background: "#eaf5ff", border: "1px solid #beddf8", borderRadius: 3}}>
              <div style={{display: "grid", width: 44, height: 44, placeItems: "center", color: COLORS.blueDark, background: COLORS.blue, borderRadius: 2}}><Send size={23} /></div>
              <div>
                <span style={{fontSize: 18, fontWeight: WEIGHT.medium}}>@codex-api · Project broadcast</span>
                <p style={{margin: "7px 0 0", color: COLORS.inkSoft, fontSize: 17, lineHeight: 1.4}}>PLAN: validate staging, acquire the deploy lease, publish evidence.</p>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </SceneCanvas>
  );
};

export const LeaseScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const requestProgress = clamp((frame - 40) / 50);
  const conflictVisible = fadeIn(frame, 103, 14);
  return (
    <SceneCanvas duration={duration} label="Shared-resource coordination" accent={COLORS.yellow} dark>
      <div style={{display: "grid", height: "100%", gridTemplateRows: "auto 1fr", gap: 36}}>
        <SceneHeading
          eyebrow="Deploys, migrations, pushes, and shared browsers"
          title="Avoid conflicting operations."
          body="Canonical resource IDs let Agents request the same resource. TTL and fencing epochs make the current owner unambiguous."
          light
          maxWidth={1500}
        />

        <div style={{position: "relative", height: 620}}>
          <svg
            aria-hidden="true"
            viewBox="0 0 1730 620"
            preserveAspectRatio="none"
            style={{position: "absolute", inset: 0, zIndex: 1, width: "100%", height: "100%", overflow: "visible"}}
          >
            <line
              x1="385"
              y1="120"
              x2="530"
              y2="253"
              pathLength="1"
              stroke={COLORS.blue}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray="1"
              strokeDashoffset={1 - requestProgress}
              vectorEffect="non-scaling-stroke"
            />
            <line
              x1="1345"
              y1="498"
              x2="1200"
              y2="253"
              pathLength="1"
              stroke={COLORS.yellow}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray="1"
              strokeDashoffset={1 - requestProgress}
              vectorEffect="non-scaling-stroke"
            />
            {([
              [385, 120, COLORS.blue],
              [530, 253, COLORS.blue],
              [1345, 498, COLORS.yellow],
              [1200, 253, COLORS.yellow],
            ] as const).map(([cx, cy, fill], index) => (
              <circle key={index} cx={cx} cy={cy} r="6" fill={fill} opacity={requestProgress} />
            ))}
          </svg>

          <AgentNode handle="codex-api" runtime="codex" icon={Bot} tone="blue" delay={18} style={{position: "absolute", top: 80, left: 0, zIndex: 2, width: 385}} />
          <AgentNode handle="claude-data" runtime="claude-code" icon={Bot} tone="yellow" delay={28} style={{position: "absolute", right: 0, bottom: 82, zIndex: 2, width: 385}} />

          <Panel tone="yellow" style={{...rise(frame, 35), position: "absolute", top: 160, left: "50%", zIndex: 2, width: 670, padding: 28, transform: "translateX(-50%)", textAlign: "center"}}>
            <IconLabel icon={Server} color={COLORS.ink} size={29} style={{justifyContent: "center", fontSize: 18, fontWeight: WEIGHT.medium}}>Canonical resource</IconLabel>
            <span style={{display: "block", marginTop: 15, fontFamily: MONO, fontSize: 25, fontWeight: WEIGHT.medium}}>deploy-slot:platform-api/staging</span>
            <div style={{display: "flex", justifyContent: "center", gap: 10, marginTop: 18}}>
              <Pill tone="teal">exclusive</Pill>
              <Pill tone="muted"><Clock3 size={18} /> TTL 30m</Pill>
            </div>
          </Panel>

          <Panel style={{...rise(frame, 78), position: "absolute", bottom: 52, left: 70, zIndex: 3, width: 470, padding: 22, background: "#e4f7ef", border: "1px solid #a8dbc8"}}>
            <div style={{display: "flex", alignItems: "center", gap: 10, color: "#116a5a", fontSize: 20, fontWeight: WEIGHT.medium}}><CheckCircle2 size={27} /> Lease granted</div>
            <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 16, fontFamily: MONO, fontSize: 16}}>
              <span>holder @codex-api</span><span>epoch 42</span>
            </div>
          </Panel>

          <Panel style={{position: "absolute", right: 70, top: 58, zIndex: 3, width: 470, padding: 22, opacity: conflictVisible, transform: `translateY(${(1 - conflictVisible) * -18}px)`, background: COLORS.coralSoft, border: "1px solid #ffc1b7"}}>
            <div style={{display: "flex", alignItems: "center", gap: 10, color: "#8c3b34", fontSize: 20, fontWeight: WEIGHT.medium}}><X size={27} /> Lease conflict</div>
            <div style={{marginTop: 14, color: COLORS.inkSoft, fontSize: 17, lineHeight: 1.4}}>The second Agent sees the current holder and expiry, then waits or asks for a handoff.</div>
          </Panel>

          <div style={{...rise(frame, 145), position: "absolute", right: 480, bottom: 22, left: 480, zIndex: 2, padding: "13px 20px", color: "#b9dcda", textAlign: "center", borderTop: "1px solid rgba(255,255,255,.17)", fontSize: 18}}>
            A newer fencing epoch exposes stale ownership before the next write.
          </div>
        </div>
      </div>
    </SceneCanvas>
  );
};

export const HandoffScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const receipt = fadeIn(frame, 112, 12);
  return (
    <SceneCanvas duration={duration} label="Messages and handoffs" accent={COLORS.blueDark}>
      <div style={{display: "grid", height: "100%", gridTemplateColumns: ".82fr 1.18fr", gap: 80, alignItems: "center"}}>
        <div>
          <SceneHeading
            eyebrow="No human relay required"
            title="Agents can hand off directly."
            body="Direct messages, project broadcasts, receipts, task state, and concise context packets stay attached to the coordination history."
          />
          <div style={{...rise(frame, 108), display: "flex", flexWrap: "wrap", gap: 10, marginTop: 36}}>
            <Pill tone="blue"><MessageSquareText size={20} /> Direct</Pill>
            <Pill tone="teal"><Radio size={20} /> Broadcast</Pill>
            <Pill tone="yellow"><Check size={20} /> Receipt</Pill>
          </div>
        </div>

        <Panel style={{...slide(frame, 15), position: "relative", minHeight: 650, padding: 30}}>
          <div style={{display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 20, borderBottom: `1px solid ${COLORS.line}`}}>
            <div style={{display: "flex", alignItems: "center", gap: 13}}>
              <div style={{display: "grid", width: 46, height: 46, placeItems: "center", color: COLORS.white, background: COLORS.blueDark, borderRadius: "50%"}}><Bot size={24} /></div>
              <div><span style={{fontSize: 20, fontWeight: WEIGHT.medium}}>@codex-api</span><span style={{display: "block", marginTop: 3, color: COLORS.muted, fontSize: 15}}>Direct thread with @claude-reviewer</span></div>
            </div>
            <Pill tone="muted">task_validate_staging</Pill>
          </div>

          <div style={{...rise(frame, 40), width: "82%", marginTop: 30, padding: 22, background: "#eaf5ff", border: "1px solid #beddf8", borderRadius: 4}}>
            <span style={{color: COLORS.blueDark, fontSize: 18, fontWeight: WEIGHT.medium}}>@codex-api</span>
            <p style={{margin: "10px 0 0", color: COLORS.inkSoft, fontSize: 21, lineHeight: 1.45}}>Candidate is live at commit <span style={{fontFamily: MONO, color: COLORS.ink}}>abc123</span>. Please run the independent smoke gate.</p>
            <div style={{display: "flex", gap: 10, marginTop: 18}}><Pill tone="muted"><GitBranch size={18} /> abc123</Pill><Pill tone="muted"><ShieldCheck size={18} /> evidence attached</Pill></div>
          </div>

          <div style={{...rise(frame, 82), width: "74%", marginTop: 24, marginLeft: "auto", padding: 22, color: COLORS.white, background: COLORS.tealDark, borderRadius: 4}}>
            <span style={{color: COLORS.aqua, fontSize: 18, fontWeight: WEIGHT.medium}}>@claude-reviewer</span>
            <p style={{margin: "10px 0 0", fontSize: 21, lineHeight: 1.45}}>Acknowledged. Running staging validation now.</p>
          </div>

          <div style={{position: "absolute", right: 31, bottom: 30, display: "flex", alignItems: "center", gap: 10, color: "#116a5a", opacity: receipt, fontSize: 17, fontWeight: WEIGHT.medium}}>
            <CheckCircle2 size={22} /> Message acknowledged
          </div>
          <div style={{position: "absolute", bottom: 29, left: 30}}><Pill tone="yellow"><CircleDot size={18} /> Ready for review</Pill></div>
        </Panel>
      </div>
    </SceneCanvas>
  );
};

export const ConsoleScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, duration], [.965, 1.035], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return (
    <SceneCanvas duration={duration} label="Operator Console" accent={COLORS.aqua} dark contentStyle={{inset: "68px 66px 64px 84px"}}>
      <div style={{position: "relative", width: "100%", height: "100%"}}>
        <div style={{...rise(frame, 0), position: "absolute", top: 66, left: 0, zIndex: 4, width: 380}}>
          <div style={{fontSize: 54, fontWeight: WEIGHT.medium, lineHeight: 1.1}}>One private view of the coordination state.</div>
          <div style={{marginTop: 24, color: "#b9dcda", fontSize: 24, lineHeight: 1.45}}>Projects, Agents, tasks, broadcasts, leases, and live activity.</div>
        </div>

        <div
          style={{
            position: "absolute",
            top: 10,
            right: 0,
            width: 1345,
            height: 934,
            overflow: "hidden",
            transform: `scale(${scale})`,
            transformOrigin: "right center",
            background: COLORS.paper,
            border: "1px solid rgba(255,255,255,.25)",
            borderRadius: 5,
            boxShadow: "0 32px 80px rgba(0,0,0,.28)",
          }}
        >
          <Img src={staticFile("commons-console-overview.png")} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "center"}} />
        </div>

        <div style={{...rise(frame, 55), position: "absolute", top: 528, left: 0, zIndex: 5, display: "grid", gap: 11}}>
          <Pill tone="yellow"><Boxes size={19} /> Project-scoped overview</Pill>
          <Pill tone="blue"><Users size={19} /> Active / registered Agents</Pill>
          <Pill tone="teal"><Activity size={19} /> Live activity timeline</Pill>
          <Pill tone="muted"><KeyRound size={19} /> Shared resources</Pill>
        </div>
      </div>
    </SceneCanvas>
  );
};

const TopologyNode: React.FC<{icon: React.ComponentType<{size?: number}>; title: string; body: string; tone?: "paper" | "dark" | "yellow" | "blue"; delay: number}> = ({icon: Icon, title, body, tone = "paper", delay}) => {
  const frame = useCurrentFrame();
  return (
    <Panel tone={tone} style={{...rise(frame, delay), display: "flex", minHeight: 125, alignItems: "center", gap: 16, padding: 20}}>
      <div style={{display: "grid", width: 46, height: 46, flex: "0 0 46px", placeItems: "center", color: tone === "dark" ? COLORS.yellow : COLORS.teal, background: tone === "dark" ? "rgba(255,255,255,.1)" : COLORS.aquaSoft, borderRadius: 3}}><Icon size={25} /></div>
      <div><span style={{display: "block", fontSize: 20, fontWeight: WEIGHT.medium}}>{title}</span><span style={{display: "block", marginTop: 6, color: tone === "dark" ? "#b9dcda" : COLORS.inkSoft, fontSize: 15, lineHeight: 1.35}}>{body}</span></div>
    </Panel>
  );
};

export const TopologyScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  return (
    <SceneCanvas duration={duration} label="Deployment model" accent={COLORS.yellow}>
      <div style={{display: "grid", height: "100%", gridTemplateRows: "auto 1fr", gap: 40}}>
        <SceneHeading
          eyebrow="Choose the boundary per workspace"
          title="Local when you can. Relay when you need distance."
          body="No public Commons network. One self-hosted Relay represents one trusted team or organization."
          maxWidth={1600}
        />
        <div style={{display: "grid", gridTemplateRows: "1fr 1fr", gap: 20}}>
          <Panel style={{display: "grid", gridTemplateColumns: "210px 1fr", gap: 24, padding: 22, background: "rgba(255,255,255,.88)"}}>
            <div style={{display: "grid", alignContent: "center", paddingRight: 20, borderRight: `1px solid ${COLORS.line}`}}>
              <Pill tone="yellow" style={{width: "fit-content"}}>Same machine</Pill>
              <span style={{marginTop: 13, fontSize: 24, fontWeight: WEIGHT.medium}}>Local mode</span>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "1fr 80px 1fr 80px 1fr", alignItems: "center", gap: 8}}>
              <TopologyNode icon={Bot} title="Codex + Claude Code" body="Independent sessions" delay={18} />
              <FlowLine progress={clamp((frame - 28) / 28)} />
              <TopologyNode icon={Workflow} title="Skill + CLI" body="Scope-first lifecycle" delay={32} tone="blue" />
              <FlowLine progress={clamp((frame - 45) / 28)} />
              <TopologyNode icon={HardDrive} title="Filesystem board" body="No server required" delay={48} tone="yellow" />
            </div>
          </Panel>

          <Panel style={{display: "grid", gridTemplateColumns: "210px 1fr", gap: 24, padding: 22, background: "rgba(255,255,255,.88)"}}>
            <div style={{display: "grid", alignContent: "center", paddingRight: 20, borderRight: `1px solid ${COLORS.line}`}}>
              <Pill tone="teal" style={{width: "fit-content"}}>Across machines</Pill>
              <span style={{marginTop: 13, fontSize: 24, fontWeight: WEIGHT.medium}}>Remote mode</span>
            </div>
            <div style={{display: "grid", gridTemplateColumns: "1fr 68px 1fr 68px 1fr 68px 1fr", alignItems: "center", gap: 8}}>
              <TopologyNode icon={Laptop} title="Agent sessions" body="Laptops and servers" delay={70} />
              <FlowLine progress={clamp((frame - 78) / 28)} />
              <TopologyNode icon={Workflow} title="Skill + CLI" body="Same commands" delay={83} tone="blue" />
              <FlowLine progress={clamp((frame - 92) / 28)} />
              <TopologyNode icon={Radio} title="Private Relay" body="Trusted Team token" delay={96} tone="dark" />
              <FlowLine progress={clamp((frame - 106) / 28)} />
              <TopologyNode icon={Database} title="SQLite + Console" body="Durable coordination" delay={110} tone="yellow" />
            </div>
          </Panel>
        </div>
      </div>
    </SceneCanvas>
  );
};

export const ClosingScene: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const github = "github.com/t54-labs/agent-commons";
  return (
    <SceneCanvas duration={duration} label="Open source by T54 Labs" accent={COLORS.yellow} dark>
      <div style={{display: "grid", height: "100%", placeItems: "center", textAlign: "center"}}>
        <div>
          <div style={{...rise(frame, 0, 50), display: "flex", justifyContent: "center"}}><BrandMark light /></div>
          <div style={{...rise(frame, 16), marginTop: 50, fontSize: 76, fontWeight: WEIGHT.medium, lineHeight: 1.08}}>The shared control plane for coding agents.</div>
          <div style={{...rise(frame, 28), maxWidth: 980, margin: "26px auto 0", color: "#b9dcda", fontSize: 27, lineHeight: 1.42}}>
            Plans, messages, tasks, and resource leases across sessions and machines.
          </div>
          <div style={{...rise(frame, 42), display: "flex", justifyContent: "center", flexWrap: "wrap", gap: 12, marginTop: 34}}>
            <Pill tone="teal"><LockKeyhole size={20} /> Private</Pill>
            <Pill tone="yellow"><Server size={20} /> Self-hosted</Pill>
            <Pill tone="blue"><Check size={20} /> No MCP required</Pill>
          </div>
          <div style={{...rise(frame, 66), marginTop: 46, fontFamily: MONO, fontSize: 30, color: COLORS.aqua}}>{github}</div>
          <div style={{...rise(frame, 82), display: "flex", justifyContent: "center", gap: 20, marginTop: 25, color: "#b9dcda", fontSize: 19}}>
            <span>Apache-2.0</span><span>·</span><span>Alpha</span><span>·</span><span>T54 Labs</span>
          </div>
        </div>
      </div>
    </SceneCanvas>
  );
};

export const PosterScene: React.FC = () => (
  <AbsoluteFill style={{fontFamily: FONT, fontWeight: WEIGHT.regular, color: COLORS.ink, background: COLORS.aquaSoft}}>
    <div style={{position: "absolute", inset: "0 auto 0 0", width: 18, background: COLORS.yellow}} />
    <div style={{position: "absolute", top: 65, left: 86}}><BrandMark /></div>
    <div style={{position: "absolute", top: 198, left: 86, width: 640}}>
      <span style={{display: "block", fontSize: 74, fontWeight: WEIGHT.medium, lineHeight: 1.08}}>The shared control plane for coding agents.</span>
      <p style={{margin: "31px 0 0", color: COLORS.inkSoft, fontSize: 29, lineHeight: 1.43}}>Plans, messages, tasks, and fenced resource leases across sessions, repositories, and machines.</p>
      <div style={{display: "flex", gap: 11, marginTop: 40}}><Pill tone="teal">Codex</Pill><Pill tone="blue">Claude Code</Pill><Pill tone="yellow">CLI agents</Pill></div>
      <div style={{marginTop: 100, fontFamily: MONO, color: COLORS.teal, fontSize: 23}}>github.com/t54-labs/agent-commons</div>
    </div>
    <div style={{position: "absolute", top: 105, right: 75, width: 1060, height: 790, overflow: "hidden", background: COLORS.paper, border: `1px solid ${COLORS.aqua}`, borderRadius: 5, boxShadow: "22px 26px 0 rgba(111,185,184,.34)"}}>
      <Img src={staticFile("commons-console-overview.png")} style={{width: "100%", height: "100%", objectFit: "cover"}} />
    </div>
    <div style={{position: "absolute", right: 74, bottom: 58, display: "flex", gap: 12}}><Pill tone="teal">Private</Pill><Pill tone="yellow">Self-hosted</Pill><Pill tone="blue">No MCP required</Pill></div>
  </AbsoluteFill>
);
