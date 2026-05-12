"""
acds-model-hub: Cross-model executor/reviewer routing
Routes tasks to appropriate AI models and manages review workflows.
"""
import logging
import time
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ModelCapability(Enum):
    """Model capability flags."""
    CODE_GENERATION = auto()
    CODE_REVIEW = auto()
    PLANNING = auto()
    ANALYSIS = auto()
    CREATIVE = auto()
    TEXT = auto()
    MULTIMODAL = auto()


@dataclass
class ModelConfig:
    """Configuration for a model."""
    name: str
    provider: str
    model_id: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    capabilities: List[ModelCapability] = field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 0.7
    cost_per_token: float = 0.0
    latency_ms: float = 0.0
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """Response from a model."""
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingRule:
    """Rule for routing tasks to models."""
    name: str
    matcher: Callable[[Dict[str, Any]], bool]
    target_models: List[str]
    priority: int = 0
    fallback_models: List[str] = field(default_factory=list)


class ModelProvider(ABC):
    """Abstract base for model providers."""
    
    @abstractmethod
    def complete(self, prompt: str, config: ModelConfig) -> ModelResponse:
        """Send completion request to model."""
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models."""
        pass


class OpenAIProvider(ModelProvider):
    """OpenAI API provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._get_api_key()
    
    def _get_api_key(self) -> str:
        import os
        return os.environ.get("OPENAI_API_KEY", "")
    
    def complete(self, prompt: str, config: ModelConfig) -> ModelResponse:
        import urllib.request
        import json
        import time as t
        
        start = t.time()
        try:
            data = json.dumps({
                "model": config.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": config.max_tokens,
                "temperature": config.temperature
            }).encode()
            
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                content = result["choices"][0]["message"]["content"]
                tokens = result.get("usage", {}).get("total_tokens", 0)
                
                return ModelResponse(
                    content=content,
                    model=config.name,
                    provider="openai",
                    tokens_used=tokens,
                    latency_ms=(t.time() - start) * 1000
                )
        except Exception as e:
            return ModelResponse(
                content="",
                model=config.name,
                provider="openai",
                success=False,
                error=str(e)
            )


class AnthropicProvider(ModelProvider):
    """Anthropic API provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._get_api_key()
    
    def _get_api_key(self) -> str:
        import os
        return os.environ.get("ANTHROPIC_API_KEY", "")
    
    def complete(self, prompt: str, config: ModelConfig) -> ModelResponse:
        import urllib.request
        import json
        import time as t
        
        start = t.time()
        try:
            data = json.dumps({
                "model": config.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": config.max_tokens
            }).encode()
            
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=data,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
            )
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                content = result["content"][0]["text"]
                tokens = result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)
                
                return ModelResponse(
                    content=content,
                    model=config.name,
                    provider="anthropic",
                    tokens_used=tokens,
                    latency_ms=(t.time() - start) * 1000
                )
        except Exception as e:
            return ModelResponse(
                content="",
                model=config.name,
                provider="anthropic",
                success=False,
                error=str(e)
            )


class MockProvider(ModelProvider):
    """Mock provider for testing."""
    
    def complete(self, prompt: str, config: ModelConfig) -> ModelResponse:
        import time as t
        start = t.time()
        time.sleep(0.1)  # Simulate latency
        
        return ModelResponse(
            content=f"[Mock response from {config.name}] Processed: {prompt[:50]}...",
            model=config.name,
            provider="mock",
            tokens_used=len(prompt) // 4,
            latency_ms=(t.time() - start) * 1000
        )
    
    def list_models(self) -> List[str]:
        return ["mock-gpt", "mock-claude"]


class ModelHub:
    """
    Central hub for model routing and management.
    Routes tasks to appropriate models based on capabilities and rules.
    """
    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._providers: Dict[str, ModelProvider] = {}
        self._routing_rules: List[RoutingRule] = []
        self._fallback_model: Optional[str] = None
        self._stats: Dict[str, Dict] = {}
    
    def register_model(self, config: ModelConfig):
        """Register a model with its provider."""
        self._models[config.name] = config
        
        if config.provider not in self._providers:
            self._providers[config.provider] = self._create_provider(config.provider, config.api_key)
        
        self._init_model_stats(config.name)
    
    def _create_provider(self, provider_name: str, api_key: Optional[str] = None) -> ModelProvider:
        """Create provider instance."""
        providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "mock": MockProvider,
        }
        provider_class = providers.get(provider_name.lower(), MockProvider)
        return provider_class(api_key)
    
    def _init_model_stats(self, model_name: str):
        """Initialize stats tracking for a model."""
        self._stats[model_name] = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
            "last_used": None
        }
    
    def add_routing_rule(self, rule: RoutingRule):
        """Add a routing rule."""
        self._routing_rules.append(rule)
        self._routing_rules.sort(key=lambda r: -r.priority)
    
    def set_fallback_model(self, model_name: str):
        """Set the fallback model."""
        self._fallback_model = model_name
    
    def route(
        self,
        task_type: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """Route a task to appropriate model."""
        context = context or {}
        context["task_type"] = task_type
        
        # Find matching models
        target_models = self._find_matching_models(context)
        
        # Try each model in order
        for model_name in target_models:
            response = self._execute_model(model_name, prompt)
            if response.success:
                self._update_stats(model_name, True, response)
                return response
        
        # Try fallback
        if self._fallback_model:
            response = self._execute_model(self._fallback_model, prompt)
            if response.success:
                self._update_stats(self._fallback_model, True, response)
                return response
        
        return ModelResponse(
            content="",
            model="none",
            provider="none",
            success=False,
            error="No available models"
        )
    
    def _find_matching_models(self, context: Dict[str, Any]) -> List[str]:
        """Find models matching the context."""
        matching_rules = [r for r in self._routing_rules if r.matcher(context)]
        
        if matching_rules:
            return matching_rules[0].target_models
        
        # Default: select by capability
        task_type = context.get("task_type", "")
        
        if "review" in task_type.lower():
            capable = [m for m, cfg in self._models.items() 
                      if ModelCapability.CODE_REVIEW in cfg.capabilities]
            if capable:
                return [sorted(capable, key=lambda x: self._models[x].priority, reverse=True)[0]]
        
        # Return all models sorted by priority
        return sorted(self._models.keys(), key=lambda x: self._models[x].priority, reverse=True)
    
    def _execute_model(self, model_name: str, prompt: str) -> ModelResponse:
        """Execute a model."""
        if model_name not in self._models:
            return ModelResponse(
                content="",
                model=model_name,
                provider="unknown",
                success=False,
                error=f"Model {model_name} not registered"
            )
        
        config = self._models[model_name]
        provider = self._providers.get(config.provider)
        
        if not provider:
            return ModelResponse(
                content="",
                model=model_name,
                provider=config.provider,
                success=False,
                error=f"Provider {config.provider} not available"
            )
        
        try:
            return provider.complete(prompt, config)
        except Exception as e:
            return ModelResponse(
                content="",
                model=model_name,
                provider=config.provider,
                success=False,
                error=str(e)
            )
    
    def _update_stats(self, model_name: str, success: bool, response: ModelResponse):
        """Update model statistics."""
        stats = self._stats.get(model_name, {})
        stats["requests"] = stats.get("requests", 0) + 1
        if success:
            stats["successes"] = stats.get("successes", 0) + 1
        else:
            stats["failures"] = stats.get("failures", 0) + 1
        stats["total_tokens"] = stats.get("total_tokens", 0) + response.tokens_used
        stats["total_latency"] = stats.get("total_latency", 0.0) + response.latency_ms
        stats["last_used"] = time.time()
    
    def get_stats(self, model_name: Optional[str] = None) -> Dict:
        """Get model statistics."""
        if model_name:
            return self._stats.get(model_name, {})
        return dict(self._stats)
    
    def list_models(self, capability: Optional[ModelCapability] = None) -> List[ModelConfig]:
        """List all registered models, optionally filtered by capability."""
        models = list(self._models.values())
        if capability:
            models = [m for m in models if capability in m.capabilities]
        return sorted(models, key=lambda x: x.priority, reverse=True)


class ExecutorReviewer:
    """
    Combined executor/reviewer using ModelHub.
    Handles both generation and review phases.
    """
    def __init__(self, hub: ModelHub):
        self.hub = hub
    
    def execute(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """Execute a task using the hub."""
        return self.hub.route("execute", task, context)
    
    def review(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """Review code using the hub."""
        prompt = f"Review the following code:\n\n{code}"
        return self.hub.route("review", prompt, context)
    
    def plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """Create a plan using the hub."""
        prompt = f"Create a plan for: {goal}"
        return self.hub.route("plan", prompt, context)


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ACDS Model Hub - Cross-model routing")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    parser.add_argument("--test", help="Test routing with prompt")
    parser.add_argument("--model", help="Specific model to use")

    args = parser.parse_args()

    hub = ModelHub()
    
    # Register default mock models
    hub.register_model(ModelConfig(
        name="mock-gpt",
        provider="mock",
        model_id="gpt-4",
        capabilities=[ModelCapability.CODE_GENERATION, ModelCapability.PLANNING]
    ))
    hub.register_model(ModelConfig(
        name="mock-claude",
        provider="mock", 
        model_id="claude-3",
        capabilities=[ModelCapability.CODE_REVIEW, ModelCapability.ANALYSIS]
    ))

    if args.list_models:
        models = hub.list_models()
        for m in models:
            caps = [c.name for c in m.capabilities]
            print(f"{m.name} ({m.provider}): {', '.join(caps)}")
    
    elif args.test:
        response = hub.route("test", args.test)
        print(f"Response from {response.model}:")
        print(response.content)