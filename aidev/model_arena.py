"""Model arena for AI DevTools - compare and select models across providers.

Provides a simple interface for comparing models from different providers
based on engineering metrics tracked in traces: latency, tokens, cost, errors.

Supports:
- Model registration from different providers (OpenAI, Ollama, local)
- Comparison based on traced metrics (latency, tokens, stop reason)
- Simple scoring for model selection
- Provider-agnostic (no hard-coding around single provider)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from aidev.storage import TraceSQLite
from aidev.trace import SpanStatus


class Provider(Enum):
    """Supported model providers."""

    OPENAI = "openai"
    OLLAMA = "ollama"
    LOCAL = "local"
    ANTHROPIC = "anthropic"


@dataclass
class ModelInfo:
    """Metadata about a model available in the arena."""

    name: str
    provider: Provider
    family: str  # e.g., "gpt-4o", "claude-3", "llama-3"
    context_window: int
    supports_tools: bool = True
    supports_vision: bool = False
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None


@dataclass
class ArenaScore:
    """Score for a model in the arena, based on traced metrics."""

    model_name: str
    provider: Provider
    avg_latency: float | None = None  # in seconds
    avg_ttft: float | None = None  # Time To First Token
    avg_tokens_per_sec: float | None = None
    total_tokens: int | None = None
    error_rate: float | None = None  # errors / total runs
    success_rate: float | None = None  # runs without error
    cost_estimate: float | None = None
    comparison_data: dict[str, any] = field(default_factory=dict)


class ModelArena:
    """Manages model comparison and selection across providers.

    Reads traced metrics from SQLite and provides scoring/selection
    recommendations based on engineering criteria.
    """

    def __init__(self, storage: TraceSQLite):
        self.storage = storage
        self._models: dict[str, ModelInfo] = {}
        self._scores: dict[str, ArenaScore] = {}

    def register_model(self, model_info: ModelInfo) -> None:
        """Register a model available in the arena."""
        self._models[model_info.name] = model_info

    def auto_register(self) -> ModelArena:
        """Register every model name found in the trace database.

        Model metadata not present in traces (context window, costs, etc.)
        is left at conservative defaults; provider is inferred from the name.
        """
        for model_name in self.storage.get_models():
            if model_name not in self._models:
                self._models[model_name] = ModelInfo(
                    name=model_name,
                    provider=self._get_provider(model_name),
                    family=model_name,
                    context_window=0,
                )
        return self

    def compute_score(self, model_name: str) -> ArenaScore:
        """Compute an ArenaScore for a model from its traced spans.

        Averages real measured latency/TTFT/throughput over the spans recorded
        for this model and derives error/success rates from span status. Models
        with no traces get a score whose fields are all ``None``.
        """
        spans = self.storage.get_spans_by_model(model_name)
        provider = self._get_provider(model_name)
        if not spans:
            return ArenaScore(model_name=model_name, provider=provider)

        latencies = [s.end_time - s.start_time for s in spans if s.end_time > s.start_time]
        ttfts = [s.ttft for s in spans if s.ttft is not None]
        throughputs = [s.tokens_per_sec for s in spans if s.tokens_per_sec is not None]
        tokens = sum(s.total_tokens or 0 for s in spans)
        errors = sum(1 for s in spans if s.status == SpanStatus.ERROR)

        return ArenaScore(
            model_name=model_name,
            provider=provider,
            avg_latency=sum(latencies) / len(latencies) if latencies else None,
            avg_ttft=sum(ttfts) / len(ttfts) if ttfts else None,
            avg_tokens_per_sec=sum(throughputs) / len(throughputs) if throughputs else None,
            total_tokens=tokens if tokens else None,
            error_rate=errors / len(spans) if spans else None,
            success_rate=(len(spans) - errors) / len(spans) if spans else None,
        )

    def compare_models(self, model_a: str, model_b: str) -> dict[str, any] | None:
        """Compare two models based on their traced spans.

        Returns a dict with engineering metrics difference, or None if
        insufficient data.
        """
        score_a = self.compute_score(model_a)
        score_b = self.compute_score(model_b)

        if score_a.avg_latency is None and score_a.total_tokens is None:
            return None  # No data for model A

        if score_b.avg_latency is None and score_b.total_tokens is None:
            return None  # No data for model B

        comparison: dict[str, any] = {
            "model_a": model_a,
            "model_b": model_b,
        }

        # Compare latency
        if score_a.avg_latency is not None and score_b.avg_latency is not None:
            diff = score_b.avg_latency - score_a.avg_latency
            comparison["latency_diff_s"] = diff
            comparison["latency_faster"] = (
                "model_a" if diff < 0 else "model_b" if diff > 0 else "tie"
            )

        # Compare TTFT
        if score_a.avg_ttft is not None and score_b.avg_ttft is not None:
            diff = score_b.avg_ttft - score_a.avg_ttft
            comparison["ttft_diff_s"] = diff
            comparison["ttft_faster"] = "model_a" if diff < 0 else "model_b" if diff > 0 else "tie"

        # Compare tokens/sec
        if score_a.avg_tokens_per_sec is not None and score_b.avg_tokens_per_sec is not None:
            ratio = score_b.avg_tokens_per_sec / score_a.avg_tokens_per_sec
            comparison["tokens_per_sec_ratio"] = ratio
            comparison["tokens_per_sec_faster"] = (
                "model_a" if ratio > 1 else "model_b" if ratio < 1 else "tie"
            )

        # Compare total tokens
        if score_a.total_tokens is not None and score_b.total_tokens is not None:
            diff = score_b.total_tokens - score_a.total_tokens
            comparison["total_tokens_diff"] = diff
            comparison["total_tokens_fewer"] = (
                "model_a" if diff < 0 else "model_b" if diff > 0 else "tie"
            )

        # Compare error rate (if available via metadata errors)
        # Note: errors are per-span, not aggregated yet; placeholder
        comparison["error_rate_note"] = "Error rate per-span; aggregate not yet implemented"

        return comparison

    def _get_provider(self, model_name: str) -> Provider:
        """Guess provider from model name."""
        # Simple heuristics - expand as more models are registered
        lower = model_name.lower()
        if any(k in lower for k in ["gpt-4", "gpt-3.5", "dall-e", "whisper"]):
            return Provider.OPENAI
        if any(k in lower for k in ["llama", "mistral", "phi", "gemma"]):
            return Provider.LOCAL
        if any(k in lower for k in ["claude", "sonnet", "opus"]):
            return Provider.ANTHROPIC
        if any(k in lower for k in ["llama3", "phi3", "gemma2"]):
            return Provider.LOCAL
        return Provider.LOCAL  # default


# Provide a convenience function for quick arena setup


def create_arena(storage: TraceSQLite) -> ModelArena:
    """Create an arena directly from the trace database.

    All models present in the traces are auto-registered, so routing and
    comparison work immediately on real traced data.
    """
    return ModelArena(storage).auto_register()
