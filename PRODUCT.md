# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing: Python standard library server (`jarvis.py`) serving one static
`index.html`, no frontend framework, SQLite for memory, run as one Podman
container. v2 keeps that stack.

## Users

One owner-operator, working at a desk or laptop. They run the container
themselves, speak to Jarvis while working, and open the panel to check what it
heard, what it cost, and what it remembers. No multi-user, no roles, no sharing.

## Product Purpose

A bilingual (FR/EN) voice companion that runs locally: speech recognition,
speech synthesis, memory, and routing stay on the machine; only text goes to a
cloud brain. The panel exists so the owner can see and control every local
subsystem without reading container logs or SQLite.

Success: the owner can answer "is it working, what did it just do, what does it
know, what is it costing" on one screen, in one glance, and change the brain,
voice, or memory without a shell.

## Positioning

A voice assistant where the private parts stay yours: audio never leaves the
device, memory is a local SQLite file you can inspect and delete, and the cloud
only ever receives text. The control panel makes that promise checkable rather
than asserted.

## Operating Context

- Container on amd64 or arm64, browser on desktop over localhost or HTTPS.
- Local speech services: whisper.cpp (`whisper-server`/`whisper-cli`) and Piper.
- Cloud brain is configuration: provider/model/fallback in `brain.toml`.
- Costs are per-turn and per-session, priced by `pricing.json`.
- Optional access token (`JARVIS_TOKEN`) when exposed beyond localhost.

## Capabilities and Constraints

- Speech, memory, routing, UI are local; the cloud brain is the only network hop.
- Browser mic requires a secure context (`localhost` or HTTPS); the panel must
  say so instead of showing a generic browser error.
- Existing API: `/api/status`, `/api/health`, `/api/brain`, `/api/events`,
  `/api/facts`, `/api/usage`, `/api/chat`, `/api/tts`, `/api/forget`,
  `/api/cancel`, `/api/turn` (SSE).
- Turns are stored with timings, token counts, cost, provider, and model.
- No wake word, no always-on listening, no multi-user, no timers.

## Brand Commitments

Name: Jarvis. Warm neutral surface, teal accent, one sans family, light and
dark via `prefers-color-scheme`. Bilingual French and English, including UI
copy and voice. Privacy line stays visible: audio stays on device, cloud gets
text only.

## Evidence on Hand

- `aium/jcode-jarvis/index.html` is the incumbent interface.
- `aium/jcode-jarvis/jarvis.py` is the server and data model.
- `pricing.json`, `brain.toml`, `config.toml`, `AGENTS.md` (persona).
- No screenshots, brand assets, testimonials, or analytics exist.

## Product Principles

1. Local truth is visible: every claim about privacy or health is confirmable
   in the panel.
2. One glance answers the daily question before any click.
3. Dense is fine; ambiguous is not. Group by subsystem, not by convenience.
4. Controls live next to the evidence they change.
5. Failure is shown in place, with the fix, not in a log file.

## Accessibility & Inclusion

Keyboard operable, visible focus, `prefers-reduced-motion` respected, AA
contrast in both themes. No product-specific requirement established beyond
that.

## Open Decisions

- Whether a spend budget limit ships in v2 (proposed, not agreed).
- Whether the panel needs per-fact editing, or forget plus export is enough.
- Firefox mic failure cause still unconfirmed; the Voice tab will show origin,
  secure-context, and permission state to settle it.
