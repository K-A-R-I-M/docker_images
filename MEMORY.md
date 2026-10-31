# Memory

Updated: 2026-10-31 20:15

## Current state

- Plan: PLAN.md (v2 built and refactored; hardware verification pending)
- Working on: `aium/jcode-jarvis` cleanup and optimization
- Built: `jarvis.py` is a 39-line entrypoint; `app/` has config, cost,
  language, store, router, speech, brain, core, supervisor, api, device.
  Largest module 409 lines. Tests are pytest, selftest removed.
- Cleaned: dropped dead helpers/attributes/unused imports, deduped icons,
  lazy-loads mermaid (2.7 MB only when a diagram appears), skips hidden-tab
  re-renders.
- Verified: 19 pytest tests pass; all 5 backend probes and all 6 browser probes
  report 0 failures; detector clean; no mermaid fetch without a diagram.
- Blocked: image rebuild needs podman; real mic and Piper audio need hardware.

## Next step

1. Rebuild the image on a podman machine; the Dockerfile now copies `app/`.
2. Test the real microphone and Piper audio; the Voice tab diagnostics settle
   the Firefox report.
3. Optional later phase: FastAPI/httpx or the UI split, only after a dependency
   and latency review.

## Log (last 10)

- 2026-10-31 11:16 - Investigated repo image patterns, jcode run/resume, and
  audio options. Wrote proposed plan, awaiting approval.
- 2026-10-31 17:31 - Fixed whisper exit 127 (static link) and supervisor log
  spam; clarified mic errors on insecure contexts. Rebuild still pending.
- 2026-10-31 20:07 - Agreed v2 direction: desktop-first control panel. Wrote
  PRODUCT.md and v2 plan with frozen API contract. No code yet.
- 2026-10-31 20:15 - Built v2: panel rewrite, six tabs, backend endpoints and
  settings, DESIGN.md, tests. Detector clean; runtime verification pending.
- 2026-10-31 20:20 - Verified: 14 tests, selftest, endpoint smoke, SSE history,
  screenshots at four sizes. Fixed tab clipping, cost empty state, provider
  select, stale mic device, TTS-off fallback.
- 2026-10-31 20:23 - Deep validation: 36 backend edge checks and 43 Selenium
  browser checks, 0 failures. Fixed favicon 404; added 2 regression tests.
- 2026-10-31 20:28 - Second pass: concurrency, perf, restart persistence,
  axe, reconnect, token flow; backend 31 and browser 27 checks, 0 failures.
  Fixed 413 for oversized bodies, Offline chip recovery, chart zero days.
- 2026-10-31 20:32 - Third pass: timezone buckets, concurrent settings, export
  download, dark axe, denied mic; backend 20 and browser 44 checks, 0 failures.
  Fixed hash navigation and aria roles.
- 2026-10-31 20:39 - Fourth pass: SSE contract, concurrent turns, brain switch
  persistence, transcript cap, tab edit retention; backend 27 and browser 17
  checks, 0 failures. Fixed 400 mapping, last_turn reset, unsaved tab edits.
- 2026-10-31 20:43 - Fifth pass: facts limit/count, type validation, voice
  clear, NULL costs, long content, health flip; backend 25 and browser 13
  checks, 0 failures. Fixed 500s on bad types, fact truncation, chip overflow.
- 2026-10-31 21:24 - Added mermaid diagrams: persona allows one on request,
  2.7 MB renderer vendored locally, transcript renders fences, speech filter
  skips them. 19 tests; all probes green.
- 2026-10-31 21:40 - Refactored jarvis.py (1946 lines) into app/ modules with a
  39-line entrypoint; converted tests to pytest and removed --selftest.
  Fixed a missing health-check import found by the probes.
- 2026-10-31 21:50 - Cleanup: removed dead helpers/attrs, deduped icons,
  lazy-loaded mermaid, and skipped hidden-tab renders. 19 tests and all probes
  green.
