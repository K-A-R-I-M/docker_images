# Memory

Updated: 2026-10-31 20:15

## Current state

- Plan: PLAN.md (v2 built, verification pending)
- Working on: `aium/jcode-jarvis` v2 control panel
- Built: panel shell (Now, Live rail, six tabs), backend endpoints
  `/api/history`, `/api/cost`, `/api/settings`, `/api/export`,
  `/api/facts`, `/api/facts/forget`; settings file; status fields.
- Verified: Impeccable detector clean; JS bracket balance clean; every JS id
  exists; backend diff reviewed. No runtime run: no python3, podman, browser.
- Blocked: tests, selftest, HTTP smoke, screenshots, image rebuild need the
  user's machine.

## Next step

1. User runs `python3 -m unittest discover -s tests` and
   `python3 jarvis.py --selftest` in `aium/jcode-jarvis`, then rebuilds the
   image and confirms whisper health.
2. Open the panel and check mic diagnostics, transcript, cost tab, and memory.
3. Still open: Firefox mic cause, screenshots, commit.

## Log (last 10)

- 2026-10-31 11:16 - Investigated repo image patterns, jcode run/resume, and
  audio options. Wrote proposed plan, awaiting approval.
- 2026-10-31 17:31 - Fixed whisper exit 127 (static link) and supervisor log
  spam; clarified mic errors on insecure contexts. Rebuild still pending.
- 2026-10-31 20:07 - Agreed v2 direction: desktop-first control panel. Wrote
  PRODUCT.md and v2 plan with frozen API contract. No code yet.
- 2026-10-31 20:15 - Built v2: panel rewrite, six tabs, backend endpoints and
  settings, DESIGN.md, tests. Detector clean; runtime verification pending.
