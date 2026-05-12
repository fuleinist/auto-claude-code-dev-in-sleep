# acds-report

HTML iteration diary generator for auto-claude-code-dev-in-sleep.

## Overview

The `acds-report` module generates beautiful HTML reports documenting ACDS loop iterations with metrics, timelines, and logs.

## Features

- **Multiple Themes**: Dark, Light, GitHub-style themes
- **Timeline Views**: Visual timeline of all iterations
- **Metrics Dashboard**: Success rates, durations, file changes
- **Log Aggregation**: Collated logs from all iterations
- **Diary Mode**: Create iteration diaries with timeline views
- **CLI Tool**: Generate reports from command line or JSON files

## Installation

```bash
pip install acds-report
```

## Usage

### Python API

```python
from acds_report import ReportGenerator, ReportConfig, IterationData

config = ReportConfig(
    title="My ACDS Report",
    theme="dark"
)

gen = ReportGenerator(config)

iterations = [
    IterationData(
        iteration=1,
        task="Initialize project",
        status="success",
        start_time=time.time() - 3600,
        duration_seconds=100,
        changes=[{"file": "setup.py"}],
        logs=[LogEntry(time.time(), "info", "Started")]
    )
]

gen.generate(iterations, "report.html")
```

### CLI

```bash
# From iteration data
python -m acds_report --input iterations.json --output report.html

# With theme
python -m acds_report --input data.json --theme light --title "Daily Report"
```

### JSON Input Format

```json
{
  "iterations": [
    {
      "iteration": 1,
      "task": "Implement feature X",
      "status": "success",
      "start_time": 1700000000,
      "duration_seconds": 120,
      "changes": [{"file": "src/x.py", "type": "create"}],
      "logs": [{"timestamp": 1700000000, "level": "info", "message": "..."}]
    }
  ]
}
```

## Report Themes

| Theme | Description |
|-------|-------------|
| `dark` | Dark mode with cyan accents (default) |
| `light` | Light mode with blue accents |
| `github` | GitHub-inspired styling |

## License

MIT