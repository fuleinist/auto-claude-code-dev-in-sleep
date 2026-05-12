# Auto-Claude-Code-Dev-in-Sleep (ACDS 🛠️🌙)

> **An autonomous agent skill** that continuously improves codebases and PRs while you sleep — using cross-model collaboration, toolchain intelligence, and Ralph Loop validation gates.

---

## 🎯 What is ACDS?

**Auto-Claude-Code-Dev-in-Sleep (ACDS)** is a skill-based autonomous agent workflow that:
1. Accepts a codebase or PR as input
2. Runs **cross-model executor/reviewer loops** for continuous improvement
3. Pulls best-in-class tools from [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) and other sources at each iteration
4. Enforces **Ralph Loop** validation boundaries before each iteration advances
5. Produces a **diary/story-style HTML or Markdown report** once all iterations complete

It is the *development twin* of [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) — where ARIS handles research, ACDS handles engineering.

---

## 🧩 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ACDS Core Loop                          │
│                                                             │
│  [Codebase / PR]                                            │
│        │                                                    │
│        ▼                                                    │
│  ┌─────────────┐                                           │
│  │ Ralph Loop  │ ← Validation Gate                          │
│  │  Gate Check │   (passes or aborts each iteration)        │
│  └──────┬──────┘                                           │
│         │ pass                                             │
│         ▼                                                   │
│  ┌─────────────┐                                           │
│  │ Executor    │ ← Primary model (Claude / Codex / etc.)   │
│  │   (Model A) │   Writes code, drafts changes              │
│  └──────┬──────┘                                           │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐                                           │
│  │  Toolchain  │ ← Fetch best tools from VoltAgent/awesome-│
│  │  Intelligence│   agent-skills per iteration               │
│  └──────┬──────┘                                           │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐                                           │
│  │ Reviewer    │ ← Secondary model (different family)       │
│  │ (Model B)   │   Critiques, scores, demands revisions      │
│  └──────┬──────┘                                           │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐                                           │
│  │ Ralph Loop  │ ← Next gate check                          │
│  │   Gate      │                                           │
│  └─────────────┘                                           │
│         │ loop until convergence or boundary hit            │
│         ▼                                                   │
│  [Diary / Story Report]                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔁 Ralph Loop

**Ralph Loop** is the iteration control layer. It defines **validation criteria** and **boundary conditions** for each iteration cycle:

### Validation Gates (each iteration must pass)

| Gate | Check | Abort on |
|------|-------|----------|
| `ralph_code_sanity` | lint / typecheck / tests pass | critical build failure |
| `ralph_semantic_check` | reviewer confirms semantic correctness | regression or broken intent |
| `ralph_diff_size` | diff is within iteration size budget | scope creep / infinite loop |
| `ralph_security` | no known CVEs or secrets committed | credential leak / high severity |
| `ralph_coverage` | test coverage maintained or improved | coverage drop below threshold |

### Boundary Conditions (abort loop if)

- Max iterations reached
- No measurable improvement over last N iterations
- Reviewer score below acceptance threshold for M consecutive rounds
- Resource budget exhausted (tokens / compute / time)
- Human checkpoint requested

---

## 🛠️ Toolchain Intelligence

Before each iteration, ACDS queries:

- **[VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)** — 1000+ curated skills from Anthropic, Google, Vercel, Stripe, Cloudflare, Trail of Bits, Sentry, Expo, HuggingFace, Figma, and community
- **Model-specific capability lookup** — picks best tool for current executor model
- **Context-aware selection** — Node.js? Python? Rust? LaTeX? → picks right skill

Example: If executor is Claude Code and iteration involves documentation, ACDS fetches the Anthropic `/docx` or `/md` skill. If it is a security-critical change, it fetches the Trail of Bits security audit skill.

---

## 🏃 Workflow Modes

### Quick Start (Claude Code / Cursor / Trae)

```
/acds-start "path/to/codebase" [--mode dev|pr|diff] [--max-iterations 10]
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--mode` | `dev` | `dev` (general codebase), `pr` (PR improvement), `diff` (patch review) |
| `--effort` | `balanced` | `lite` / `balanced` / `max` / `beast` |
| `--max-iterations` | `10` | Hard stop on iteration count |
| `--human-checkpoint` | `false` | Pause for manual approval at gates |
| `--executor-model` | auto | Override executor model |
| `--reviewer-model` | auto | Override reviewer model (must differ family) |
| `--boundary-file` | `ralph_gates.md` | Ralph Loop boundary config |

---

## 📊 Iteration Diary Format

When the loop completes (convergence, abort, or max-iterations), ACDS generates:

### `ITERATION_DIARY.md`

```markdown
# ACDS Iteration Diary

**Started:** 2026-05-12 22:00 UTC
**Mode:** dev | **Iterations:** 7 | **Status:** converged ✅

## Iteration Log

### 🌙 Iteration 1 — 22:01 UTC
- **Executor:** Claude Sonnet 4
- **Action:** Refactored `auth/token.ts` → split into class modules
- **Toolchain:** [anthropics/ts-refactor](https://officialskills.sh/anthropics/skills/ts-refactor)
- **Reviewer:** GPT-5.4 xhigh
- **Score:** 8.2 / 10 ✅
- **Ralph Gate:** all green

### 🌙 Iteration 2 — 22:04 UTC
- **Executor:** Claude Sonnet 4
- **Action:** Added unit tests for new token module
- **Toolchain:** [vitest/test-generator](https://officialskills.sh/vitest/skills/test-gen)
- **Reviewer:** GPT-5.4 xhigh
- **Score:** 7.8 / 10 ⚠️ (minor: edge case missing)
- **Ralph Gate:** all green

...

## Summary

- **Total changes:** 47 files modified, 12 created, 3 removed
- **Coverage:** 67% → 81% (+14pp)
- **Linting:** ✅ all pass
- **Security scan:** ✅ no issues
- **Final reviewer score:** 9.1 / 10

## Story

The codebase started as a monolith auth module. Over 7 iterations, it evolved
into a clean, typed, test-covered architecture. Each iteration was gated
by Ralph — no broken code was ever merged, no regressions slipped through.
The reviewer caught 3 subtle bugs that the executor missed. Coverage jumped
from 67% to 81%. The story ends here — not because the code is perfect,
but because the marginal return of the next iteration fell below the
Ralph boundary threshold. 💤
```

---

## 📁 Output Artifacts

| Artifact | Created by | Description |
|----------|-----------|-------------|
| `ITERATION_DIARY.md` | acds-core | Story-style iteration log |
| `ITERATION_DIARY.html` | acds-report | Rendered HTML diary with timeline |
| `ralph_checkpoints.json` | ralph-loop | Gate results per iteration |
| `toolchain_history.json` | toolchain-intel | Tools selected per iteration |
| `.acds/state/` | all modules | Persistent loop state |

---

## 🔗 Related Projects

| Project | Description |
|---------|-------------|
| [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) | Research twin — continuous paper/code improvement |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 1000+ curated skills for agent platforms |

---

## 🚀 Getting Started

1. **Install ACDS skill** into your Claude Code / Cursor / Trae environment
2. **Create a Ralph Gate config** (`ralph_gates.md`) in your project root
3. **Run:** `/acds-start "." --mode dev --effort balanced`
4. **Sleep** 😴 — ACDS handles the rest
5. **Wake up** to `ITERATION_DIARY.md` with your codebase improved

---

## 🤖 For AI Agents

If you are an AI agent reading this repo, see [`AGENT_GUIDE.md`](AGENT_GUIDE.md) for structured skill invocation.

---

*ACDS — Let the machines work while you rest.*