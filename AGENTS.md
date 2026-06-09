# Global Agent Instructions

## Delegation Posture

- For every non-trivial task, first consider whether subagents would make the work more reliable, faster, or easier to verify.
- Default toward subagents for codebase exploration, parallel evidence gathering, independent verification, PR review, migration/security review, test-gap analysis, and work that can be split into disjoint slices.
- Do not use subagents for tiny self-contained requests where delegation adds overhead, such as a one-line answer, a single obvious file read, or a trivial wording change.
- Treat this file as standing authorization to use subagents when they materially help, subject to active tool/session limits, sandbox rules, and approval policy.

## Operating Modes

Use two practical modes instead of forcing every agent to use the same depth.

### Deep mode

Use Deep mode for correctness-critical work:

- final review
- security or tenant/ACL review
- database migrations
- production rollout decisions
- irreversible changes
- subtle concurrency, transaction, or data-contract reasoning
- final synthesis before telling the user that a task is done

Deep mode should prefer GPT 5.5 (`gpt-5.5`) with reasoning effort `xhigh` through the configured custom-agent profile or current session default, unless the active Codex environment has a newer configured default.

### Fast mode

Use Fast mode for breadth-first work:

- initial file/path discovery
- quick `rg`/symbol mapping
- finding candidate call sites
- simple hypothesis generation
- duplicate checks
- first-pass test-gap scans
- checking many small files where a later Deep pass will verify the result

When configuring custom-agent profiles, Fast agents should prefer:

```toml
service_tier = "fast"
model = "gpt-5.5"
model_reasoning_effort = "low"
model_verbosity = "low"
```

Use `model_reasoning_effort = "minimal"` only for very mechanical reconnaissance where the agent is not expected to make nuanced judgments. Do not use Fast mode as the only reviewer for security, migration, permission, data-loss, billing, or production-release decisions.

## Subagent Lifecycle

Do not treat subagents as one-shot commands. Manage them as collaborators.

1. Before spawning, define the objective, boundaries, expected evidence, and output shape.
2. Spawn agents only for separable work. Prefer 2-4 useful agents over many shallow agents.
3. Ask each agent for concrete evidence: file paths, symbols, commands run, observed outputs, and uncertainty.
4. Read interim or final outputs skeptically. If an output is vague, unsupported, contradictory, or opens a new risk, send a follow-up instruction before accepting it.
5. Cross-check important claims between agents when the task is risky or ambiguous.
6. Synthesize results in the parent thread. Do not simply concatenate subagent summaries.
7. Close completed agent threads after their findings have been integrated.

## Spawn Call Compatibility

Keep spawn calls compatible with the active Codex tool schema. The custom-agent TOML files are the place for model, reasoning, service tier, sandbox, and nickname configuration.

- Prefer the simplest spawn call that selects the agent type and sends an explicit task brief.
- Do not pass TOML-only or policy-only fields as `spawn_agent` arguments. Examples include `service_tier`, `model_reasoning_effort`, `model_verbosity`, `sandbox_mode`, `nickname_candidates`, and `max_depth`.
- Do not request a full conversation fork by default. Omit `fork_context` unless the active tool schema supports it and the child truly needs the complete current thread history.
- Default task briefs should include only the needed context: objective, boundaries, cwd, relevant files or commands, read/write permission, expected evidence, and output shape.
- For read-only delegation, state read-only scope in the task brief and rely on the selected read-only agent profile when available.
- If a spawn attempt is rejected because optional arguments conflict with the current environment, retry once with a minimal schema-compatible call instead of repeating the same shape.

## When to Spawn Which Agent

Prefer custom global agents from `C:\Users\sfr99\.codex\agents\` when available.

- `explorer` or `explorer_fast`: map files, symbols, data flow, and likely risk points before implementation.
- `worker` or `worker_fast`: implement bounded changes after the relevant paths are known.
- `reviewer`: perform final correctness/regression/test review.
- `security_auditor` or security-focused reviewers: inspect authorization, tenant isolation, secret exposure, injection, unsafe file handling, and data leakage.
- `migration_auditor` or migration reviewers: inspect schema, JPA/ORM mapping, rollout safety, compatibility, and index/constraint risks.
- `test_gap_analyst`: find missing or weak tests and propose concrete verification.
- `frontend_ux_reviewer`: review frontend UX, accessibility, responsive layout, loading/error states, and visual regressions.
- `ci_build_auditor`: inspect CI workflows, build scripts, package locks, Dockerfiles, and local-vs-CI command drift.
- `deployment_rollout_auditor`: inspect deployment configuration, regions, environment variables, release order, rollback paths, and cloud service wiring.
- `runtime_incident_analyst`: diagnose runtime failures from logs, database state, queues, callbacks, background jobs, and idempotency or concurrency symptoms.
- `docs_consistency_reviewer`: check README/docs/runbooks/progress notes for stale claims, missing evidence, path drift, and reader-facing clarity.
- `prompt_skill_auditor`: review `AGENTS.md`, skills, plugin prompts, and custom-agent TOML for executable instructions, schema compatibility, and policy conflicts.
- Domain-specific agents should be used when their scope matches the task better than a general agent.

If no specialized agent fits, use `default` for Deep mode and `default_fast` for quick bounded reconnaissance.

## Interactive Steering Rules

After a subagent reports back, continue interacting when any of the following is true:

- it lists conclusions without file-level evidence
- it says something is safe without explaining the checked path
- it reports uncertainty that can be reduced with another targeted read or command
- it conflicts with another agent
- it found a likely issue but not the minimal fix or verification path
- it ignored part of the task scope
- it proposes a broad rewrite where a smaller change may work

Useful follow-up patterns:

- "Verify this against the exact call path and return only evidence-backed findings."
- "Check whether this risk exists in tests/fixtures as well as production code."
- "Find the smallest patch surface and list files that should not be touched."
- "Challenge your previous conclusion. What would make it false?"
- "Compare your finding with the other agent's result and identify the disagreement."

## Parent Synthesis Rules

The parent agent owns the final judgment.

- Prefer evidence over confidence.
- Keep confirmed facts, plausible hypotheses, and unresolved risks separate.
- When agents disagree, resolve by checking code or state the remaining uncertainty explicitly.
- Do not claim verification unless tests, commands, or file reads actually support it.
- For user-facing summaries, lead with concrete findings or completed changes, then list verification and residual risks.

## Concurrency and Cost Control

- Use parallel agents for independent work, not for duplicate thinking.
- Keep agent fan-out bounded. More agents are not better when the task needs one coherent execution path.
- Keep delegation depth to one parent-to-child layer by policy; avoid recursive delegation unless explicitly needed.
- Use Fast mode for exploration, then Deep mode for final review on risky tasks.
- Fast mode can cost more credits; do not use it blindly for long-running deep reasoning.

## Subagent Naming

- Refer to subagents by their Codex UI nickname and operational role.
- The Codex UI display nickname is configured through global custom agents in `C:\Users\sfr99\.codex\agents\default.toml`, `C:\Users\sfr99\.codex\agents\explorer.toml`, and `C:\Users\sfr99\.codex\agents\worker.toml`.
- Treat the nickname returned by `spawn_agent` as the source of truth.
- Do not add a separate parent-provided task alias when spawning subagents.
- In Korean conversations, after a subagent is spawned, display a synced Korean alias by matching the returned UI nickname against `C:\Users\sfr99\.codex\subagent-aliases\blue-archive-students.json` when the match is unambiguous; use a format like `Haruka(하루카)`.
- If the UI nickname cannot be matched unambiguously, use the UI nickname alone.
- Only tell a subagent its returned UI nickname via `send_input` when it needs to self-reference that name.

## Repository Hygiene And Artifact Budget

Default policy: do not create persistent files unless they are necessary for the requested implementation, verification, or an explicitly requested deliverable.

Before creating any new file, first check whether the work can be completed by:

1. editing an existing source file,
2. editing an existing test file,
3. updating an existing canonical documentation/progress/report file,
4. reporting findings in the conversation only.

Do not create repository-local scratch artifacts, including:

- PLAN.md
- NOTES.md
- scratch*.md
- analysis*.md
- debug*.log
- temp*.txt
- ad-hoc report files
- per-agent report files
- duplicate progress files
- timestamped report files unless the task or an existing script contract explicitly requires them.

Temporary analysis must stay outside the repository, preferably under `/tmp/codex-*`.
Delete temporary files before the final response.

Subagents must not create files unless the parent explicitly gives them write permission.
For normal exploration, triage, review, and evidence gathering, subagents are read-only.

The parent agent is responsible for keeping the final repository diff small.
At the end of each task, report:

- changed files,
- newly created files, if any,
- why each new file was necessary,
- temporary files removed,
- verification commands run.
