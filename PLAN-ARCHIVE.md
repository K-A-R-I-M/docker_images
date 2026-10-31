# Plan: motion-design skill for jcode-remotion

## Goal

Turn the user's historical motion graphics brief into the `motion-design` jcode
skill shipped by the `aium/jcode-remotion` image, and make the image actually
install it.

## Steps

| # | Step | Files | Status | Evidence |
|---|---|---|---|---|
| 1 | Author the skill: principles, provenance rules, workflow, component contracts, visual system, verification | `aium/jcode-remotion/motion-design/SKILL.md` | done | 613 lines, valid frontmatter, 34 fences balanced |
| 2 | Add copy-paste implementations for all seven required components plus helpers and demo | `aium/jcode-remotion/motion-design/TEMPLATES.md` | done | 1538 lines, 19 extracted source files |
| 3 | Wire the skill into the image and carry global config | `aium/jcode-remotion/Dockerfile` | done | COPY sources exist in context; label fixed; CRLF and trailing space removed |
| 4 | Verify the templates in a real Remotion project | scratch project | done | typecheck, bundle, compositions, stills, MP4, ffprobe all pass |

## Verification evidence

- Extracted every `## src/...` block from `TEMPLATES.md` into a throwaway
  project, installed `remotion@4.0.538`, and ran `npx tsc --noEmit` with strict
  mode. Exit 0.
- `npx remotion bundle src/index.ts` succeeded.
- `npx remotion compositions src/index.ts` reported `HistoricalDemo 30 1920x1080
  900 (30.00 sec)`.
- Rendered stills at frames 90 and 200 and inspected them. Found the lower-third
  title colliding with the timeline, moved it from `bottom: 150` to `bottom:
  240`, re-rendered.
- Rendered the full video: `out/HistoricalDemo.mp4`, 640.5 kB. `npx remotion
  ffprobe` reports h264, 1920x1080, 30 fps, 30.00 s, yuv420p.
- Dockerfile: no CR bytes, no trailing whitespace, final newline, all COPY
  sources present. No container runtime is installed here, so the image build
  itself was not run.

## Out of scope

- Building or pushing the image.
- Adding a real historical dataset. The demo is explicitly marked unverified
  placeholder data.

---



## Goal

Make the agent default to parallel swarm execution for approved plans with
multiple independent workstreams, at the largest fan-out that is actually
beneficial, without lowering the verification bar.

## Approved scope

Apply the same policy to all three image variants, which currently ship
byte-identical `AGENTS.md` files:

- `aium/jcode/AGENTS.md`
- `aium/jcode-node/AGENTS.md`
- `aium/jcode-rust/AGENTS.md`

## Steps

| # | Step | Files | Status | Evidence |
|---|---|---|---|---|
| 1 | Write plan and running memory | `PLAN.md`, `RUNNING_MEMORY.md` | done | files present |
| 2 | Add `Swarm-first execution` section (decision rules, fan-out sizing, phases/lanes, spawn contract, worker contract, integration, worktrees, anti-patterns) | `aium/jcode/AGENTS.md` | done | section at line 61 |
| 3 | Add lane-splitting step to Per-request routing; add parallel pipeline; update swarm tool bullet; add execution rule | `aium/jcode/AGENTS.md` | done | anchors at lines 216, 336, 382, 396 |
| 4 | Mirror the approved file to node and rust variants | `aium/jcode-node/AGENTS.md`, `aium/jcode-rust/AGENTS.md` | done | all three hash `86d9621a...` |
| 5 | Document cap and remove trailing space in swarm config | `aium/*/config.toml` | done | all three hash `cafdd119...`; comment lines 17-18 |
| 6 | Verify | all of the above | done | hashes, grep anchors, structural TOML check, balanced fences |

## Verification

- `diff` between the three AGENTS.md files is empty.
- `sha256sum` matches across the three copies.
- No TOML parser is installed in the image (`python3` absent). A structural check
  confirms every non-comment, non-section line is a `key = value` pair, and the
  only changes to the already-valid TOML are comments and a final newline.
- A strict subset parser (sections, keys, quoted strings, booleans, integers,
  duplicate-section/key detection) accepts all three configs. Effective values
  read back as `swarm=true`, `swarm_model="inherit"`,
  `swarm_spawn_mode="headless"`, `swarm_max_concurrent_agents=20`.
- Byte hygiene: no CR bytes, no tabs, no trailing whitespace, final newline
  present in every AGENTS.md and config.
- Policy cross-check against bundled swarm docs: one-level fan-out, workers
  cannot spawn, reports auto-forward to the coordinator, `launch` assigns one
  agent per todo lane, and lanes inside a phase run in parallel.
- The jcode binary contains the three config keys (`swarm_model`,
  `swarm_spawn_mode`, `swarm_max_concurrent_agents`), so the keys are recognized
  by this build. An isolated `JCODE_HOME` smoke test did not surface parse errors
  for a malformed config, so it was not treated as validation evidence.
- Every `##` heading present in the committed AGENTS.md still exists in the new
  file. The fan-out table covers 1-20 plus an open-ended `> 20` row with no gaps
  or overlaps.
- No secret patterns in `PLAN.md`, `RUNNING_MEMORY.md`, or the edited files.
- Docker build context: each Dockerfile copies `./AGENTS.md` and
  `./config.toml`, both present, and no `.dockerignore` excludes them. `run.ps1`
  builds from `./aium/<tag>`, which matches those paths.
- New policy size: 101 lines / 4,222 bytes, about 1K tokens added to every
  session prompt; total AGENTS.md is 18,847 bytes.
- `grep` confirms the new section, routing step, pipeline, and tool bullet.
- No image build is required for a documentation/config-only change; the
  Dockerfiles `COPY ./AGENTS.md` and `COPY ./config.toml` unchanged.

## Out of scope

- Rebuilding or pushing images.
- Changing the 20-agent hard cap.
- Committing pre-existing unrelated working-tree changes.

## Note

The three `config.toml` files were stored with CRLF endings, a trailing space,
and no final newline. Rewriting them normalized all three to LF with a final
newline. This is why their diff shows every line changed.

## Validation follow-up

- Closed a gap found during validation: the policy now says to mirror approved
  lanes into the todo list (`lane` + `phase` + `details`), which is the input
  `swarm launch` actually consumes.
- Re-mirrored all three AGENTS.md copies and re-ran hashes after that edit.

## Validation follow-up 2

- Confirmed config-key strings in the shipped binary, original headings intact,
  table ranges contiguous, no secret patterns, Docker paths correct, and the
  prompt-cost delta measured.
- The only unavailable check is a full TOML parser: the image has no Python,
  Node, Ruby, or TOML CLI, and jcode's loader did not report malformed sandbox
  config. The strict subset parser plus the binary key check cover every
  construct actually present in the file.

## Validation follow-up 3

- `git diff --check` reports no whitespace errors; no conflict markers; no BOM;
  all edited files are pure ASCII with a final newline.
- Inline backticks are balanced on every non-fence line, and every Markdown table
  has a consistent column count.
- The recovery wording ("retry or reassign") matches the documented swarm
  handoffs: retry keeps the assignee, reassign moves to another existing agent,
  replace swaps after safe-state checks, and salvage preserves progress.
- PLAN line references (61; 216, 336, 382, 396) and documented hashes
  (`86d9621a...`, `cafdd119...`) match the files exactly.

## Validation follow-up 4

- Binary string evidence confirms the cap is real and enforced: "Swarm live-agent
  limit reached (max ..., configured by agents.swarm_max_concurrent_agents). This
  swarm already has ... active spawned agents." This matches the policy wording
  "hard cap, not a target".
- The binary also exposes the config type `AgentsConfig` with a `toml_edit2`
  deserializer and a `default_swarm_max_concurrent_agents` field, confirming the
  key is a TOML-deserialized field of the `[agents]` section.
- Fan-out logic simulated for 1-30 lanes: workers never exceed lanes or the 20
  cap, lane 1 stays serial, every multi-lane count gets at least 2 workers, and
  21+ lanes cap at 20 with phasing.
- `PLAN.md` and `RUNNING_MEMORY.md` pass the same Markdown checks: consistent
  table columns, no heading-level jumps, balanced inline backticks, no trailing
  whitespace.
- Numeric claims agree across AGENTS.md, config.toml, and PLAN.md: cap 20,
  practical ceiling 6-8.

## Validation follow-up 5

- `swarm_spawn_mode = "headless"` is valid: the binary documents "Expected one
  of: visible, headless, inline, auto" and includes a
  `swarm_spawn_mode = "inline"` example.
- `swarm_model = "inherit"` is valid: the binary includes a
  `# swarm_model = "inherit"` example and a "Configured agents.swarm_model
  default" message.
- The fan-out table header now reads "Max workers", removing the ambiguity
  between per-lane counts and the 6-8 practical ceiling; the ranges are unchanged.
- Host baseline is 12 logical CPUs / 23.4 GiB, so 6-8 compute-bound workers is a
  conservative ceiling and the 20 cap is reserved for I/O-bound lanes.
