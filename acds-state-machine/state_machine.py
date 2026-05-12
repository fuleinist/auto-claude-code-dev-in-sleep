"""
acds-state-machine: Persistent loop state + crash recovery
Manages ACDS loop execution state with crash recovery capabilities.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from threading import Lock, Event
from datetime import datetime

logger = logging.getLogger(__name__)


class LoopPhase(Enum):
    """ACDS loop execution phases."""
    IDLE = auto()
    PLANNING = auto()
    EXECUTING = auto()
    REVIEWING = auto()
    COMMITTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    PAUSED = auto()


class Transition:
    """Represents a state transition with metadata."""
    def __init__(
        self,
        from_state: LoopPhase,
        to_state: LoopPhase,
        reason: str = "",
        data: Optional[Dict] = None
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        self.data = data or {}
        self.timestamp = time.time()


@dataclass
class LoopState:
    """Complete state of the ACDS loop."""
    phase: str = "IDLE"
    iteration: int = 0
    task: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    last_activity: float = field(default_factory=time.time)
    error_count: int = 0
    max_errors: int = 5
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    transitions: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateSnapshot:
    """Serializable snapshot for persistence."""
    version: str = "1.0"
    state: Dict[str, Any]
    checksum: str = ""
    
    def to_dict(self) -> Dict:
        return {"version": self.version, "state": self.state, "checksum": self.checksum}


class StateMachine:
    """
    Persistent state machine for ACDS loop management.
    Handles state transitions, persistence, and crash recovery.
    """
    def __init__(
        self,
        state_file: Optional[str] = None,
        auto_save: bool = True,
        save_interval: float = 30.0,
        on_transition: Optional[Callable] = None
    ):
        self.state_file = Path(state_file) if state_file else Path(".acds-state.json")
        self.auto_save = auto_save
        self.save_interval = save_interval
        self.on_transition = on_transition
        
        self._state = LoopState()
        self._lock = Lock()
        self._running = Event()
        self._last_save = time.time()
        self._transition_history: List[Transition] = []
        
        self._load_or_init()

    def _load_or_init(self):
        """Load existing state or initialize fresh."""
        if self.state_file.exists():
            try:
                self._load_state()
            except Exception as e:
                logger.warning(f"Failed to load state: {e}, starting fresh")
                self._state = LoopState()
        else:
            self._state = LoopState()

    def _load_state(self):
        """Load state from file."""
        with open(self.state_file) as f:
            data = json.load(f)
            snapshot = StateSnapshot(**data)
            state_dict = snapshot.state
            
            self._state.phase = state_dict.get("phase", "IDLE")
            self._state.iteration = state_dict.get("iteration", 0)
            self._state.task = state_dict.get("task", "")
            self._state.context = state_dict.get("context", {})
            self._state.error_count = state_dict.get("error_count", 0)
            self._state.metadata = state_dict.get("metadata", {})
            self._state.transitions = state_dict.get("transitions", [])
            
            if state_dict.get("started_at"):
                self._state.started_at = state_dict["started_at"]
            if state_dict.get("completed_at"):
                self._state.completed_at = state_dict["completed_at"]

    def save(self) -> bool:
        """Persist current state to disk."""
        with self._lock:
            try:
                state_dict = {
                    "phase": self._state.phase,
                    "iteration": self._state.iteration,
                    "task": self._state.task,
                    "context": self._state.context,
                    "error_count": self._state.error_count,
                    "max_errors": self._state.max_errors,
                    "started_at": self._state.started_at,
                    "completed_at": self._state.completed_at,
                    "transitions": self._state.transitions[-50:],  # Keep last 50
                    "metadata": self._state.metadata,
                    "last_activity": time.time()
                }
                
                snapshot = StateSnapshot(state=state_dict)
                with open(self.state_file, "w") as f:
                    json.dump(snapshot.to_dict(), f, indent=2)
                
                self._last_save = time.time()
                return True
            except Exception as e:
                logger.error(f"Failed to save state: {e}")
                return False

    def _should_save(self) -> bool:
        """Check if state should be auto-saved."""
        return self.auto_save and (time.time() - self._last_save) >= self.save_interval

    def transition(
        self,
        to: LoopPhase,
        reason: str = "",
        data: Optional[Dict] = None
    ) -> bool:
        """Transition to a new phase."""
        with self._lock:
            from_phase = LoopPhase[self._state.phase]
            
            if not self._is_valid_transition(from_phase, to):
                logger.warning(f"Invalid transition: {from_phase} -> {to}")
                return False
            
            transition = Transition(from_phase, to, reason, data)
            self._transition_history.append(transition)
            
            self._state.phase = to.name
            self._state.last_activity = time.time()
            
            if to == LoopPhase.PLANNING and not self._state.started_at:
                self._state.started_at = time.time()
            elif to == LoopPhase.COMPLETED:
                self._state.completed_at = time.time()
            
            self._state.transitions.append({
                "from": from_phase.name,
                "to": to.name,
                "reason": reason,
                "timestamp": time.time()
            })
            
            if self._should_save():
                self.save()
            
            if self.on_transition:
                self.on_transition(transition)
            
            return True

    def _is_valid_transition(self, from_state: LoopPhase, to_state: LoopPhase) -> bool:
        """Validate state transition."""
        valid_paths = {
            LoopPhase.IDLE: [LoopPhase.PLANNING, LoopPhase.PAUSED],
            LoopPhase.PLANNING: [LoopPhase.EXECUTING, LoopPhase.FAILED, LoopPhase.IDLE],
            LoopPhase.EXECUTING: [LoopPhase.REVIEWING, LoopPhase.FAILED, LoopPhase.PAUSED],
            LoopPhase.REVIEWING: [LoopPhase.COMMITTING, LoopPhase.EXECUTING, LoopPhase.FAILED],
            LoopPhase.COMMITTING: [LoopPhase.COMPLETED, LoopPhase.FAILED, LoopPhase.EXECUTING],
            LoopPhase.COMPLETED: [LoopPhase.IDLE, LoopPhase.PLANNING],
            LoopPhase.FAILED: [LoopPhase.IDLE, LoopPhase.PLANNING],
            LoopPhase.PAUSED: [LoopPhase.EXECUTING, LoopPhase.IDLE],
        }
        return to_state in valid_paths.get(from_state, [])

    def start_iteration(self, task: str) -> bool:
        """Start a new iteration."""
        return self.transition(LoopPhase.PLANNING, f"Starting iteration for: {task}")

    def record_error(self, error: str) -> bool:
        """Record an error and check for failure threshold."""
        self._state.error_count += 1
        self._state.metadata["last_error"] = {
            "message": error,
            "timestamp": time.time()
        }
        
        if self._state.error_count >= self._state.max_errors:
            return self.transition(LoopPhase.FAILED, f"Max errors ({self._state.max_errors}) reached")
        
        return True

    def reset_errors(self):
        """Reset error counter."""
        self._state.error_count = 0

    def get_state(self) -> Dict[str, Any]:
        """Get current state as dict."""
        with self._lock:
            return {
                "phase": self._state.phase,
                "iteration": self._state.iteration,
                "task": self._state.task,
                "context": self._state.context,
                "error_count": self._state.error_count,
                "is_running": self._running.is_set(),
                "started_at": self._state.started_at,
                "completed_at": self._state.completed_at,
                "last_activity": self._state.last_activity
            }

    def update_context(self, key: str, value: Any):
        """Update context value."""
        with self._lock:
            self._state.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context value."""
        return self._state.context.get(key, default)

    def can_recover(self) -> bool:
        """Check if current state allows recovery."""
        return self._state.phase in ["FAILED", "PAUSED", "EXECUTING"]

    def recover(self) -> bool:
        """Attempt to recover from crash/failure."""
        if not self.can_recover():
            return False
        
        current = LoopPhase[self._state.phase]
        
        recovery_map = {
            LoopPhase.FAILED: LoopPhase.IDLE,
            LoopPhase.PAUSED: LoopPhase.EXECUTING,
            LoopPhase.EXECUTING: LoopPhase.EXECUTING,
        }
        
        target = recovery_map.get(current, LoopPhase.IDLE)
        return self.transition(target, "Crash recovery")

    def clear(self):
        """Reset state completely."""
        with self._lock:
            self._state = LoopState()
            self._transition_history.clear()
            if self.state_file.exists():
                self.state_file.unlink()

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get transition history."""
        return self._state.transitions[-limit:]


class PersistentStateMachine(StateMachine):
    """Extended state machine with automatic persistence."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._watchdog = Event()
    
    def run_with_watchdog(self, tick_interval: float = 10.0):
        """Run watchdog that auto-saves state."""
        self._watchdog.set()
        
        while self._watchdog.is_set():
            time.sleep(tick_interval)
            if self._running.is_set():
                self.save()

    def stop_watchdog(self):
        """Stop the watchdog."""
        self._watchdog.clear()


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ACDS State Machine - Persistent loop state")
    parser.add_argument("--state-file", default=".acds-state.json", help="State file path")
    parser.add_argument("--phase", help="Set current phase")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--reset", action="store_true", help="Reset state")

    args = parser.parse_args()

    sm = StateMachine(state_file=args.state_file)

    if args.reset:
        sm.clear()
        print("State reset")
    elif args.status:
        state = sm.get_state()
        print(json.dumps(state, indent=2))
    elif args.phase:
        try:
            phase = LoopPhase[args.phase.upper()]
            sm.transition(phase, "CLI transition")
            print(f"Transitioned to {phase.name}")
        except KeyError:
            print(f"Invalid phase: {args.phase}")