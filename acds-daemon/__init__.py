"""acds-daemon: Background watcher + auto-trigger loop."""

from .daemon import (
    WatchEvent,
    DaemonConfig,
    DaemonWatcher,
    DaemonManager,
    FileHasher,
    EventQueue,
)

__version__ = "0.1.0"
__all__ = [
    "WatchEvent",
    "DaemonConfig", 
    "DaemonWatcher",
    "DaemonManager",
    "FileHasher",
    "EventQueue",
]