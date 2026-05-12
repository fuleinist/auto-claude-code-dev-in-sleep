# acds-daemon

Background watcher + auto-trigger loop for auto-claude-code-dev-in-sleep.

## Overview

The `acds-daemon` module provides a background process that monitors repository state and triggers ACDS loop execution when file changes or Git events are detected.

## Features

- **File System Monitoring**: Watches specified paths for modifications, creations, and deletions
- **Git Event Detection**: Detects Git-related events (commits, branches, pushes)
- **Debouncing**: Prevents rapid successive triggers with configurable debounce window
- **Event Queue**: Thread-safe queue with configurable max size
- **Pause/Resume**: Dynamically pause and resume monitoring
- **Multiple Watchers**: Manage multiple watchers with the DaemonManager

## Installation

```bash
pip install acds-daemon
```

## Usage

### Basic Daemon

```python
from acds_daemon.daemon import DaemonWatcher, DaemonConfig

config = DaemonConfig(
    watch_paths=["src/", "tests/"],
    poll_interval=5.0,
    debounce_seconds=2.0
)

def on_trigger(events):
    print(f"Detected {len(events)} changes")

daemon = DaemonWatcher(config, on_trigger)
daemon.start()
```

### CLI

```bash
python -m acds_daemon --watch src tests --poll-interval 3
```

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `watch_paths` | list[str] | `["."]` | Paths to monitor |
| `poll_interval` | float | `5.0` | Seconds between scans |
| `debounce_seconds` | float | `2.0` | Minimum time between triggers |
| `trigger_on` | list[str] | `["modify", "create", "delete"]` | Event types to trigger on |
| `ignore_patterns` | list[str] | (see code) | Glob patterns to ignore |
| `max_queue_size` | int | `1000` | Max events in queue |

## Architecture

```
DaemonWatcher
├── FileHasher        # Lightweight file change detection
├── EventQueue        # Thread-safe event queue
├── DaemonConfig      # Configuration container
└── DaemonManager     # Multi-watcher coordinator
```

## Events

Events are `WatchEvent` objects with:
- `event_type`: "modify" | "create" | "delete"
- `path`: Absolute file path
- `metadata`: Optional dict with extra data
- `timestamp`: Unix timestamp

## License

MIT