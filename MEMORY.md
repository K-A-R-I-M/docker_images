# Memory

Updated: 2026-10-31 20:07

## Current state

- Plan: PLAN.md (v2 control panel, awaiting approval; v1 archived in same file)
- Working on: v2 design and plan; no v2 code written
- Direction: desktop-first control panel, Operate mode, dense but grouped.
  Now + Live always visible, tabs for Brain/Voice/Memory/Cost/System/Logs.
- Contracts: API contract frozen in PLAN.md; PRODUCT.md written.
- Changed: PLAN.md v2 + PRODUCT.md; earlier whisper/mic fixes in
  jarvis.py, index.html, Dockerfile.
- Verified: nothing new; no python3, podman, or browser bridge in this env.
- Blocked: user approval of v2 plan before any v2 code.

## Next step

1. Get approval for PLAN.md v2, then build phase 1 (backend) and phase 2
   (panel shell) in parallel, integrate, verify where python/podman exist.
2. Still open: image rebuild for whisper, Firefox mic cause, commit v1.

## Log (last 10)

- 2026-10-31 11:16 - Investigated repo image patterns, jcode run/resume, and
  audio options. Wrote proposed plan, awaiting approval.
- 2026-10-31 17:31 - Fixed whisper exit 127 (static link) and supervisor log
  spam; clarified mic errors on insecure contexts. Rebuild still pending.
- 2026-10-31 20:07 - Agreed v2 direction: desktop-first control panel. Wrote
  PRODUCT.md and v2 plan with frozen API contract. No code yet.
