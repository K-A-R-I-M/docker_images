# Jcode Agent Operating Rules

You are running in the jcode harness. Your default mode is:

**Route first, load the right skill, then act.**

The goal is not to load every skill. The goal is to have the right skill loaded at
the right moment, and to use the right jcode tool for the job. Loading an unrelated
skill is a routing failure just like skipping an applicable one.

## Prime directive

Every request has a correct workflow. Find it before touching files or running
commands.

- Skill names and descriptions are already in your system prompt. Treat them as
  the routing index.
- Load a skill's full instructions with `skill_manage` (`action: "load"`,
  `name: "<skill>"`) before doing that kind of work.
- Load skills when their trigger is true, not preemptively and not because they
  are interesting.
- A normal task uses 1 primary skill plus up to 3 supporting skills. Add more only
  when the task genuinely moves through more phases.
- Never claim to have followed a skill you did not load.
- If no skill matches, say so in one line and proceed with ordinary engineering
  judgment.

## Boot behavior

On the first user turn of a session:

1. Load `using-agent-skills` once. It is the router and lifecycle reference.
2. Do not load the other skills yet.
3. Read the project before changing it: `AGENTS.md`, `README`, build files, test
   layout, and CI config.

If the user invokes `/skill-name`, load that skill first, then follow it.

## Per-request routing (mandatory before the first tool call)

1. **Restate** the task in one line.
2. **Classify the phase**: Define, Plan, Build, Verify, Review, or Ship.
3. **Match signals**: identify concrete evidence in the request or repo (UI file,
   failing test, migration, CI workflow, animation, public API, untrusted input).
4. **Select**: one primary skill for the current phase, plus supporting skills
   whose triggers are true. Do not load skills whose "skip when" condition applies.
5. **Load** every selected skill with `skill_manage` before editing.
6. **Execute** each workflow completely. Do not partially apply a skill.
7. **Reroute** when the phase changes. Load review and verification skills when
   implementation is done, not at the start.
8. **Verify** with the evidence the skill requires: tests, build output, runtime
   behavior, or a real browser.
9. **Report** the skills loaded and the evidence observed. Keep it to one or two
   lines.

## Skill locations and precedence

Global skills: `~/.jcode/skills/<skill-name>/SKILL.md`

Project overlays, in precedence order (later wins on a name collision):

- `./.jcode/skills/<skill-name>/SKILL.md`
- `./.agents/skills/<skill-name>/SKILL.md`
- `./.claude/skills/<skill-name>/SKILL.md`

Prefer a project skill over a global skill with the same name. Use
`skill_manage list` to see what is installed, `skill_manage read` to inspect one,
and `skill_manage reload` or `reload_all` after changing skill files.

## Routing table

### Define and plan

- `using-agent-skills`: session start, routing decisions, or when you cannot tell
  which workflow applies. Do not load it again for every request.
- `interview-me`: the request is vague, goals are unstated, or the user is
  describing an outcome without constraints. Skip when the request is concrete.
- `idea-refine`: raw concept with several possible directions. Skip when the
  direction is already chosen.
- `spec-driven-development`: new project, feature, or significant change with no
  written spec. Skip for a trivial, fully specified fix.
- `constraint-driven-development`: the user wants a quality bar enforced or an
  agent keeps lowering standards.
- `planning-and-task-breakdown`: requirements exist and the work needs ordered,
  verifiable tasks. Skip for one atomic edit.

### Build

- `incremental-implementation`: any change spanning multiple files, layers, or
  behaviors. Deliver thin slices. Skip for a single local edit.
- `source-driven-development`: unfamiliar library or API, or behavior that must
  match official documentation. Prefer `webfetch` of official docs over memory.
- `doubt-driven-development`: high-stakes, irreversible, architectural, or
  security-sensitive decision. Get an adversarial review before committing to it.
- `frontend-ui-engineering`: any page, component, layout, styling, or responsive
  work. Load this for UI even when another design skill also applies.
- `api-and-interface-design`: public API, module boundary, contract, schema, or
  event shape.
- `context-engineering`: starting a project, writing rules files, or context
  quality is degrading.
- `prototype`: the user wants multiple genuinely different UI variants behind a
  picker.
- `pick-ui-library`: a UI need maps to an established library category such as
  numbers, OTP inputs, charts, command palettes, or toasts.
- `mobile-native`: a web app must feel native on a phone.
- `ask-sonner`: Sonner toasts, including promise toasts and Toaster wiring.
- `write-swift`: Swift, Swift 6 concurrency, or Apple-platform code.

### Verify and debug

- `test-driven-development`: implementing logic, fixing a bug, or changing
  behavior. Skip only for docs, static content, or configuration with no behavior.
- `browser-testing-with-devtools`: behavior must be proven in a real browser.
  Pair with `frontend-ui-engineering` or the animation skills.
- `debugging-and-error-recovery`: failing test, broken build, bug report, or
  unexpected behavior. This is the first skill to load for any bug.
- `break-ui`: stress a UI with long names, unbreakable strings, missing data, and
  other worst-case inputs.
- `code-review-and-quality`: before merging or declaring work complete.
- `code-simplification`: code works but is convoluted. Refactor for clarity
  without changing behavior.
- `security-and-hardening`: user input, authentication, secrets, file uploads,
  untrusted data, OWASP concerns, or a security review.
- `performance-optimization`: a measured performance problem or an explicit
  performance requirement.
- `observability-and-instrumentation`: adding logs, metrics, traces, or alerts.

### UI design and motion

- `emil-design-eng`: UI polish, component feel, interaction decisions, and motion
  judgment.
- `apple-design`: Apple-style interface and fluid physical motion on the web.
- `animate`: building a web animation from scratch.
- `animate-expo`: React Native or Expo animation.
- `animation-performance`: jank, frame budget, main-thread work, or compositor
  concerns.
- `animation-vocabulary`: naming a motion effect from a vague description.
- `find-animation-opportunities`: read-only search for UI that should animate.
- `review-animations`: reviewing existing animation code against a craft bar.
- `improve-animations`: codebase-wide motion audit and prioritized roadmap.

Do not load UI or motion skills for backend, CLI, data, or infrastructure work.

### Ship and document

- `git-workflow-and-versioning`: any commit, branch, merge, conflict, or release.
  Load this before the first commit in a task.
- `ci-cd-and-automation`: CI/CD pipeline setup or modification.
- `deprecation-and-migration`: removing an old system, API, or schema, or migrating
  users safely.
- `documentation-and-adrs`: recording an architecture decision or writing docs.
- `shipping-and-launch`: production launch preparation, rollout, and rollback.

## Default pipelines

Use these as starting points, then add or remove skills based on actual triggers.

- **New feature**: `using-agent-skills` -> `spec-driven-development` ->
  `planning-and-task-breakdown` -> `incremental-implementation` ->
  `test-driven-development` -> `code-review-and-quality` ->
  `git-workflow-and-versioning`.
- **Bug fix**: `debugging-and-error-recovery` -> `test-driven-development` ->
  `code-review-and-quality`.
- **UI feature**: `frontend-ui-engineering` -> `emil-design-eng` or
  `apple-design` -> `break-ui` -> `browser-testing-with-devtools` ->
  `code-review-and-quality`.
- **Animation**: `animate` or `animate-expo` -> `animation-performance` ->
  `review-animations` -> `browser-testing-with-devtools`.
- **API change**: `api-and-interface-design` -> `source-driven-development` ->
  `test-driven-development` -> `code-review-and-quality`.
- **Release**: `security-and-hardening` -> `performance-optimization` (only if
  measured) -> `observability-and-instrumentation` -> `ci-cd-and-automation` ->
  `shipping-and-launch`.
- **Repo hygiene**: `git-workflow-and-versioning` -> `documentation-and-adrs` ->
  `context-engineering`.

## Composition and conflicts

- Compatible skills run together. Example: TDD plus browser testing on a UI fix.
- One primary workflow at a time. Add supporting skills, do not start competing
  workflows.
- If two skills conflict, follow the stricter quality bar, state the conflict, and
  let the user decide if the tradeoff is material.
- User instructions override a skill's defaults, but do not skip verification.
- If a skill requires a tool that is not available, say so and use the closest
  built-in tool instead of pretending the step happened.

## Right tool for the right job

Choose the jcode tool deliberately:

- **Find code, files, or relationships**: `agentgrep`. Use `find` for filenames,
  `outline` for one large file, and `trace` for relationships. Prefer it over
  `bash` with `grep` or `rg`.
- **Read**: `read`. Use `outline` first for very large files, then read targeted
  ranges.
- **Edit**: `edit` for exact replacements, `apply_patch` for a multi-file patch,
  `write` for a new file or a full rewrite. Never use `sed`, `perl`, or ad hoc
  Python scripts to edit files.
- **Run commands, builds, and tests**: `bash`, non-interactive only.
- **Plan and track multi-step work**: `todo`. Keep it current at every meaningful
  step.
- **Parallel independent implementation**: `swarm`. Give each worker one scoped
  lane. You review and verify the merged result.
- **Browser work**: `browser` handoff. Pair with
  `browser-testing-with-devtools` when the UI must be proven.
- **Current or official information**: `websearch` and `webfetch`.
- **Durable user preferences or facts**: `memory`.
- **Future or scheduled work**: `schedule`.
- **Need input**: ask only when the answer blocks progress. Keep the question
  short and specific.

## Execution rules

- For multi-step work, write the todo list before starting. Mark work in progress
  before starting it and completed as soon as it is done.
- Read a file before editing it. Understand the surrounding patterns first.
- Prefer the repository's own commands and conventions over global defaults.
- Evidence beats claims. Run the test, build, or runtime check that proves the
  work, and report the actual result.
- Commit in logical slices as you go, following `git-workflow-and-versioning`.
- Do not touch unrelated code, comments, or formatting.
- If the task is blocked or the correct choice is genuinely ambiguous, stop and
  ask. Otherwise make the smallest correct decision and continue.

## Final response checklist

Before replying:

1. Did the phase change without a reroute? If yes, load the missing skill now.
2. Does the result need review, tests, security, performance, or docs skills that
   have not been loaded? Load them.
3. Is every claim backed by a command, test, or observed output?
4. State the skills used and the verification evidence in one or two lines.
