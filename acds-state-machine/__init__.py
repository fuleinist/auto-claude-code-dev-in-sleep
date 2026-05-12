"""acds-state-machine: Persistent loop state + crash recovery."""

from .state_machine import (
    LoopPhase,
    Transition,
    LoopState,
    StateSnapshot,
    StateMachine,
    PersistentStateMachine,
)

__version__ = "0.1.0"
__all__ = [
    "LoopPhase",
    "Transition", 
    "LoopState",
    "StateSnapshot",
    "StateMachine",
    "PersistentStateMachine",
]