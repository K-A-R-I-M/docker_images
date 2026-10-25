# Templates

Copy these into a new Remotion project, then replace the demo data. Every
component is deterministic and depends only on Remotion, React, and SVG.

## package.json

```json
{
  "name": "historical-motion",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "studio": "remotion studio src/index.ts",
    "typecheck": "tsc --noEmit",
    "build": "npm run typecheck && remotion bundle src/index.ts",
    "render": "remotion render src/index.ts",
    "still": "remotion still src/index.ts"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "remotion": "^4.0.0"
  },
  "devDependencies": {
    "@remotion/cli": "^4.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.6.0"
  }
}
```

## tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true,
    "resolveJsonModule": true,
    "lib": ["ES2020", "DOM"]
  },
  "include": ["src", "remotion.config.ts"]
}
```

## remotion.config.ts

```ts
import {Config} from '@remotion/cli/config';

Config.setEntryPoint('./src/index.ts');
Config.setVideoImageFormat('png');
Config.setOverwriteOutput(true);
Config.setChromiumOpenGlRenderer('swangle');
Config.setConcurrency(4);
```

`swangle` keeps software rendering consistent across machines. Raise
`concurrency` only up to the CPU count.

## src/theme.ts

```ts
export const theme = {
  colors: {
    bg: '#0A0D12',
    bgAlt: '#121821',
    parchment: '#E7D9BC',
    parchmentDim: '#C9B993',
    ink: '#1B1710',
    gold: '#C9A227',
    goldBright: '#E8C766',
    text: '#F2EAD8',
    textMuted: '#A89C86',
    disputed: '#B4553F',
    territoryA: '#3E5C76',
    territoryB: '#6B4F3A',
    territoryC: '#5C6B4A',
    territoryD: '#7A4E4E',
    grid: '#2A3140',
  },
  font: {
    display: '"Cormorant Garamond", Georgia, "Times New Roman", serif',
    body: 'Inter, system-ui, "DejaVu Sans", sans-serif',
    data: '"IBM Plex Mono", ui-monospace, "DejaVu Sans Mono", monospace',
  },
  size: {
    title: 96,
    chapter: 64,
    subtitle: 30,
    body: 28,
    label: 24,
    caption: 22,
    source: 18,
  },
  margin: 96,
} as const;

export type TerritoryFill =
  | 'territoryA'
  | 'territoryB'
  | 'territoryC'
  | 'territoryD';
```

## src/lib/animation.ts

```ts
import {Easing, interpolate, spring} from 'remotion';

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export const seconds = (value: number) => Math.round(value * FPS);

export const clamp = (value: number, min = 0, max = 1) =>
  Math.min(max, Math.max(min, value));

export const ramp = ({
  frame,
  start,
  duration,
  from = 0,
  to = 1,
  easing = Easing.inOut(Easing.cubic),
}: {
  frame: number;
  start: number;
  duration: number;
  from?: number;
  to?: number;
  easing?: (input: number) => number;
}) =>
  interpolate(frame, [start, start + duration], [from, to], {
    easing,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

export const settle = ({
  frame,
  fps,
  delay = 0,
  duration,
}: {
  frame: number;
  fps: number;
  delay?: number;
  duration: number;
}) =>
  spring({
    frame: Math.max(0, frame - delay),
    fps,
    durationInFrames: duration,
    config: {damping: 200},
  });

export const stagger = (index: number, step = 6) => index * step;
```

## src/lib/format.ts

```ts
import {clamp} from './animation';

export const formatYear = (sortYear: number, approximate = false) => {
  if (sortYear === 0) {
    throw new Error('Historical years have no zero. Use -1 for 1 BCE.');
  }

  const label =
    sortYear < 0 ? `${Math.abs(sortYear)} BCE` : `${sortYear} CE`;

  return approximate ? `c. ${label}` : label;
};

export const yearProgress = (
  year: number,
  startYear: number,
  endYear: number,
) => clamp((year - startYear) / (endYear - startYear));

export const formatRange = (startYear: number, endYear: number) =>
  `${formatYear(startYear)} - ${formatYear(endYear)}`;
```

## src/lib/geo.ts

```ts
export type Position = readonly [number, number];
export type Projection = (position: Position) => [number, number];

export type Box = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type GeoGeometry =
  | {type: 'Polygon'; coordinates: Position[][]}
  | {type: 'MultiPolygon'; coordinates: Position[][][]};

const MAX_MERCATOR_LAT = 85.05112878;

export const projectMercator = ([lon, lat]: Position): [number, number] => {
  const safeLat = Math.min(
    MAX_MERCATOR_LAT,
    Math.max(-MAX_MERCATOR_LAT, lat),
  );
  const x = (lon + 180) / 360;
  const y =
    (1 -
      Math.log(
        Math.tan(Math.PI / 4 + (safeLat * Math.PI) / 360),
      ) /
        Math.PI) /
    2;

  return [x, y];
};

export const collectPositions = (
  geometries: GeoGeometry[],
): Position[] => {
  const output: Position[] = [];

  for (const geometry of geometries) {
    if (geometry.type === 'Polygon') {
      for (const ring of geometry.coordinates) {
        output.push(...ring);
      }
    } else {
      for (const polygon of geometry.coordinates) {
        for (const ring of polygon) {
          output.push(...ring);
        }
      }
    }
  }

  return output;
};

export const createFit = (
  positions: Position[],
  box: Box,
  project: (position: Position) => [number, number] = projectMercator,
): Projection => {
  if (positions.length === 0) {
    throw new Error('createFit() needs at least one position.');
  }

  const projected = positions.map(project);
  const xs = projected.map(([x]) => x);
  const ys = projected.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 1e-9);
  const spanY = Math.max(maxY - minY, 1e-9);
  const scale = Math.min(box.width / spanX, box.height / spanY);
  const offsetX = box.x + (box.width - spanX * scale) / 2 - minX * scale;
  const offsetY = box.y + (box.height - spanY * scale) / 2 - minY * scale;

  return (position) => {
    const [x, y] = project(position);
    return [x * scale + offsetX, y * scale + offsetY];
  };
};

const ringToPath = (ring: Position[], project: Projection) =>
  ring
    .map((position, index) => {
      const [x, y] = project(position);
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ') + ' Z';

export const geometryToPath = (
  geometry: GeoGeometry,
  project: Projection,
) => {
  if (geometry.type === 'Polygon') {
    return geometry.coordinates
      .map((ring) => ringToPath(ring, project))
      .join(' ');
  }

  return geometry.coordinates
    .flatMap((polygon) =>
      polygon.map((ring) => ringToPath(ring, project)),
    )
    .join(' ');
};

export const polylineToPath = (
  points: Array<[number, number]>,
) =>
  points
    .map(
      ([x, y], index) =>
        `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`,
    )
    .join(' ');

export const polylineLength = (points: Array<[number, number]>) => {
  let total = 0;

  for (let index = 1; index < points.length; index += 1) {
    const [x1, y1] = points[index - 1];
    const [x2, y2] = points[index];
    total += Math.hypot(x2 - x1, y2 - y1);
  }

  return total;
};

export const pointAtProgress = (
  points: Array<[number, number]>,
  progress: number,
) => {
  if (points.length === 0) {
    return {x: 0, y: 0, angle: 0};
  }

  if (points.length === 1) {
    return {x: points[0][0], y: points[0][1], angle: 0};
  }

  const total = polylineLength(points);
  const target = Math.min(1, Math.max(0, progress)) * total;
  let travelled = 0;

  for (let index = 1; index < points.length; index += 1) {
    const [x1, y1] = points[index - 1];
    const [x2, y2] = points[index];
    const segment = Math.hypot(x2 - x1, y2 - y1);
    const isLast = index === points.length - 1;

    if (travelled + segment >= target || isLast) {
      const local = segment === 0 ? 0 : (target - travelled) / segment;
      return {
        x: x1 + (x2 - x1) * local,
        y: y1 + (y2 - y1) * local,
        angle: (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI,
      };
    }

    travelled += segment;
  }

  return {x: 0, y: 0, angle: 0};
};
```

## src/data/types.ts

```ts
import type {GeoGeometry} from '../lib/geo';

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
  fillToken?: 'territoryA' | 'territoryB' | 'territoryC' | 'territoryD';
  labelAt?: {x: number; y: number};
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

export type EraData = {
  id: string;
  title: string;
  subtitle: string;
  startYear: number;
  endYear: number;
  sources: SourceRef[];
  events: HistoricalEventData[];
  territories: TerritoryData[];
  armies: ArmyData[];
};
```

## src/index.ts

```ts
import {registerRoot} from 'remotion';
import {RemotionRoot} from './Root';

registerRoot(RemotionRoot);
```

## src/Root.tsx

```tsx
import React from 'react';
import {Composition} from 'remotion';
import {FPS, HEIGHT, WIDTH, seconds} from './lib/animation';
import {HistoricalDemo} from './videos/HistoricalDemo';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="HistoricalDemo"
    component={HistoricalDemo}
    durationInFrames={seconds(30)}
    fps={FPS}
    width={WIDTH}
    height={HEIGHT}
  />
);
```

## src/components/HistoricalMap.tsx

```tsx
import React from 'react';
import {AbsoluteFill} from 'remotion';
import type {Projection} from '../lib/geo';
import {theme} from '../theme';

type HistoricalMapProps = {
  project: Projection;
  children: React.ReactNode;
  background?: 'dark' | 'parchment';
  graticule?: boolean;
};

const Graticule: React.FC<{project: Projection}> = ({project}) => {
  const lines: React.ReactNode[] = [];

  for (let lon = -180; lon <= 180; lon += 30) {
    const points: string[] = [];
    for (let lat = -80; lat <= 80; lat += 5) {
      const [x, y] = project([lon, lat]);
      points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    lines.push(
      <polyline
        key={`lon-${lon}`}
        points={points.join(' ')}
        fill="none"
        stroke={theme.colors.grid}
        strokeWidth={1}
        opacity={0.45}
      />,
    );
  }

  for (let lat = -60; lat <= 80; lat += 30) {
    const points: string[] = [];
    for (let lon = -180; lon <= 180; lon += 5) {
      const [x, y] = project([lon, lat]);
      points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    lines.push(
      <polyline
        key={`lat-${lat}`}
        points={points.join(' ')}
        fill="none"
        stroke={theme.colors.grid}
        strokeWidth={1}
        opacity={0.45}
      />,
    );
  }

  return <g>{lines}</g>;
};

export const HistoricalMap: React.FC<HistoricalMapProps> = ({
  project,
  children,
  background = 'dark',
  graticule = false,
}) => (
  <AbsoluteFill
    style={{
      backgroundColor:
        background === 'dark' ? theme.colors.bg : theme.colors.parchment,
    }}
  >
    <svg
      viewBox="0 0 1920 1080"
      width={1920}
      height={1080}
      style={{position: 'absolute', inset: 0}}
    >
      {graticule ? <Graticule project={project} /> : null}
      {children}
    </svg>
  </AbsoluteFill>
);
```

## src/components/Territory.tsx

```tsx
import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {geometryToPath} from '../lib/geo';
import type {GeoGeometry, Projection} from '../lib/geo';
import {theme} from '../theme';

type TerritoryProps = {
  id: string;
  geometry: GeoGeometry;
  project: Projection;
  name?: string;
  fill?: string;
  disputed?: boolean;
  revealAt?: number;
  revealDuration?: number;
  labelAt?: {x: number; y: number};
};

export const Territory: React.FC<TerritoryProps> = ({
  id,
  geometry,
  project,
  name,
  fill = theme.colors.territoryA,
  disputed = false,
  revealAt = 0,
  revealDuration = 48,
  labelAt,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = spring({
    frame: Math.max(0, frame - revealAt),
    fps,
    durationInFrames: revealDuration,
    config: {damping: 200},
  });
  const fillOpacity = interpolate(progress, [0.6, 1], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const path = geometryToPath(geometry, project);
  const hatchId = `hatch-${id}`;
  const stroke = disputed ? theme.colors.disputed : theme.colors.parchmentDim;

  return (
    <g>
      {disputed ? (
        <defs>
          <pattern
            id={hatchId}
            width={12}
            height={12}
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(35)"
          >
            <line
              x1={0}
              y1={0}
              x2={0}
              y2={12}
              stroke={theme.colors.disputed}
              strokeWidth={2}
              opacity={0.55}
            />
          </pattern>
        </defs>
      ) : null}

      {disputed ? (
        <path
          d={path}
          fill={`url(#${hatchId})`}
          fillRule="evenodd"
          opacity={fillOpacity * 0.45}
        />
      ) : null}

      <path
        d={path}
        fill={fill}
        fillRule="evenodd"
        opacity={fillOpacity}
      />

      {disputed ? (
        <path
          d={path}
          fill="none"
          stroke={stroke}
          strokeWidth={2.5}
          strokeDasharray="10 7"
          opacity={progress}
        />
      ) : (
        <path
          d={path}
          fill="none"
          stroke={stroke}
          strokeWidth={2}
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={1 - progress}
        />
      )}

      {name && labelAt && progress > 0.7 ? (
        <text
          x={labelAt.x}
          y={labelAt.y}
          fill={theme.colors.text}
          fontFamily={theme.font.data}
          fontSize={theme.size.label}
          fontWeight={500}
          letterSpacing="0.08em"
          textAnchor="middle"
          opacity={fillOpacity}
        >
          {name.toUpperCase()}
        </text>
      ) : null}
    </g>
  );
};
```

## src/components/ArmyMovement.tsx

```tsx
import React, {useMemo} from 'react';
import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {
  pointAtProgress,
  polylineLength,
  polylineToPath,
} from '../lib/geo';
import type {Projection} from '../lib/geo';
import {theme} from '../theme';

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

export const ArmyMovement: React.FC<ArmyMovementProps> = ({
  id,
  path,
  project,
  start,
  duration,
  color = theme.colors.goldBright,
  label,
  dashed = false,
  confidence,
}) => {
  const frame = useCurrentFrame();
  const points = useMemo(
    () => path.map((position) => project(position)),
    [path, project],
  );
  const route = useMemo(() => polylineToPath(points), [points]);
  const total = useMemo(() => polylineLength(points), [points]);
  const progress = interpolate(frame, [start, start + duration], [0, 1], {
    easing: Easing.inOut(Easing.quad),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const head = pointAtProgress(points, progress);
  const isSchematic = dashed || confidence === 'schematic';

  return (
    <g opacity={progress > 0 ? 1 : 0}>
      <path
        d={route}
        fill="none"
        stroke={color}
        strokeWidth={12}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.12}
      />

      {isSchematic ? (
        <path
          d={route}
          fill="none"
          stroke={color}
          strokeWidth={3}
          strokeDasharray="10 8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : (
        <path
          d={route}
          fill="none"
          stroke={color}
          strokeWidth={3}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={total}
          strokeDashoffset={total * (1 - progress)}
        />
      )}

      <g
        transform={`translate(${head.x.toFixed(2)} ${head.y.toFixed(
          2,
        )}) rotate(${head.angle.toFixed(2)})`}
      >
        <path d="M -10 -7 L 12 0 L -10 7 Z" fill={color} />
      </g>

      {label ? (
        <text
          x={head.x + 18}
          y={head.y - 18}
          fill={theme.colors.text}
          fontFamily={theme.font.data}
          fontSize={theme.size.caption}
          opacity={Math.min(1, progress * 1.6)}
        >
          {label}
        </text>
      ) : null}

      {isSchematic ? (
        <text
          x={head.x + 18}
          y={head.y + 4}
          fill={theme.colors.textMuted}
          fontFamily={theme.font.body}
          fontSize={theme.size.source}
          opacity={Math.min(1, progress * 1.6)}
        >
          schematic route
        </text>
      ) : null}
    </g>
  );
};
```

Memoize `project` with `useMemo()` in the video. If a new function identity is
created each render, the route recomputes, which is correct but wasted work.

## src/components/Timeline.tsx

```tsx
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {formatYear} from '../lib/format';
import type {HistoricalEventData} from '../data/types';
import {theme} from '../theme';

type TimelineProps = {
  startYear: number;
  endYear: number;
  events: HistoricalEventData[];
  playheadYear: number;
  accent?: string;
};

const X0 = 140;
const X1 = 1780;
const Y = 930;
const MIN_TICK_PX = 120;
const MIN_LABEL_PX = 140;

const chooseStep = (span: number) => {
  const steps = [
    1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000,
  ];
  const usable = X1 - X0;

  return (
    steps.find((step) => (usable * step) / span >= MIN_TICK_PX) ??
    steps[steps.length - 1]
  );
};

export const Timeline: React.FC<TimelineProps> = ({
  startYear,
  endYear,
  events,
  playheadYear,
  accent = theme.colors.gold,
}) => {
  const span = Math.max(1, endYear - startYear);
  const yearToX = (year: number) =>
    X0 + ((year - startYear) / span) * (X1 - X0);
  const step = chooseStep(span);
  const firstTick = Math.ceil(startYear / step) * step;
  const ticks: number[] = [];
  for (let year = firstTick; year <= endYear; year += step) {
    // Historical years have no zero, so a tick at 0 would be a data error.
    if (year !== 0) {
      ticks.push(year);
    }
  }

  const playheadX = Math.min(
    X1,
    Math.max(X0, yearToX(playheadYear)),
  );
  let lastAbove = -Infinity;
  let lastBelow = -Infinity;

  const inRange = events
    .filter(
      (event) =>
        event.sortYear !== 0 &&
        event.sortYear >= startYear &&
        event.sortYear <= endYear,
    )
    .sort((a, b) => a.sortYear - b.sortYear);

  return (
    <AbsoluteFill>
      <svg
        viewBox="0 0 1920 1080"
        width={1920}
        height={1080}
        style={{position: 'absolute', inset: 0}}
      >
        <line
          x1={X0}
          y1={Y}
          x2={X1}
          y2={Y}
          stroke={theme.colors.parchmentDim}
          strokeWidth={2}
          opacity={0.55}
        />

        {ticks.map((year) => {
          const x = yearToX(year);
          return (
            <g key={year}>
              <line
                x1={x}
                y1={Y - 8}
                x2={x}
                y2={Y + 8}
                stroke={theme.colors.textMuted}
                strokeWidth={1.5}
              />
              <text
                x={x}
                y={Y + 34}
                fill={theme.colors.textMuted}
                fontFamily={theme.font.data}
                fontSize={theme.size.source}
                textAnchor="middle"
              >
                {formatYear(year)}
              </text>
            </g>
          );
        })}

        {inRange.map((event, index) => {
          const x = yearToX(event.sortYear);
          const above = index % 2 === 0;
          const last = above ? lastAbove : lastBelow;
          const showLabel = x - last >= MIN_LABEL_PX;

          if (showLabel) {
            if (above) {
              lastAbove = x;
            } else {
              lastBelow = x;
            }
          }

          const labelY = above ? Y - 22 : Y + 62;

          return (
            <g key={event.id}>
              <circle
                cx={x}
                cy={Y}
                r={event.confidence === 'verified' ? 6 : 5}
                fill={
                  event.confidence === 'verified'
                    ? accent
                    : theme.colors.disputed
                }
              />
              {showLabel ? (
                <text
                  x={x}
                  y={labelY}
                  fill={theme.colors.text}
                  fontFamily={theme.font.body}
                  fontSize={theme.size.caption}
                  textAnchor="middle"
                >
                  {event.yearLabel}
                </text>
              ) : null}
            </g>
          );
        })}

        <line
          x1={playheadX}
          y1={Y - 54}
          x2={playheadX}
          y2={Y + 54}
          stroke={theme.colors.goldBright}
          strokeWidth={2}
        />
        <circle
          cx={playheadX}
          cy={Y}
          r={7}
          fill={theme.colors.goldBright}
        />
      </svg>
    </AbsoluteFill>
  );
};
```

## src/components/HistoricalEvent.tsx

```tsx
import React from 'react';
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {HistoricalEventData} from '../data/types';
import {theme} from '../theme';

type HistoricalEventProps = {
  event: HistoricalEventData;
  variant?: 'callout' | 'lower-third';
  align?: 'left' | 'right' | 'center';
  sourceLabel?: string;
};

const confidenceLabel: Record<string, string> = {
  approximate: 'approximate',
  disputed: 'disputed',
  schematic: 'schematic',
  unverified: 'unverified',
};

export const HistoricalEvent: React.FC<HistoricalEventProps> = ({
  event,
  variant = 'callout',
  align = 'left',
  sourceLabel,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = spring({
    frame,
    fps,
    durationInFrames: 18,
    config: {damping: 200},
  });
  const opacity = interpolate(progress, [0, 1], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const translateY = interpolate(progress, [0, 1], [16, 0], {
    extrapolateRight: 'clamp',
  });
  const isLowerThird = variant === 'lower-third';
  const horizontal =
    align === 'left'
      ? {left: theme.margin}
      : align === 'right'
        ? {right: theme.margin}
        : {left: '50%', transform: 'translateX(-50%)'};
  const chip = confidenceLabel[event.confidence];

  return (
    <div
      style={{
        position: 'absolute',
        ...(isLowerThird ? {bottom: 180} : {top: 150}),
        ...horizontal,
        width: 720,
      }}
    >
      <div
        style={{
        padding: '28px 32px',
        backgroundColor: 'rgba(10, 13, 18, 0.86)',
        borderLeft: `2px solid ${theme.colors.gold}`,
        boxShadow: '0 18px 60px rgba(0, 0, 0, 0.35)',
        opacity,
        transform: `translateY(${translateY}px)`,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            marginBottom: 12,
          }}
        >
          <span
            style={{
              fontFamily: theme.font.data,
              fontSize: theme.size.caption,
              letterSpacing: '0.12em',
              color: theme.colors.gold,
            }}
          >
            {event.yearLabel}
          </span>
          {chip ? (
            <span
              style={{
                fontFamily: theme.font.body,
                fontSize: theme.size.source,
                color: theme.colors.disputed,
                border: `1px solid ${theme.colors.disputed}`,
                padding: '2px 8px',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              {chip}
            </span>
          ) : null}
        </div>
        <div
          style={{
            fontFamily: theme.font.display,
            fontSize: theme.size.chapter,
            lineHeight: 1.1,
            color: theme.colors.text,
            marginBottom: 10,
          }}
        >
          {event.title}
        </div>
        <div
          style={{
            fontFamily: theme.font.body,
            fontSize: theme.size.caption,
            lineHeight: 1.45,
            color: theme.colors.parchmentDim,
          }}
        >
          {event.summary}
        </div>
        {sourceLabel ? (
          <div
            style={{
              fontFamily: theme.font.body,
              fontSize: theme.size.source,
              color: theme.colors.textMuted,
              marginTop: 14,
            }}
          >
            Source: {sourceLabel}
          </div>
        ) : null}
      </div>
    </div>
  );
};
```

## src/components/CameraMovement.tsx

```tsx
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

type CameraMovementProps = {
  children: React.ReactNode;
  from: {x: number; y: number; scale: number};
  to: {x: number; y: number; scale: number};
  start: number;
  duration: number;
};

export const CameraMovement: React.FC<CameraMovementProps> = ({
  children,
  from,
  to,
  start,
  duration,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = spring({
    frame: Math.max(0, frame - start),
    fps,
    durationInFrames: duration,
    config: {damping: 200},
  });
  const focusX = interpolate(progress, [0, 1], [from.x, to.x]);
  const focusY = interpolate(progress, [0, 1], [from.y, to.y]);
  const scale = interpolate(progress, [0, 1], [from.scale, to.scale]);
  const translateX = 960 - focusX * scale;
  const translateY = 540 - focusY * scale;

  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `translate(${translateX}px, ${translateY}px) scale(${scale})`,
          transformOrigin: '0 0',
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
```

## src/components/AnimatedTitle.tsx

```tsx
import React from 'react';
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {theme} from '../theme';

type AnimatedTitleProps = {
  title: string;
  subtitle?: string;
  kicker?: string;
  start?: number;
  duration?: number;
  align?: 'left' | 'center';
};

export const AnimatedTitle: React.FC<AnimatedTitleProps> = ({
  title,
  subtitle,
  kicker,
  start = 0,
  duration = 36,
  align = 'left',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - start);
  const titleProgress = spring({
    frame: local,
    fps,
    durationInFrames: duration,
    config: {damping: 200},
  });
  const subtitleProgress = spring({
    frame: Math.max(0, local - 8),
    fps,
    durationInFrames: duration,
    config: {damping: 200},
  });
  const revealed = Math.min(1, Math.max(0, titleProgress));
  const clip = `inset(0 ${Math.round((1 - revealed) * 100)}% 0 0)`;
  const subtitleOpacity = interpolate(
    subtitleProgress,
    [0, 1],
    [0, 1],
    {extrapolateRight: 'clamp'},
  );
  const centered = align === 'center';

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 240,
        left: theme.margin,
        right: theme.margin,
        textAlign: centered ? 'center' : 'left',
      }}
    >
      {kicker ? (
        <div
          style={{
            fontFamily: theme.font.data,
            fontSize: theme.size.caption,
            letterSpacing: '0.24em',
            textTransform: 'uppercase',
            color: theme.colors.gold,
            marginBottom: 14,
            opacity: subtitleOpacity,
          }}
        >
          {kicker}
        </div>
      ) : null}
      <div
        style={{
          fontFamily: theme.font.display,
          fontSize: theme.size.title,
          lineHeight: 1.05,
          color: theme.colors.text,
          clipPath: clip,
        }}
      >
        {title}
      </div>
      <div
        style={{
          width: 180,
          height: 2,
          backgroundColor: theme.colors.gold,
          marginTop: 20,
          marginLeft: centered ? 'auto' : 0,
          marginRight: centered ? 'auto' : 0,
          transform: `scaleX(${titleProgress})`,
          transformOrigin: centered ? 'center' : 'left',
        }}
      />
      {subtitle ? (
        <div
          style={{
            fontFamily: theme.font.body,
            fontSize: theme.size.subtitle,
            letterSpacing: '0.04em',
            color: theme.colors.parchmentDim,
            marginTop: 18,
            opacity: subtitleOpacity,
          }}
        >
          {subtitle}
        </div>
      ) : null}
    </div>
  );
};
```

## src/components/DataNotice.tsx

```tsx
import React from 'react';
import {theme} from '../theme';

type DataNoticeProps = {
  text: string;
  tone?: 'neutral' | 'warning';
};

export const DataNotice: React.FC<DataNoticeProps> = ({
  text,
  tone = 'neutral',
}) => (
  <div
    style={{
      position: 'absolute',
      left: 40,
      bottom: 32,
      padding: '8px 12px',
      backgroundColor: 'rgba(10, 13, 18, 0.72)',
      border: `1px solid ${
        tone === 'warning' ? theme.colors.disputed : theme.colors.grid
      }`,
      color:
        tone === 'warning'
          ? theme.colors.disputed
          : theme.colors.textMuted,
      fontFamily: theme.font.body,
      fontSize: theme.size.source,
      letterSpacing: '0.04em',
    }}
  >
    {text}
  </div>
);
```

## src/videos/HistoricalDemo.tsx

This is a structural example, not a historical claim. Replace all of it with
sourced data before rendering anything the user will publish.

```tsx
import React, {useMemo} from 'react';
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {AnimatedTitle} from '../components/AnimatedTitle';
import {ArmyMovement} from '../components/ArmyMovement';
import {CameraMovement} from '../components/CameraMovement';
import {DataNotice} from '../components/DataNotice';
import {HistoricalEvent} from '../components/HistoricalEvent';
import {HistoricalMap} from '../components/HistoricalMap';
import {Territory} from '../components/Territory';
import {Timeline} from '../components/Timeline';
import type {EraData} from '../data/types';
import {createFit, collectPositions} from '../lib/geo';
import {theme} from '../theme';

const demo: EraData = {
  id: 'demo',
  title: 'Example Campaign',
  subtitle: 'Replace this with sourced data',
  startYear: 1200,
  endYear: 1300,
  sources: [{id: 'demo-source', citation: 'Placeholder source'}],
  events: [
    {
      id: 'event-1',
      sortYear: 1210,
      yearLabel: 'c. 1210',
      title: 'Example event',
      summary: 'Placeholder summary. Replace with a sourced claim.',
      confidence: 'unverified',
      sourceIds: ['demo-source'],
    },
  ],
  territories: [
    {
      id: 'territory-1',
      name: 'Example',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [10, 40],
            [30, 40],
            [30, 50],
            [10, 50],
            [10, 40],
          ],
        ],
      },
      confidence: 'unverified',
      sourceIds: ['demo-source'],
      fillToken: 'territoryA',
      labelAt: {x: 900, y: 520},
    },
  ],
  armies: [
    {
      id: 'army-1',
      label: 'Schematic',
      path: [
        [12, 44],
        [24, 47],
        [32, 46],
      ],
      confidence: 'schematic',
      sourceIds: ['demo-source'],
      dashed: true,
    },
  ],
};

export const HistoricalDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const project = useMemo(() => {
    const positions = collectPositions(
      demo.territories.map((territory) => territory.geometry),
    );
    return createFit(positions, {
      x: 140,
      y: 150,
      width: 1640,
      height: 700,
    });
  }, []);
  const playheadYear = interpolate(
    frame,
    [0, demo.events[0].sortYear - demo.startYear + 300],
    [demo.startYear, demo.endYear],
    {extrapolateRight: 'clamp'},
  );

  return (
    <AbsoluteFill style={{backgroundColor: theme.colors.bg}}>
      <CameraMovement
        from={{x: 960, y: 500, scale: 1}}
        to={{x: 1000, y: 480, scale: 1.06}}
        start={0}
        duration={Math.round(9 * fps)}
      >
        <HistoricalMap project={project}>
          {demo.territories.map((territory) => (
            <Territory
              key={territory.id}
              id={territory.id}
              geometry={territory.geometry}
              project={project}
              name={territory.name}
              labelAt={territory.labelAt}
              disputed={territory.confidence === 'disputed'}
              fill={theme.colors[territory.fillToken ?? 'territoryA']}
              revealAt={20}
            />
          ))}
          {demo.armies.map((army) => (
            <ArmyMovement
              key={army.id}
              id={army.id}
              path={army.path}
              project={project}
              start={90}
              duration={90}
              label={army.label}
              dashed={army.dashed}
              confidence={
                army.confidence === 'verified' ||
                army.confidence === 'approximate'
                  ? army.confidence
                  : 'schematic'
              }
            />
          ))}
        </HistoricalMap>
      </CameraMovement>

      <Sequence from={0} durationInFrames={120}>
        <AnimatedTitle
          kicker="Example"
          title={demo.title}
          subtitle={demo.subtitle}
          start={10}
        />
      </Sequence>

      <Sequence from={60} durationInFrames={120}>
        <HistoricalEvent
          event={demo.events[0]}
          variant="callout"
          align="right"
          sourceLabel={demo.sources[0].citation}
        />
      </Sequence>

      <Timeline
        startYear={demo.startYear}
        endYear={demo.endYear}
        events={demo.events}
        playheadYear={playheadYear}
      />

      <DataNotice
        text="Demo data. All claims and geometry are placeholders."
        tone="warning"
      />
    </AbsoluteFill>
  );
};
```

## Font loading

If the project ships licensed font files, load them before rendering:

```ts
import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const displayFont = 'Cormorant Garamond';

loadFont({
  family: displayFont,
  url: staticFile('fonts/CormorantGaramond-SemiBold.woff2'),
  weight: '600',
});
```

`@remotion/fonts` waits for the font. Without local fonts, use the fallback
stacks in `theme.ts` and verify the render container has DejaVu fonts installed.
