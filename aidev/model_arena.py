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

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


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
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None


@dataclass
class ArenaScore:
    """Score for a model in the arena, based on traced metrics."""
    model_name: str
    provider: Provider
    avg_latency: Optional[float] = None  # in seconds
    avg_ttft: Optional[float] = None     # Time To First Token
    avg_tokens_per_sec: Optional[float] = None
    total_tokens: Optional[int] = None
    error_rate: Optional[float] = None   # errors / total runs
    success_rate: Optional[float] = None # runs without error
    cost_estimate: Optional[float] = None
    comparison_data: Dict[str, any] = field(default_factory=dict)


class ModelArena:
    """Manages model comparison and selection across providers.

    Reads traced metrics from SQLite and provides scoring/selection
    recommendations based on engineering criteria.
    """

    def __init__(self, storage: TraceSQLite):
        self.storage = storage
        self._models: Dict[str, ModelInfo] = {}
        self._scores: Dict[str, ArenaScore] = {}

    def register_model(self, model_info: ModelInfo) -> None:
        """Register a model available in the arena."""
        self._models[model_info.name] = model_info

    def compute_score(self, model_name: str) -> ArenaScore:
        """Compute an ArenaScore for a model based on traced spans.

        Uses traced metrics: latency, TTFT, tokens/sec, error rate, success rate.
        If no traces exist for the model, returns a score with None values.
        """
        score = ArenaScore(model_name=model_name, provider=self._get_provider(model_name))

        # Search for spans with this model
        all_spans: list = []
        # We need to search through all spans; storage only provides root spans
        # For now, compute from available data
        # TODO: Add a method to storage to get spans by model filter

        # Since we can't easily filter spans by model from storage alone,
        # we'll compute based on what's available and mark as limited
        score.comparison_data["note"] = (
            "Limited: model-based span filtering not yet in storage API; "
            "using available metadata fields"
        )

        return score

    def compare_models(self, model_a: str, model_b: str) -> Optional[Dict[str, any]]:
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

        comparison: Dict[str, any] = {
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
            comparison["ttft_faster"] = (
                "model_a" if diff < 0 else "model_b" if diff > 0 else "tie"
            )

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
    """Create a ModelArena instance registered with traced metrics.

    In a full implementation, this would auto-register models from
    traced data. For now, returns a bare arena for manual registration.
    """
    arena = ModelArena(storage)
    return arena