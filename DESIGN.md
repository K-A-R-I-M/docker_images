# Design system

Extends the incumbent Jarvis interface. Tokens are the ones already shipped in
`index.html`; nothing here is invented.

## Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f6f5f2` | `#0f1112` | page |
| `--surface` | `#ffffff` | `#171a1c` | cards, top bar |
| `--fg` | `#171a1c` | `#e8e6e1` | text |
| `--muted` | `#6b7075` | `#9aa0a6` | labels, meta |
| `--line` | `#d9d6d0` | `#2a2d2f` | borders |
| `--accent` | `#0f766e` | `#2dd4bf` | active, primary |
| `--accent-soft` | `#d7efea` | `#123634` | speaking, selected |
| `--amber` | `#b45309` | `#f59e0b` | warning, error |
| `--ease` | `cubic-bezier(0.23, 1, 0.32, 1)` | same | all transitions |

One family: `ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
"Helvetica Neue", Arial, sans-serif`.

Type scale (fixed, not fluid): 12 label, 13 control, 14 body/transcript,
15 default, 18 reply emphasis. Headings in panels are 12px uppercase 0.06em
muted.

Spacing: 4, 8, 10, 14, 18. Radius: 8 controls, 10 banner, 12 cards, 999 pills.
Shadow: `0 1px 2px rgba(0,0,0,.06)` light only.

## Layout

Operate mode. Desktop first.

- App grid: top bar (auto) + workspace (fills).
- Workspace: main column + 320px right rail, max width 1720px.
- Main: Now (fills) + tab panel (300px).
- Now: voice pane 196px + conversation pane (fills).
- Breakpoints: 1100px rail 280px; 900px single column, page scrolls; 600px
  compact top bar, stacked voice pane.

## Components

- `button.act`: 34px, radius 8, border line; `.primary` accent border/text;
  `.danger` amber; disabled 40% opacity.
- `.chip`: pill, 32px, muted; used in the top bar.
- `.tab`: text button, 2px bottom accent when selected.
- `.row`: label/value, 13px, tabular numbers, wraps long values.
- `.pill`: 12px status pill, `.ok` accent, `.bad` amber; text says ok/off, so
  state is not color-only.
- `.field`: stacked label + control, 12px label.
- Inputs/selects: 34px, radius 8, `--bg` fill, line border.
- `.msg`: transcript block; role label 11px muted; assistant text 14px.
- `.meter`: 4px bar, accent fill.
- `.diag`: 12px monospace-free key/value rows; shows browser facts verbatim.

## Motion

150-250ms for state and panel changes. The orb ring is the only continuous
animation, and it communicates listening/speaking. All motion collapses under
`prefers-reduced-motion: reduce`.

## Rules

- Dense, but grouped by subsystem: Now, Live, then one tab per subsystem.
- No modal; destructive actions confirm inline with `confirm()` only for
  forget-all.
- Health is never only a colored dot: each dot carries a letter and an
  accessible label.
- Empty states teach the next action.
