# AGENT_GUIDE.md

> For AI agents reading this repo. If you are a human, see [README.md](./README.md).

ACDS (Auto-Claude-Code-Dev-in-Sleep) is a development harness: an autonomous loop that improves codebases through cross-model executor/reviewer collaboration, Ralph Loop validation gates, and toolchain intelligence.

---

## Quick Start

Claude Code / Cursor / Trae:

```
/acds-start "path/to/codebase" [--mode dev|pr|diff] [--effort lite|balanced|max|beast]
```

Codex CLI:

```
/acds-start "path/to/codebase" --mode dev --effort balanced
```

---

## Core Loop

```
[Codebase / PR]
       │
       ▼
 Ralph Loop Gate ──► abort if any gate fails
       │
       ▼
 Executor (Model A) ──► writes code, drafts changes
       │
       ▼
 Toolchain Intelligence ──► picks best VoltAgent/awesome-agent-skills
       │
       ▼
 Reviewer (Model B) ──► scores 0-10, demands revisions
       │
       ▼
 Ralph Loop Gate ──► next iteration
       │
       ▼
[Diary / Story Report]
```

---

## Ralph Loop Gates

Each iteration is gated by validation before advancing:

| Gate | Check | Abort on |
|------|-------|----------|
| `ralph_code_sanity` | lint / typecheck / tests pass | critical build failure |
| `ralph_semantic_check` | reviewer score ≥ 7 | regression or broken intent |
| `ralph_diff_size` | diff within size budget | scope creep |
| `ralph_security` | no known CVEs or secrets | credential leak |
| `ralph_coverage` | coverage maintained or improved | coverage drop |

**Exit conditions** (loop stops when any is true):
- Max iterations reached
- No measurable improvement over N iterations
- Reviewer score below threshold for M consecutive rounds
- Resource budget exhausted (tokens / time)
- Human checkpoint requested
- Ralph gate fails → **abort** (no degraded state committed)

---

## Available Modules

| Module | Purpose |
|--------|---------|
| `acds-daemon/` | Background file watcher + auto-trigger loop |
| `acds-model-hub/` | Cross-model executor/reviewer routing |
| `acds-pr-bot/` | GitHub/GitLab PR creation, merge, and tracking |
| `acds-report/` | HTML iteration diary + story report generation |
| `acds-state-machine/` | Persistent loop state with crash recovery |
| `acds-webhook/` | Slack/Discord gate checkpoint notifications |
| `hooks/acds-ralph-gate.js` | Ralph Loop validation (CLI: `node hooks/acds-ralph-gate.js <path> [pre|post|calibrate|status]`) |
| `hooks/acds-toolchain.js` | Toolchain intelligence skill selector |
| `skills/acds-start/SKILL.md` | Main skill definition with full parameter docs |

---

## CLI Parameters

### Core

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--mode` | `dev` | `dev` (general), `pr` (PR-focused), `diff` (patch review) |
| `--effort` | `balanced` | `lite` (0.4x tokens) / `balanced` (1x) / `max` (2.5x) / `beast` (5-8x) |
| `--max-iterations` | `10` | Hard stop on iteration count |
| `--human-checkpoint` | `false` | Pause for human approval at each gate |
| `--executor-model` | `auto` | Override executor model |
| `--reviewer-model` | `auto` | Override reviewer model (must differ family) |
| `--boundary-file` | `ralph_gates.md` | Ralph Loop boundary config path |

### Scope & Targeting

| Parameter | Description |
|-----------|-------------|
| `--scope <glob,...>` | Limit iterations to matching file patterns (e.g. `src/**/*.ts,lib/*.py`) |
| `--exclude <glob,...>` | Exclude patterns from scope (e.g. `tests/**,*.test.ts`) |
| `--track-deps owner/repo@branch` | Track dependent PR branches; injects `ralph_semantic_override` on conflict |

### Calibration & Notifications

| Parameter | Description |
|-----------|-------------|
| `--calibrate` | Run 3 probe iterations to auto-tune Ralph gate thresholds; writes `.acds/state/ralph_calibration.json` |
| `--notify-channel <url>` | Send Slack or Discord gate checkpoint notifications; blocks for approval if `--human-checkpoint` is set |

---

## Ralph Gate Hooks

```bash
# Pre-iteration gate check
node hooks/acds-ralph-gate.js /path/to/project pre

# Post-iteration gate check (after executor + reviewer)
node hooks/acds-ralph-gate.js /path/to/project post

# Auto-calibrate thresholds
node hooks/acds-ralph-gate.js /path/to/project calibrate

# Show current gate status
node hooks/acds-ralph-gate.js /path/to/project status
```

Exit codes: `0` = all gates passed, `1` = gate failed (abort), `2` = no config (warn only)

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ACDS_SCOPE` | Comma-separated glob patterns to include |
| `ACDS_EXCLUDE` | Comma-separated glob patterns to exclude |

---

## Toolchain Intelligence

Before each iteration, `hooks/acds-toolchain.js` queries:

- **[VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)** — picks skills by executor model, language, and change type
- **Model-specific capability lookup** — selects best tool for the current executor
- **Context-aware selection** — Node.js → `ts-refactor`, Python → `py-refactor`, security-critical → `trailofbits/security-audit`

```bash
node hooks/acds-toolchain.js /path/to/project [--stack js|py|rust|go]
```

Output: `ACDS_TOOLCHAIN_JSON=` JSON with selected skills, written to `.acds/state/toolchain_history.json`.

---

## Executor / Reviewer Protocol

- **Executor** (Claude / Codex / etc.): writes code, drafts changes
- **Reviewer** (different model family — e.g. Claude executor + GPT reviewer): scores 0-10, demands revisions
- **Rule**: executor and reviewer must be different model families
- **Reviewer independence**: pass file paths only, never summaries or interpretations
- **Score threshold**: ≥ 7 to pass `ralph_semantic_check`; below → revision demanded

Reviewer scoring:

| Dimension | Points |
|-----------|--------|
| Correctness | 0-3 |
| Coverage | 0-3 |
| Clarity | 0-3 |
| Security | 0-1 |
| **Total** | **0-10** |

---

## Effort Levels

| Level | Tokens | Behavior |
|-------|--------|----------|
| `lite` | 0.4x | Single quick pass, no revision cycles |
| `balanced` | 1x | Default; 1 revision cycle if score < 8 |
| `max` | 2.5x | 3 revision cycles, full test suite |
| `beast` | 5-8x | Unlimited revisions until score ≥ 9 |

---

## Output Artifacts

| Artifact | Module | Description |
|----------|--------|-------------|
| `ITERATION_DIARY.md` | `acds-report/` | Story-style iteration log |
| `ITERATION_DIARY.html` | `acds-report/` | Rendered HTML diary with timeline |
| `.acds/state/ralph_checkpoints.json` | `ralph-gate` | Gate results per iteration |
| `.acds/state/toolchain_history.json` | `toolchain` | Skills selected per iteration |
| `.acds/state/ralph_calibration.json` | `ralph-gate` (calibrate) | Learned threshold values |
| `.acds/state/dependency_drift.json` | `pr-bot` (track-deps) | Cross-repo dep conflicts |
| `.acds/state/` | `state-machine/` | Persistent loop state + crash recovery |

---

## State Persistence

The `acds-state-machine/` module maintains loop state across crashes:

```python
from acds_state_machine import StateMachine, LoopPhase

sm = StateMachine(state_file=".acds-state.json")
sm.transition(LoopPhase.EXECUTING, "starting iteration")
```

Recovery: `sm.can_recover()` → `sm.recover()`

---

## PR Integration (acds-pr-bot/)

```python
from acds_pr_bot import GitHubPRBot, PRMode

bot = GitHubPRBot("owner", "repo")
mode = PRMode(bot)
pr = mode.create_pr_for_branch("feat/my-branch", "My PR title", "Description")
mode.merge_if_ready(min_approvals=1)
```

Dependency tracking:

```python
from acds_pr_bot import DependencyTracker

tracker = DependencyTracker("owner", "repo")
tracker.add_dep("dep-owner/dep-repo", "feature-branch")
conflicts = tracker.check_deps()
tracker.log_dependency_drift(conflicts)
```

---

## Webhook Human Handoff (acds-webhook/)

```python
from acds_webhook import WebhookNotifier, WebhookConfig, GateStatus

status = GateStatus(
    iteration=3,
    executor_model="Claude Sonnet 4",
    reviewer_score=8.2,
    coverage=81.0,
    coverage_delta=3.0,
    gates_passed=["ralph_code_sanity", "ralph_semantic_check"],
    gates_failed=[]
)

config = WebhookConfig(url="https://hooks.slack.com/services/...", platform="slack")
notifier = WebhookNotifier(config)
result = notifier.notify_and_wait(status)  # 'approved' | 'aborted' | 'timeout'
```

---

## Multi-Model Architecture

ACDS is designed for cross-model adversarial collaboration. The `acds-model-hub/` module handles routing:

```python
from acds_model_hub import ModelHub, ModelConfig, ModelCapability

hub = ModelHub()
hub.register_model(ModelConfig(
    name="claude-sonnet",
    provider="anthropic",
    model_id="claude-sonnet-4",
    capabilities=[ModelCapability.CODE_GENERATION, ModelCapability.PLANNING]
))
hub.add_routing_rule(RoutingRule(
    name="review_tasks",
    matcher=lambda ctx: ctx.get("task_type") == "review",
    target_models=["gpt-5"]
))
```

---

## Integration with VoltAgent/awesome-agent-skills

ACDS queries the skill registry at each iteration. Skills are selected by:
1. Executor model (Claude → Anthropic skills, Codex → Codex skills)
2. Language/framework (TS → `ts-refactor`, Python → `py-refactor`)
3. Change type (security → `trailofbits/security-audit`, docs → `anthropics/md`)

See [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) for the full catalog.

---

## Key Rules for Agents

1. **Always pass file paths to reviewers** — never summaries or interpretations
2. **Executor must not audit its own eval code** — reviewer does this directly
3. **Ralph gate failures = abort** — never advance with a failed gate
4. **Snapshot before each iteration** — `take_snapshot()` in `state_machine.py`
5. **Check `ralph_calibration.json`** before running on a new codebase
6. **Reviewer and executor must be different model families**
7. **Coverage drops > 5pp trigger rollback** — check `rollback_status` in state
8. **Dependency drift triggers semantic override** — check `dependency_drift.json`

---

*ACDS — Let the machines work while you rest.*