# acds-pr-bot

GitHub/GitLab PR integration for pr mode.

## Overview

The `acds-pr-bot` module provides automated pull request operations for both GitHub and GitLab platforms.

## Features

- **GitHub PR Operations**: Create, merge, close PRs via `gh` CLI
- **GitLab MR Operations**: Create, merge merge requests via API
- **PRMode Controller**: High-level workflow management
- **Factory Pattern**: Easy instantiation from URLs or configs

## Installation

```bash
pip install acds-pr-bot
```

## Usage

### GitHub

```python
from acds_pr_bot import GitHubPRBot, PRMode

bot = GitHubPRBot("owner", "repo")
pr_mode = PRMode(bot)

pr = pr_mode.create_pr_for_branch(
    branch="feature/my-branch",
    title="My Feature",
    description="Implementation of..."
)

if pr_mode.validate_pr()["valid"]:
    pr_mode.merge_if_ready()
```

### GitLab

```python
from acds_pr_bot import GitLabMRBot

bot = GitLabMRBot(project_id="12345", gl_token="your-token")
mr = bot.create_mr(
    source_branch="feature/my-branch",
    title="My Feature",
    description="Implementation...",
    target="main"
)
```

### CLI

```bash
acds-pr-bot create --repo owner/repo --branch feature-x --title "My PR"
acds-pr-bot merge --repo owner/repo
```

## Classes

| Class | Description |
|-------|-------------|
| `GitHubPRBot` | GitHub PR operations via `gh` CLI |
| `GitLabMRBot` | GitLab MR operations via REST API |
| `PRMode` | High-level PR workflow controller |
| `PRBotFactory` | Factory for creating platform-specific bots |

## Configuration

`PRConfig`:
- `platform`: GITHUB or GITLAB
- `base_branch`: Target branch (default: main)
- `draft`: Create as draft PR
- `labels`: List of labels to apply
- `reviewers`: List of reviewers to request
- `auto_merge`: Auto-merge when ready

## License

MIT