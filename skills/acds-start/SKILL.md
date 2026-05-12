---
name: acds:start
description: "Auto-Claude-Code-Dev-in-Sleep: run autonomous cross-model improvement loop with Ralph Loop gates. Usage: acds:start <path> [--mode dev|pr|diff] [--max-iterations N] [--effort lite|balanced|max|beast] [--human-checkpoint]"
argument-hint: "<path> [--mode dev|pr|diff] [--max-iterations N] [--effort lite|balanced|max|beast] [--human-checkpoint]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - exec
  - Edit
  - Task
  - Agent
  - WebFetch
  - WebSearch
---

<objective>
Run the ACDS (Auto-Claude-Code-Dev-in-Sleep) autonomous improvement loop on the target codebase or PR. Each cycle: Ralph Loop gate → Executor (primary model) → Toolchain Intelligence → Reviewer (secondary model) → next gate. Produces ITERATION_DIARY.md on completion.

Target: the codebase at the specified path. If "." or omitted, use current working directory.
</objective>

<context>
ACDS Architecture:
- Ralph Loop: validation gates before each iteration (code_sanity, semantic_check, diff_size, security, coverage)
- Executor: primary model executes code changes
- Toolchain Intelligence: fetches best skills per iteration from VoltAgent/awesome-agent-skills
- Reviewer: secondary model (different family) scores and demands revisions
- Loop until: convergence, max-iterations, no improvement, resource budget, or human checkpoint

Ralph Gates (abort loop if):
- ralph_code_sanity: lint/typecheck/tests pass — abort on critical build failure
- ralph_semantic_check: reviewer confirms correctness — abort on regression
- ralph_diff_size: diff within size budget — abort on scope creep
- ralph_security: no CVEs/secrets committed — abort on credential leak
- ralph_coverage: coverage maintained/improved — abort on coverage drop

Boundary conditions:
- max_iterations reached
- no measurable improvement over last N iterations
- reviewer score below threshold for M consecutive rounds
- resource budget exhausted
- human checkpoint requested

Output artifacts:
- ITERATION_DIARY.md — story-style iteration log
- ITERATION_DIARY.html — rendered HTML diary
- ralph_checkpoints.json — gate results per iteration
- toolchain_history.json — tools selected per iteration
- .acds/state/ — persistent loop state
</context>

<process>
## ACDS Main Loop

### Step 1: Initialize
1. Parse arguments (path, mode, max_iterations, effort, human_checkpoint)
2. Check for ralph_gates.md in project root — use default gates if missing
3. Create .acds/state/ directory
4. Initialize state: cycle=0, score=0, improvements=0, artifacts={}

### Step 2: Ralph Loop Gate Check (pre-iteration)
Check all gates from ralph_gates.md or defaults:
- ralph_code_sanity: run lint + typecheck + tests
- ralph_diff_size: check current diff is within budget
If any gate fails → ABORT, generate partial diary with abort reason.

### Step 3: Executor Phase (Model A)
1. Analyze codebase structure, identify top 3 improvement targets
2. Context-aware toolchain selection: pick best skills for current stack (Node.js → ts-refactor, Python → py-refactor, etc.)
3. Execute improvements: code changes, refactors, tests
4. Track diff size and resource usage

### Step 4: Toolchain Intelligence
- Query VoltAgent/awesome-agent-skills for relevant skills based on:
  - Executor model (Claude, Codex, etc.)
  - Language/framework detected
  - Change type (refactor, test, docs, security)
- Log selected tools to toolchain_history.json

### Step 5: Reviewer Phase (Model B)
- Simulate cross-model review (since single-model: do critical review as different perspective)
- Score on: correctness (0-3), coverage (0-3), clarity (0-3), security (0-1)
- Total: 10-point scale
- If score < 7 → demand revision, increment revision count
- If score >= 7 → pass gate

### Step 6: Ralph Loop Gate (post-iteration)
- ralph_semantic_check: reviewer score >= 7
- ralph_security: no new vulnerabilities detected
- ralph_coverage: tests added or maintained
If all pass → advance to next iteration.

### Step 7: Loop or Converge
- If score improvement plateaued (3 consecutive iterations < 0.5pt gain) → CONVERGENCE
- If max_iterations reached → STOP
- If any boundary hit → ABORT
- Else → goto Step 2 with next cycle

### Step 8: Generate Diary
Write ITERATION_DIARY.md and ITERATION_DIARY.html with:
- All iteration logs
- Summary stats
- Story narrative
- Ralph gate results

## Effort presets (cycle depth per iteration):
- lite: 1 quick pass, no revision cycles
- balanced: 1 revision cycle if score < 8
- max: 3 revision cycles, full test suite
- beast: unlimited revisions until score >= 9

## Mode behaviour:
- dev: general codebase improvement
- pr: PR-focused (target changed files only)
- diff: patch review mode