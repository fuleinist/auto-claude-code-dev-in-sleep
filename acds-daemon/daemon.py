"""
acds-daemon: Background watcher + auto-trigger loop
Monitors repo state and triggers ACDS loop on file changes/events.
"""
import time
import logging
from pathlib import Path
from threading import Thread, Event
from typing import Optional, Callable, Dict, Any
import hashlib
import json

logger = logging.getLogger(__name__)


class WatchEvent:
    """Represents a detected file system or Git event."""
    def __init__(self, event_type: str, path: str, metadata: Optional[Dict] = None):
        self.event_type = event_type
        self.path = path
        self.metadata = metadata or {}
        self.timestamp = time.time()


class DaemonConfig:
    """Configuration for the daemon watcher."""
    def __init__(
        self,
        watch_paths: list[str] = None,
        poll_interval: float = 5.0,
        debounce_seconds: float = 2.0,
        trigger_on: list[str] = None,
        ignore_patterns: list[str] = None,
        max_queue_size: int = 1000,
    ):
        self.watch_paths = watch_paths or ["."]
        self.poll_interval = poll_interval
        self.debounce_seconds = debounce_seconds
        self.trigger_on = trigger_on or ["modify", "create", "delete"]
        self.ignore_patterns = ignore_patterns or [
            ".git/*", "__pycache__/*", "*.pyc", "node_modules/*",
            ".venv/*", "*.log", ".tmp/*"
        ]
        self.max_queue_size = max_queue_size


class FileHasher:
    """Computes lightweight file signatures for change detection."""
    @staticmethod
    def hash_file(path: Path) -> Optional[str]:
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read(8192)).hexdigest()[:16]
        except Exception:
            return None


class EventQueue:
    """Thread-safe event queue with debouncing support."""
    def __init__(self, max_size: int = 1000):
        self._queue: list[WatchEvent] = []
        self._lock = Event()
        self.max_size = max_size

    def put(self, event: WatchEvent):
        with self._lock:
            if len(self._queue) < self.max_size:
                self._queue.append(event)

    def drain(self) -> list[WatchEvent]:
        with self._lock:
            events = self._queue[:]
            self._queue.clear()
            return events

    def __len__(self):
        return len(self._queue)


class DaemonWatcher:
    """
    Background watcher that monitors file system and Git events.
    Triggers callback when changes are detected.
    """
    def __init__(self, config: Optional[DaemonConfig] = None, on_trigger: Optional[Callable] = None):
        self.config = config or DaemonConfig()
        self.on_trigger = on_trigger
        self._stop = Event()
        self._paused = Event()
        self._paused.set()  # Start unpaused
        self._thread: Optional[Thread] = None
        self._event_queue = EventQueue(self.config.max_queue_size)
        self._file_hashes: Dict[str, str] = {}
        self._last_trigger_time: float = 0

    def start(self, blocking: bool = True):
        """Start the daemon watcher."""
        self._stop.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if blocking:
            self._thread.join()

    def stop(self):
        """Stop the daemon watcher."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def pause(self):
        """Pause event detection."""
        self._paused.clear()

    def resume(self):
        """Resume event detection."""
        self._paused.set()

    def _run_loop(self):
        """Main event polling loop."""
        logger.info("Daemon watcher started")
        while not self._stop.is_set():
            self._scan_and_emit()
            time.sleep(self.config.poll_interval)

    def _scan_and_emit(self):
        """Scan monitored paths and emit events."""
        if not self._paused.is_set():
            return

        events = []
        for watch_path in self.config.watch_paths:
            path = Path(watch_path)
            if not path.exists():
                continue

            if path.is_file():
                events.extend(self._check_file(path))
            else:
                for fp in path.rglob("*"):
                    if self._should_ignore(fp):
                        continue
                    if fp.is_file():
                        events.extend(self._check_file(fp))

        for event in events:
            self._event_queue.put(event)

        # Process queue with debouncing
        self._process_queue()

    def _should_ignore(self, path: Path) -> bool:
        """Check if path matches ignore patterns."""
        path_str = str(path)
        for pattern in self.config.ignore_patterns:
            if pattern.replace("*", "") in path_str:
                return True
        return False

    def _check_file(self, path: Path) -> list[WatchEvent]:
        """Check file for changes and return events."""
        key = str(path)
        current_hash = FileHasher.hash_file(path)

        if key not in self._file_hashes:
            if current_hash:
                self._file_hashes[key] = current_hash
                return [WatchEvent("create", key)]
            return []

        if current_hash != self._file_hashes[key]:
            self._file_hashes[key] = current_hash
            return [WatchEvent("modify", key)]

        return []

    def _process_queue(self):
        """Process queued events with debouncing."""
        now = time.time()
        if now - self._last_trigger_time < self.config.debounce_seconds:
            return

        events = self._event_queue.drain()
        if not events:
            return

        logger.info(f"Detected {len(events)} events")
        self._last_trigger_time = now

        if self.on_trigger:
            try:
                self.on_trigger(events)
            except Exception as e:
                logger.error(f"Trigger callback failed: {e}")


class DaemonManager:
    """
    Manages multiple daemon watchers and provides
    a high-level interface for daemon control.
    """
    def __init__(self):
        self._watchers: Dict[str, DaemonWatcher] = {}
        self._processes: Dict[str, Any] = {}

    def add_watcher(self, name: str, config: DaemonConfig, on_trigger: Callable):
        """Add and start a named watcher."""
        watcher = DaemonWatcher(config, on_trigger)
        self._watchers[name] = watcher
        logger.info(f"Added watcher: {name}")

    def start_all(self):
        """Start all configured watchers."""
        for name, watcher in self._watchers.items():
            watcher.start(blocking=False)
            logger.info(f"Started watcher: {name}")

    def stop_all(self):
        """Stop all watchers."""
        for name, watcher in self._watchers.items():
            watcher.stop()
            logger.info(f"Stopped watcher: {name}")

    def status(self) -> Dict[str, Any]:
        """Return status of all watchers."""
        return {
            "watchers": {name: {"active": not w._stop.is_set()} for name, w in self._watchers.items()},
            "total_events": sum(len(w._event_queue) for w in self._watchers.values())
        }


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ACDS Daemon - Background watcher")
    parser.add_argument("--watch", nargs="+", default=["."], help="Paths to watch")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval in seconds")
    parser.add_argument("--daemonize", action="store_true", help="Run in background")

    args = parser.parse_args()

    config = DaemonConfig(
        watch_paths=args.watch,
        poll_interval=args.poll_interval
    )

    def on_events(events):
        print(f"[DAEMON] Triggered with {len(events)} events:")
        for e in events:
            print(f"  - {e.event_type}: {e.path}")

    daemon = DaemonWatcher(config, on_events)
    print(f"Watching: {args.watch}")
    daemon.start()