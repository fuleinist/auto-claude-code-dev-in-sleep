# acds-state-machine

Persistent loop state + crash recovery for auto-claude-code-dev-in-sleep.

## Overview

The `acds-state-machine` module provides persistent state management for the ACDS loop with crash recovery capabilities.

## Features

- **Phase Management**: IDLE → PLANNING → EXECUTING → REVIEWING → COMMITTING → COMPLETED
- **State Persistence**: Automatic JSON-based state saving
- **Crash Recovery**: Resume from FAILED, PAUSED, or EXECUTING states
- **Transition History**: Track all state changes with metadata
- **Context Storage**: Store task context and metadata
- **Error Tracking**: Monitor error counts with configurable thresholds

## Installation

```bash
pip install acds-state-machine
```

## Usage

### Basic State Machine

```python
from acds_state_machine import StateMachine, LoopPhase

sm = StateMachine(state_file=".acds-state.json")

# Start iteration
sm.start_iteration("Implement feature X")

# Transition through phases
sm.transition(LoopPhase.EXECUTING, "Starting work")
sm.transition(LoopPhase.REVIEWING, "Work complete")

# Handle errors
sm.record_error("API timeout")
if not sm.can_recover():
    sm.transition(LoopPhase.FAILED, "Too many errors")
```

### Crash Recovery

```python
from acds_state_machine import StateMachine

sm = StateMachine()

# Check if recovery possible
if sm.can_recover():
    sm.recover()
    print("Recovered from previous state")
```

### CLI

```bash
python -m acds_state_machine --status
python -m acds_state_machine --phase EXECUTING
python -m acds_state_machine --reset
```

## Loop Phases

| Phase | Description |
|-------|-------------|
| `IDLE` | No active task |
| `PLANNING` | Analyzing task and planning approach |
| `EXECUTING` | Performing code changes |
| `REVIEWING` | Validating changes |
| `COMMITTING` | Creating commits/PRs |
| `COMPLETED` | Task finished successfully |
| `FAILED` | Task failed after max errors |
| `PAUSED` | Temporarily paused |

## State File

```json
{
  "version": "1.0",
  "state": {
    "phase": "EXECUTING",
    "iteration": 3,
    "task": "Implement login",
    "context": {},
    "error_count": 0,
    "transitions": [...]
  }
}
```

## License

MIT