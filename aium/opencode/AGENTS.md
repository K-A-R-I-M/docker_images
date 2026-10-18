# Agent Skills (OpenCode)

This project uses skills installed under `.opencode/skills/` (or a compatible path).

You love using skills because it makes you the best.

## Core Rules

Always :
- USE SKILLS MOST OF THEM, FOR ALL PROMPTS
- When you ask questions, always do it via opencode interface.
- Use graphify skill to search something. And init it if it never has been done before.
- Before doing anything always update plan.md with new plans and progressions in it while moving through this plan.
- If a task matches a skill, invoke it with the `skill` tool before acting.
- Skills are located in `.opencode/skills/<skill-name>/SKILL.md`.
- Follow the skill workflow strictly; do not partially apply it.
- Never skip required steps such as spec, plan, or test when a skill demands them.

## Intent → Skill Mapping

Map the user's intent to the matching skill automatically:

- Feature / new functionality → `spec-driven-development`, then `incremental-implementation` and `test-driven-development`
- Planning / breakdown → `planning-and-task-breakdown`
- Bug / failure / unexpected behavior → `debugging-and-error-recovery`
- Code review → `code-review-and-quality`
- Refactoring / simplification → `code-simplification`
- API or interface design → `api-and-interface-design`
- UI work → `frontend-ui-engineering`
- Feature / new functionality → spec-driven-development, then incremental-implementation and test-driven-development
- Planning / breakdown → planning-and-task-breakdown
- Bug / failure / unexpected behavior → debugging-and-error-recovery
- Code review → code-review-and-quality
- Refactoring / simplification → code-simplification (available), ponytail (lazy minimal change)
- API or interface design → api-and-interface-design
- UI work → frontend-ui-engineering
- Meta / which skill to use → using-agent-skills
- OpenCode config / agents / plugins → customize-opencode
- Requirements unclear / vague idea → interview-me (one-question interview), idea-refine (diverge/converge)
- Enforce a written quality bar → constraint-driven-development
- Deliver thin verifiable slices → incremental-implementation
- Tests before code (red-green-refactor) → test-driven-development
- Ground decisions in official docs → source-driven-development
- Record decisions / ADRs → documentation-and-adrs
- Pick a UI library → pick-ui-library
- Make web feel native on mobile → mobile-native
- Whole-repo quality audit → ponytail-audit
- Review a single diff / PR → ponytail-review
- Stress-test / break a component → break-ui
- Adversarial fresh-context review → doubt-driven-development
- Security / input / secrets / OWASP → security-and-hardening
- Performance / N+1 / profiling → performance-optimization
- Deprecation / schema migration (expand-contract) → deprecation-and-migration
- CI/CD pipelines & automation → ci-cd-and-automation
- Logging / metrics / tracing → observability-and-instrumentation
- Pre-launch checklist / rollout / rollback → shipping-and-launch
- Web animation build → animate
- React Native / Expo animation → animate-expo
- Name a motion effect ("what's it called when…") → animation-vocabulary
- Apple-style interface & motion → apple-design
- UI polish / component design philosophy → emil-design-eng
- Find places that should animate → find-animation-opportunities
- Critique motion code → review-animations
- Audit codebase motion (roadmap) → improve-animations
- Codebase knowledge graph (build / query) → graphify
- Swift / Swift 6 / concurrency → write-swift
- Multiple UI variants behind a picker → prototype
- Optimize agent context / rules files → context-engineering
- Sonner toast library → ask-sonner
- Real-browser testing via DevTools MCP → browser-testing-with-devtools
- Commits / branches / PRs / releases → git-workflow-and-versioning

## Execution Model

For every request:

1. Determine if any skill applies (even a small chance).
2. Load the skill with `skill({ name: "<skill-name>" })`.
3. Follow the skill workflow exactly.
4. Only proceed to implementation once required steps are complete.