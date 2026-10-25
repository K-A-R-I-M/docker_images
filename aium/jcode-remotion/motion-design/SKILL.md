---
name: motion-design
description: Build deterministic 2D historical motion graphics with React, TypeScript, Remotion and SVG. Use when creating or editing historical map animations, territory changes, army movements, timelines, documentary titles, or any Remotion video in a historical project. Covers data provenance, component contracts, camera movement, and MP4 export verification. Do not use for generic web animation.
---

# Historical Motion Graphics

A construction skill for cinematic, evidence-based historical videos built
entirely from code. Remotion renders every frame deterministically. Historical
data is separate from presentation and every visible claim is traceable.

Companion file: `TEMPLATES.md` holds copy-paste configuration, helpers, data
types, and the seven required components. Read it before writing components.

## Initial response

When this skill is invoked without a specific brief, respond with:

> I will not invent historical facts or map borders. Send me the period, the
> claim, the region, and the sources you have. I will model the data first, then
> build the Remotion scenes.

If the user gives a brief but no sources, complete Step 1 of the workflow before
writing any component code.

## Scope

Use this skill for:

- Historical map animation, borders, campaigns, trade routes, migrations.
- Chronologies, timelines, era transitions, date-driven reveals.
- Documentary title cards, lower thirds, event callouts.
- Assembling these into one 1920x1080, 30 FPS Remotion composition.

Do not use it for live-action editing, generic UI motion, or anything generated
by an external AI video service. Those are out of scope by rule, not by taste.

## Non-negotiables

| Rule | Test you must pass |
|---|---|
| Code only | Every pixel is produced by React, CSS, or SVG in this repo. No external generated video, stock footage, or image sequences used as animation. |
| Deterministic | Same props and frame produce the same output on every machine and every render. No wall clock, no unseeded randomness, no CSS transitions. |
| Data before pixels | Every date, place, border, arrow, and label exists in a typed data file with at least one source id. |
| No invented history | No guessed borders, no guessed dates, no guessed army routes, no invented quotes. Missing data is shown as missing or omitted. |
| Uncertainty is visible | Approximate, disputed, schematic, and unverified data is labeled on screen, not buried in a comment. |
| Reuse | Videos compose the shared components. A new video is a data file plus a timeline, not a copy of another video. |
| Cheap dependencies | Use Remotion, React, and SVG first. Add a package only when it replaces real complexity. |
| Verify before done | Typecheck, bundle, list compositions, render a still, render the MP4, probe the output. |

If a request conflicts with the history rules, say so and offer the closest
honest version. Do not quietly fabricate.

## Workflow

### 1. Write the historical brief

Before code, produce this block in the project or in your response:

```text
Period:
Thesis (one sentence):
Region and extent:
Key dates:
Actors and polities:
Claims that need a source:
Source list (id, citation, URL or archive, accessed date):
Known gaps and disputed points:
```

Every claim that appears on screen needs an entry in the source list. If the
user cannot supply sources, ask once. If they approve approximations, mark them
`unverified` and render the uncertainty notice. Never upgrade an approximation
to fact because it looks better.

### 2. Model the data

Create `src/data/<period>/` with:

- `sources.ts`: citation records, no prose from memory.
- `events.ts`: typed events with `sortYear`, `yearLabel`, and source ids.
- `territories.geo.json` or `territories.ts`: real GeoJSON coordinates.
- `armies.ts`: routes, only at the precision the source supports.
- `index.ts`: one exported `EraData` object consumed by the video.

Use null for unknown values. Never interpolate a missing date or coordinate.
Run `npm run typecheck` after this step. Data errors are cheaper here than in a
render.

### 3. Build a still frame

Compose the hardest frame first: the densest map plus its labels. Register the
composition, run the Studio, and judge hierarchy, contrast, and label collisions
at 100 percent zoom. Do not animate a layout that does not work standing still.

### 4. Animate in beats

Add motion in this order: map reveal, territory change, route, timeline,
event callout, title and camera. Each beat gets its own `Sequence`. Keep one
idea moving at a time. A camera move can run underneath, but it must be slow
enough to read as a camera, not a zoom effect.

### 5. Verify and export

Run the full verification block below. A composition that previews is not done.
A composition that typechecks, bundles, renders, and probes correctly is done.

## Project layout

```text
historical-video/
  package.json
  tsconfig.json
  remotion.config.ts
  public/
    geo/                 # raw, licensed source geometry
    fonts/               # licensed local fonts, optional
  src/
    index.ts             # registerRoot
    Root.tsx             # Composition registry
    theme.ts             # colors, type scale, spacing, motion tokens
    lib/
      animation.ts       # seconds, ramp, enter, exit, stagger
      geo.ts             # projection, fit, GeoJSON path, point along line
      format.ts          # year labels, circa, ranges
    data/
      types.ts           # provenance-aware data contract
      <period>/
        sources.ts
        events.ts
        territories.geo.json
        armies.ts
        index.ts
    components/
      HistoricalMap.tsx
      Territory.tsx
      ArmyMovement.tsx
      Timeline.tsx
      HistoricalEvent.tsx
      CameraMovement.tsx
      AnimatedTitle.tsx
      DataNotice.tsx
    videos/
      <VideoName>.tsx
  out/                   # renders, gitignored
```

Keep `src/data` free of JSX. Keep `src/components` free of specific historical
facts. A component receives data. It never imports a period.

## Dependencies

Minimal set:

```bash
npm install remotion react react-dom
npm install -D @remotion/cli typescript @types/react @types/react-dom
```

Optional, only when the project already ships local font files:

```bash
npm install @remotion/fonts
```

Do not add charting, mapping, animation, or state libraries. SVG and
`interpolate()` cover this work. GeoJSON is read as data, not rendered through a
map library.

## Composition contract

Every video composition is exactly:

- 1920 x 1080
- 30 FPS
- duration in frames computed from seconds, never hand-typed

```tsx
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;
const seconds = (s: number) => Math.round(s * FPS);

<Composition
  id="FallOfConstantinople"
  component={FallOfConstantinople}
  durationInFrames={seconds(95)}
  fps={FPS}
  width={WIDTH}
  height={HEIGHT}
/>
```

Rules:

- `durationInFrames` must equal the final beat end plus the tail hold.
- The last visible element must be fully readable for at least 45 frames.
- Every `Sequence` uses `durationInFrames` explicitly, not open-ended timing.
- Overlay typography sits outside the camera transform so text stays crisp.
- One composition per video. Shared scenes are components, not compositions.

## Visual system

### Palette

Dark documentary base, parchment accents, muted territory fills. Pure black and
pure white are forbidden. They crush detail and look digital.

| Token | Value | Use |
|---|---|---|
| `bg` | `#0A0D12` | base background |
| `bgAlt` | `#121821` | panels, vignette center |
| `parchment` | `#E7D9BC` | primary light text, map land |
| `parchmentDim` | `#C9B993` | secondary text |
| `ink` | `#1B1710` | text on parchment |
| `gold` | `#C9A227` | dates, rules, active marks |
| `goldBright` | `#E8C766` | playhead, emphasis |
| `text` | `#F2EAD8` | body copy |
| `textMuted` | `#A89C86` | captions, sources |
| `disputed` | `#B4553F` | disputed borders and warnings |
| `territoryA` | `#3E5C76` | fill 1 |
| `territoryB` | `#6B4F3A` | fill 2 |
| `territoryC` | `#5C6B4A` | fill 3 |
| `territoryD` | `#7A4E4E` | fill 4 |
| `grid` | `#2A3140` | graticule at 40 percent opacity |

### Typography

One display serif, one sans for body, one mono for dates and data. Load local
fonts from `public/fonts` with `@remotion/fonts`, or fall back to a stack that
exists in the render container.

```ts
display: '"Cormorant Garamond", Georgia, "Times New Roman", serif'
body: 'Inter, system-ui, "DejaVu Sans", sans-serif'
data: '"IBM Plex Mono", ui-monospace, "DejaVu Sans Mono", monospace'
```

Type scale at 1080p. Nothing below 18 px.

| Role | Size | Weight | Tracking |
|---|---|---|---|
| Title | 96 | 600 | 0.01em |
| Chapter | 64 | 600 | 0.02em |
| Subtitle | 30 | 400 | 0.04em |
| Body | 28 | 400 | 0.01em |
| Map label | 24 | 500 | 0.08em, uppercase |
| Caption | 22 | 400 | 0.02em |
| Source | 18 | 400 | 0.01em |

Safe area is 96 px on all sides. Map labels may enter the margin only when the
leader line still has 24 px of breathing room.

### Texture

- Parchment and grain are static SVG filters or gradients. Never animate noise.
- `feTurbulence` baseFrequency around 0.8, opacity 0.04 to 0.07.
- Vignette is a radial gradient, transparent center to 45 percent dark edges.
- Map land can use a subtle paper fill, but borders must stay the highest
  contrast line on the map.

### Motion tokens

At 30 FPS:

| Motion | Frames | Seconds |
|---|---|---|
| Micro feedback | 9 to 12 | 0.3 to 0.4 |
| Standard enter | 18 to 24 | 0.6 to 0.8 |
| Title reveal | 30 to 45 | 1.0 to 1.5 |
| Map or territory reveal | 45 to 75 | 1.5 to 2.5 |
| Camera move | 180 to 420 | 6 to 14 |
| Minimum hold | 45 | 1.5 |

Springs are allowed, bounce is not. Use `{damping: 200}` for anything
informational. Use `{damping: 30, stiffness: 90}` for a barely perceptible
settle. Reserve visible overshoot for a single moving marker, never for text or
borders.

All `interpolate()` calls clamp both ends unless wrapping is the point:

```ts
interpolate(frame, [start, start + duration], [0, 1], {
  extrapolateLeft: 'clamp',
  extrapolateRight: 'clamp',
})
```

## Component contracts

Detailed implementations are in `TEMPLATES.md`. These are the stable APIs and
the rules each component must enforce.

### HistoricalMap

Owns the SVG viewport, projection, background, and optional graticule.

```ts
type HistoricalMapProps = {
  project: Projection;
  children: React.ReactNode;
  background?: 'dark' | 'parchment';
  graticule?: boolean;
};
```

- Renders `<svg viewBox="0 0 1920 1080">` filling the composition.
- Draws only geometry present in the data. No decorative coastlines, no
  remembered borders.
- Land and water derive from supplied geometry or a supplied basemap. If no
  basemap is licensed, use the dark background and the territories alone.
- The projection is computed once with `createFit()` from `lib/geo.ts` and passed
  down. Children never recompute bounds independently.

### Territory

```ts
type TerritoryProps = {
  id: string;
  geometry: GeoGeometry;
  project: Projection;
  fill?: string;
  name?: string;
  disputed?: boolean;
  revealAt?: number;
  revealDuration?: number;
  labelAt?: { x: number; y: number };
};
```

- Border draws with `pathLength={1}`, `strokeDasharray={1}`, and animated
  `strokeDashoffset`. Fill fades in after the border is 60 percent drawn.
- Disputed geometry uses a dashed stroke and a hatched pattern, plus a visible
  legend entry. A disputed border is never rendered identically to a confirmed
  one.
- Labels appear only when `name` and a source-backed `labelAt` exist. The
  component does not compute a "nice" label position from a bounding box if that
  would place a label on water or on top of another label.
- Geometry is never simplified at render time in a way that changes a border.
  Simplify upstream, from the source data, and document the tolerance.

### ArmyMovement

```ts
type ArmyMovementProps = {
  id: string;
  path: Array<[number, number]>;
  project: Projection;
  start: number;
  duration: number;
  color?: string;
  label?: string;
  dashed?: boolean;
  confidence: 'verified' | 'approximate' | 'schematic';
};
```

- The path is projected points, not a hand-drawn SVG path. Its length and the
  marker position come from the same projected points.
- `strokeDashoffset` reveals the route. The marker uses `pointAtProgress()` so
  trail and marker cannot drift apart.
- If the source gives only endpoints, the route is `schematic`: dashed line,
  curved arrow, and an on-screen "schematic route" notice. Never imply a precise
  march route that the source does not support.
- Arrowheads are `marker-end` with `orient="auto"`. Do not rotate a separate
  arrow element with a second interpolation.

### Timeline

```ts
type TimelineProps = {
  startYear: number;
  endYear: number;
  events: HistoricalEventData[];
  playheadYear: number;
  accent?: string;
};
```

- Uses `sortYear` for position and `yearLabel` for display. BCE years are stored
  as negative numbers with no year zero, and the formatter handles the label.
- Tick step is chosen from 1, 2, 5, 10, 25, 50, 100, 250, 500 so that ticks are
  at least 120 px apart.
- Event labels alternate above and below the line. If a label would be closer
  than 140 px to the previous label on the same side, drop it and keep the dot.
  Never shrink below 18 px to make it fit.
- Playhead position is a clamped interpolation over the visible year range. It
  never overshoots the track.

### HistoricalEvent

```ts
type HistoricalEventProps = {
  event: HistoricalEventData;
  variant?: 'callout' | 'lower-third';
  align?: 'left' | 'right' | 'center';
  sourceLabel?: string;
};
```

- Shows `yearLabel`, title, and a summary of at most two lines.
- `circa`, `approximate`, `disputed`, and `unverified` render as visible chips
  or prefixes. They are not hidden in metadata.
- The source line is always present when the event is on screen for more than
  90 frames.
- Entrance is opacity plus 12 to 18 px of vertical travel over 18 frames.
  No scale from zero, no letter-by-letter typewriter.

### CameraMovement

```ts
type CameraMovementProps = {
  children: React.ReactNode;
  from: { x: number; y: number; scale: number };
  to: { x: number; y: number; scale: number };
  start: number;
  duration: number;
};
```

- `x` and `y` are the composition-space point that should sit at the center of
  frame, in pixels.
- Transform is `translate(960 - focusX * scale, 540 - focusY * scale) scale(s)`
  with `transformOrigin: '0 0'`.
- Scale range is 1.0 to 1.12. More than that reads as a crash zoom, not a
  camera.
- The map layer may overscan by 8 percent so edges never show during a move.
- Overlay text, titles, and source notes live outside this component.

### AnimatedTitle

```ts
type AnimatedTitleProps = {
  title: string;
  subtitle?: string;
  kicker?: string;
  start?: number;
  duration?: number;
  align?: 'left' | 'center';
};
```

- Reveal is a clip-path wipe from left to right over 30 to 45 frames, or a
  simple opacity and 16 px rise. Pick one per video, not both.
- Kicker enters first, then title, then subtitle, with 6 to 10 frame offsets.
- Title stays fully readable for at least 45 frames. If the composition cannot
  afford that, shorten the copy, not the hold.
- No per-character animation. No glow. A thin gold rule is sufficient emphasis.

### DataNotice

```ts
type DataNoticeProps = {
  text: string;
  tone?: 'neutral' | 'warning';
};
```

Bottom-left, 18 to 20 px, muted text on a semi-transparent dark plate. Used for
"schematic route", "border approximate", "dates uncertain", and "no source
available". A warning notice appears for the duration of the uncertain element,
not only at the end.

## Data contract

Put this in `src/data/types.ts`, then extend only when a real source requires it.

```ts
export type Confidence =
  | 'verified'
  | 'approximate'
  | 'disputed'
  | 'schematic'
  | 'unverified';

export type SourceRef = {
  id: string;
  citation: string;
  url?: string;
  accessed?: string;
};

export type HistoricalEventData = {
  id: string;
  sortYear: number;
  yearLabel: string;
  title: string;
  summary: string;
  confidence: Confidence;
  sourceIds: string[];
  place?: [number, number];
};

export type TerritoryData = {
  id: string;
  name?: string;
  geometry: GeoGeometry;
  validFrom?: number;
  validTo?: number;
  confidence: Confidence;
  sourceIds: string[];
  fillToken?: string;
};

export type ArmyData = {
  id: string;
  label?: string;
  path: Array<[number, number]>;
  startYear?: number;
  endYear?: number;
  confidence: Confidence;
  sourceIds: string[];
  dashed?: boolean;
};
```

Provenance rules:

1. `sourceIds` is never empty for anything visible.
2. `confidence: 'unverified'` renders a visible notice and cannot be styled as
   confirmed.
3. A missing year is `undefined`, not `0`. A missing place is absent, not
   `[0, 0]`. Null Island is a bug.
4. Source citations live in data. Components receive a `sourceLabel` string, not
   a hard-coded citation.
5. If two sources disagree, model both or choose one and mark it `disputed`.
   Do not average borders.
6. Map geometry must come from a licensed dataset or a user-provided file. Its
   license and simplification tolerance are recorded next to the file.

## Determinism

Banned inside render paths:

| Banned | Use instead |
|---|---|
| `Date.now()`, `new Date()` | `useCurrentFrame()` and static ISO strings parsed once at module load |
| `Math.random()` | `random(seed)` from Remotion with a literal seed, or precomputed data |
| CSS `transition`, `animation`, `@keyframes` | `interpolate()` and `spring()` |
| `requestAnimationFrame`, timers | frame-derived values |
| Fetching data in a component | static imports or `calculateMetadata()` |
| Unseeded layout measurement | fixed layout tokens, or `delayRender()` plus `continueRender()` for fonts |

Data loading is static. A video must render offline, with no network access.

## Verification

These commands are the definition of done. Run them from the project root.

```bash
npm run typecheck
npx remotion bundle src/index.ts
npx remotion compositions src/index.ts
npx remotion still src/index.ts <CompositionId> out/<CompositionId>-poster.png --frame=90
npx remotion render src/index.ts <CompositionId> out/<CompositionId>.mp4
npx remotion ffprobe out/<CompositionId>.mp4
```

Checklist:

- `typecheck` exits 0 with no `any` added to silence data errors.
- `bundle` succeeds. A Studio preview alone is not a build.
- `compositions` lists the video with width 1920, height 1080, fps 30, and the
  expected duration.
- The still shows correct hierarchy, no clipped text, no label collisions, and
  every uncertainty notice that should be present.
- The MP4 plays, starts on the intended frame, and ends on the tail hold.
- `ffprobe` reports 1920x1080, 30/1 frame rate, h264, and the expected duration
  within one frame.
- A second render of the same frame is pixel-identical or visually identical.
  If not, find the wall clock or unseeded random value.
- No console errors in the Studio and no missing-font warnings in the render log.

Container notes:

- The image sets `REMOTION_BROWSER_EXECUTABLE=/usr/bin/chromium`. If Chromium is
  absent, run `npx remotion browser ensure` instead of downloading a browser
  implicitly.
- If a render fails on shared libraries, install Chromium's runtime
  dependencies. Do not switch to Alpine.
- Rendering as root in a container may require a no-sandbox launch. Prefer the
  image's Chromium setup and document any extra Chromium flags in the project.
- Use `--concurrency` no higher than available CPUs. Parallel encoding is fine
  for short videos, disable it if memory is tight.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Border looks wrong | geometry remembered or hand-drawn | replace with sourced GeoJSON or omit |
| Dates feel invented | BCE handling or guessed month | store `sortYear` and `yearLabel`, use `c.` |
| Route implies precision | endpoints drawn as a confident line | dashed schematic plus notice |
| Motion feels cheap | scale from zero, bounce on text, too many simultaneous moves | opacity plus small travel, one beat at a time |
| Text unreadable | labels below 18 px or over busy fill | raise contrast, add plate, drop label |
| Render differs each run | `Date.now`, `Math.random`, CSS animation | frame-derived, seeded, static |
| Preview fine, export broken | no bundle or font failure | run the verification block |
| Camera makes text soft | camera transform wraps text | move overlays outside the camera layer |

## Final report

When the video is complete, report:

- Composition id and output path.
- Duration, resolution, and FPS as probed from the MP4.
- Files added or changed.
- Source ids used and any `unverified`, `approximate`, `disputed`, or
  `schematic` element shown on screen.
- Commands run and their results, including the bundle and ffprobe evidence.
- Anything the user still needs to supply, especially sources or licensed
  geometry.

Do not claim the video is historically accurate. Claim only that every visible
claim is sourced or labeled, and that the render was verified.
