# Memory

Updated: 2026-10-31 20:15

## Current state

- Plan: PLAN.md (v2 built, verification pending)
- Working on: `aium/jcode-jarvis` v2 control panel
- Built: panel shell (Now, Live rail, six tabs), backend endpoints
  `/api/history`, `/api/cost`, `/api/settings`, `/api/export`,
  `/api/facts`, `/api/facts/forget`; settings file; status fields.
- Verified: 17 unit tests pass; selftest PASS. Backend probes 36 + 31 + 20 + 27,
  browser flows 43 + 27 + 44 + 17, all 0 failures. axe zero violations light
  and dark. Fixed 400 mapping, last_turn reset, and unsaved tab edits.
- Blocked: image rebuild needs podman; real mic and Piper audio need hardware.

## Next step

1. Rebuild the image on a podman machine and confirm whisper health.
2. Test the real microphone and Piper audio; the Voice tab diagnostics settle
   the Firefox report.
3. v2 is committed except for the last UI polish; nothing else open.

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
