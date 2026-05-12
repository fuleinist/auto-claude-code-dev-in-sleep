# acds-model-hub

Cross-model executor/reviewer routing for auto-claude-code-dev-in-sleep.

## Overview

The `acds-model-hub` module provides intelligent routing of tasks to appropriate AI models based on capabilities, rules, and priority.

## Features

- **Multi-Provider Support**: OpenAI, Anthropic, and custom providers
- **Capability-Based Routing**: Route by model capabilities (CODE_GENERATION, CODE_REVIEW, etc.)
- **Rule-Based Routing**: Define custom routing rules with matchers
- **Fallback Handling**: Automatic fallback to secondary models
- **Statistics Tracking**: Monitor model usage, latency, success rates
- **ExecutorReviewer**: Combined generation and review workflow

## Installation

```bash
pip install acds-model-hub
```

## Usage

### Basic Setup

```python
from acds_model_hub import ModelHub, ModelConfig, ModelCapability

hub = ModelHub()

# Register models
hub.register_model(ModelConfig(
    name="gpt-4",
    provider="openai",
    model_id="gpt-4",
    capabilities=[ModelCapability.CODE_GENERATION, ModelCapability.PLANNING],
    priority=10
))

hub.register_model(ModelConfig(
    name="claude-3",
    provider="anthropic", 
    model_id="claude-3-sonnet",
    capabilities=[ModelCapability.CODE_REVIEW, ModelCapability.ANALYSIS],
    priority=8
))

# Route tasks
response = hub.route("generate", "Write a function to sort a list")
```

### Executor/Reviewer

```python
from acds_model_hub import ExecutorReviewer, ModelHub

hub = ModelHub()
# ... register models ...

er = ExecutorReviewer(hub)

# Execute task
result = er.execute("Implement binary search")

# Review result
review = er.review(result.content)
```

### Custom Routing Rules

```python
from acds_model_hub import RoutingRule

def code_match(context):
    return context.get("task_type") == "code"

rule = RoutingRule(
    name="code-tasks",
    matcher=code_match,
    target_models=["gpt-4", "claude-3"],
    priority=10
)

hub.add_routing_rule(rule)
```

## Model Capabilities

| Capability | Description |
|------------|-------------|
| `CODE_GENERATION` | Generate code from specifications |
| `CODE_REVIEW` | Review and critique code |
| `PLANNING` | Create execution plans |
| `ANALYSIS` | Analyze and explain code |
| `CREATIVE` | Creative tasks |
| `TEXT` | Text generation |
| `MULTIMODAL` | Vision + text |

## CLI

```bash
python -m acds_model_hub --list-models
python -m acds_model_hub --test "Write hello world"
```

## License

MIT