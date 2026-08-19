"""Model routing for AI DevTools - automatic model selection based on criteria.

Provides a routing engine that selects the best model for a given task
based on engineering criteria derived from traced metrics: latency, cost,
token usage, error rate, and success rate.

Routes requests to the optimal model from the registered model arena.
All decisions are based on traced metrics, never on assumptions or predictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from aidev.model_arena import ModelArena, ModelInfo, Provider, ArenaScore


class RoutingCriteria(Enum):
    """Criteria for model routing."""
    LATENCY = "latency"        # fastest response
    THROUGHPUT = "throughput"  # most tokens/second
    COST = "cost"              # cheapest (input + output cost)
    ERROR_RATE = "error_rate"  # lowest error rate
    SUCCESS_RATE = "success_rate"  # highest success rate
    BALANCED = "balanced"      # weighted mix of all criteria


@dataclass
class RoutingResult:
    """Result of model routing evaluation."""
    selected_model: str
    rejected_models: List[str]
    reasoning: str
    metrics_comparison: Dict[str, any]
    criteria_used: RoutingCriteria


class ModelRouter:
    """Routes requests to the optimal model based on engineering criteria.

    Uses the ModelArena to compare registered models and select the best one
    based on the specified routing criteria. All decisions are based on
    traced metrics, never on assumptions or predictions.
    """

    def __init__(self, arena: ModelArena):
        self.arena = arena

    def route(self, criteria: RoutingCriteria = RoutingCriteria.BALANCED,
              rejected: Optional[List[str]] = None) -> RoutingResult:
        """Route to the best model based on the given criteria.

        Args:
            criteria: The routing criteria to optimize for
            rejected: Optional list of model names to exclude

        Returns:
            RoutingResult with the selected model and reasoning
        """
        if rejected is None:
            rejected = []

        # Get all registered models, excluding rejected ones
        candidates: List[Tuple[str, ModelInfo, ArenaScore]] = []

        for model_name, model_info in self.arena._models.items():
            if model_name in rejected:
                continue

            score = self.arena.compute_score(model_name)
            candidates.append((model_name, model_info, score))

        if not candidates:
            raise ValueError("No models available for routing (all rejected or none registered)")

        if len(candidates) == 1:
            model_name, model_info, score = candidates[0]
            return RoutingResult(
                selected_model=model_name,
                rejected_models=rejected,
                reasoning="Only one model available: " + model_name + " (" + model_info.provider.value + ")",
                metrics_comparison={},
                criteria_used=criteria,
            )

        # Select based on criteria
        selected_name, reasoning, metrics = self._select_by_criteria(
            candidates, criteria
        )

        # Build rejected list (all except selected)
        rejected_final = [name for name, _, _ in candidates if name != selected_name]

        return RoutingResult(
            selected_model=selected_name,
            rejected_models=rejected_final,
            reasoning=reasoning,
            metrics_comparison=metrics,
            criteria_used=criteria,
        )

    def _select_by_criteria(
        self, candidates: List[Tuple[str, ModelInfo, ArenaScore]],
        criteria: RoutingCriteria,
    ) -> Tuple[str, str, Dict[str, any]]:
        """Select the best model based on the given routing criteria.

        Returns: (selected_model_name, reasoning_string, metrics_comparison_dict)
        """
        # Build per-candidate metric summaries, handling None values
        candidate_metrics: Dict[str, Dict[str, any]] = {}
        for model_name, model_info, score in candidates:
            candidate_metrics[model_name] = {
                "provider": model_info.provider.value,
                "family": model_info.family,
                "context_window": model_info.context_window,
                "avg_latency_s": score.avg_latency,  # may be None
                "avg_ttft_s": score.avg_ttft,  # may be None
                "tokens_per_sec": score.avg_tokens_per_sec,  # may be None
                "total_tokens": score.total_tokens,  # may be None
                "error_rate": score.error_rate,  # may be None
                "success_rate": score.success_rate,  # may be None
                "cost_estimate": score.cost_estimate,  # may be None
            }

        if criteria == RoutingCriteria.LATENCY:
            # Select model with lowest avg_latency (fastest)
            def latency_key(item):
                _name, _info, score = item
                if score.avg_latency is not None:
                    return score.avg_latency
                return float("inf")  # None latency is "worst"

            selected_name = min(candidates, key=latency_key)[0]
            selected_score = next(s for n, _, s in candidates if n == selected_name)
            # Build reasoning - handle None
            if selected_score.avg_latency is not None:
                slower_models = [
                    n for n, _, s in candidates
                    if n != selected_name and s.avg_latency is not None and s.avg_latency < selected_score.avg_latency
                ]
                if slower_models:
                    reasoning = (
                        "Selected " + selected_name + " as fastest (avg "
                        + format(selected_score.avg_latency, ".2f") + "s); "
                        + "slower: " + ", ".join(slower_models)
                    )
                else:
                    reasoning = "Selected " + selected_name + " as fastest; all others have no latency data or are slower"
            else:
                reasoning = "Selected " + selected_name + " as fastest; all others have no latency data"
            candidate_metrics_summary = {}
            for name, m in candidate_metrics.items():
                candidate_metrics_summary[name] = {
                    "latency_s": m["avg_latency_s"],
                }
            metrics = {"candidate_metrics": candidate_metrics_summary, "selection_type": "latency"}

        elif criteria == RoutingCriteria.THROUGHPUT:
            # Select model with highest avg_tokens_per_sec
            def throughput_key(item):
                _name, _info, score = item
                if score.avg_tokens_per_sec is not None:
                    return score.avg_tokens_per_sec
                return 0.0  # None throughput is "worst"

            selected_name = max(candidates, key=throughput_key)[0]
            selected_score = next(s for n, _, s in candidates if n == selected_name)
            # Build reasoning - handle None
            if selected_score.avg_tokens_per_sec is not None:
                faster_models = [
                    n for n, _, s in candidates
                    if n != selected_name and s.avg_tokens_per_sec is not None and s.avg_tokens_per_sec > selected_score.avg_tokens_per_sec
                ]
                if faster_models:
                    reasoning = "Selected " + selected_name + " as highest throughput (" + format(selected_score.avg_tokens_per_sec, ".1f") + " tok/s); slower: " + ", ".join(faster_models)
                else:
                    reasoning = "Selected " + selected_name + " as highest throughput (" + format(selected_score.avg_tokens_per_sec, ".1f") + " tok/s); others have no throughput data"
            else:
                reasoning = "Selected " + selected_name + " as highest throughput; others have no throughput data"
            candidate_metrics_summary = {}
            for name, m in candidate_metrics.items():
                candidate_metrics_summary[name] = {
                    "tokens_per_sec": m["tokens_per_sec"],
                }
            metrics = {"candidate_metrics": candidate_metrics_summary, "selection_type": "throughput"}

        elif criteria == RoutingCriteria.COST:
            # Select model with lowest cost estimate
            def cost_key(item):
                _name, _info, score = item
                if score.cost_estimate is not None:
                    return score.cost_estimate
                return float("inf")  # No cost data is "worst"

            selected_name = min(candidates, key=cost_key)[0]
            selected_score = next(s for n, _, s in candidates if n == selected_name)
            # Build reasoning - handle None
            if selected_score.cost_estimate is not None:
                more_expensive = [
                    n for n, _, s in candidates
                    if n != selected_name and s.cost_estimate is not None and s.cost_estimate < selected_score.cost_estimate
                ]
                if more_expensive:
                    reasoning = "Selected " + selected_name + " as cheapest (cost " + format(selected_score.cost_estimate, ".4f") + "/1k tokens); more expensive: " + ", ".join(more_expensive)
                else:
                    reasoning = "Selected " + selected_name + " as cheapest (cost " + format(selected_score.cost_estimate, ".4f") + "/1k tokens); others have no cost data"
            else:
                reasoning = "Selected " + selected_name + " as cheapest; others have no cost data"
            candidate_metrics_summary = {}
            for name, m in candidate_metrics.items():
                candidate_metrics_summary[name] = {
                    "cost_estimate": m["cost_estimate"],
                }
            metrics = {"candidate_metrics": candidate_metrics_summary, "selection_type": "cost"}

        elif criteria == RoutingCriteria.ERROR_RATE:
            # Select model with lowest error_rate (highest reliability)
            def error_key(item):
                _name, _info, score = item
                if score.error_rate is not None:
                    return score.error_rate
                return 1.0  # No error rate data is "worst"

            selected_name = min(candidates, key=error_key)[0]
            selected_score = next(s for n, _, s in candidates if n == selected_name)
            # Build reasoning - handle None
            if selected_score.error_rate is not None:
                more_error_prone = [
                    n for n, _, s in candidates
                    if n != selected_name and s.error_rate is not None and s.error_rate > selected_score.error_rate
                ]
                if more_error_prone:
                    reasoning = "Selected " + selected_name + " as most reliable (error_rate=" + format(selected_score.error_rate, ".2%") + "); higher error rate: " + ", ".join(more_error_prone)
                else:
                    reasoning = "Selected " + selected_name + " as most reliable (error_rate=" + format(selected_score.error_rate, ".2%") + "; others have no error rate data"
            else:
                reasoning = "Selected " + selected_name + " as most reliable; others have no error rate data"
            candidate_metrics_summary = {}
            for name, m in candidate_metrics.items():
                candidate_metrics_summary[name] = {
                    "error_rate": m["error_rate"],
                }
            metrics = {"candidate_metrics": candidate_metrics_summary, "selection_type": "error_rate"}

        elif criteria == RoutingCriteria.SUCCESS_RATE:
            # Select model with highest success_rate
            def success_key(item):
                _name, _info, score = item
                if score.success_rate is not None:
                    return score.success_rate
                return 0.0  # No success rate data is "worst"

            selected_name = max(candidates, key=success_key)[0]
            selected_score = next(s for n, _, s in candidates if n == selected_name)
            # Build reasoning - handle None
            if selected_score.success_rate is not None:
                less_success = [
                    n for n, _, s in candidates
                    if n != selected_name and s.success_rate is not None and s.success_rate < selected_score.success_rate
                ]
                if less_success:
                    reasoning = "Selected " + selected_name + " as highest success rate (" + format(selected_score.success_rate, ".1%") + "); lower success: " + ", ".join(less_success)
                else:
                    reasoning = "Selected " + selected_name + " as highest success rate (" + format(selected_score.success_rate, ".1%") + "; others have no success rate data"
            else:
                reasoning = "Selected " + selected_name + " as highest success rate; others have no success rate data"
            candidate_metrics_summary = {}
            for name, m in candidate_metrics.items():
                candidate_metrics_summary[name] = {
                    "success_rate": m["success_rate"],
                }
            metrics = {"candidate_metrics": candidate_metrics_summary, "selection_type": "success_rate"}

        elif criteria == RoutingCriteria.BALANCED:
            # Balanced: prefer models that are good across multiple metrics.
            # Use a simple scoring: sum of normalized metrics.
            # For simplicity, if we have latency and throughput data, pick the
            # model that is fastest AND has good throughput. Otherwise fall back
            # to the model with the most available metric data.
            def balanced_key(item):
                _name, _info, score = item
                score_val = 0.0
                count = 0
                if score.avg_latency is not None and score.avg_latency > 0:
                    # lower is better, invert: use 1/latency
                    score_val += 1.0 / score.avg_latency
                    count += 1
                if score.avg_tokens_per_sec is not None and score.avg_tokens_per_sec > 0:
                    score_val += score.avg_tokens_per_sec / 100.0  # normalize
                    count += 1
                if score.success_rate is not None and score.success_rate > 0:
                    score_val += score.success_rate * 10.0  # normalize
                    count += 1
                if count == 0:
                    return 0.0
                return score_val / count

            selected_name = min(candidates, key=balanced_key)[0]
            selected_info, selected_score = next(
                (info, score) for name, info, score in candidates if name == selected_name
            )
            # Find models that dominate in at least one metric
            dominant_notes = []
            if any(s.avg_latency is not None for _, _, s in candidates):
                dominant_notes.append("latency data available")
            if any(s.avg_tokens_per_sec is not None for _, _, s in candidates):
                dominant_notes.append("throughput data available")
            if any(s.success_rate is not None for _, _, s in candidates):
                dominant_notes.append("success rate data available")

            # Build reasoning
            reasoning_parts = ["Selected " + selected_name + " (" + selected_info.family + " via balanced criteria"]
            if dominant_notes:
                reasoning_parts.append("data: " + ", ".join(dominant_notes))
            else:
                reasoning_parts.append("limited data available")
            reasoning = " ".join(reasoning_parts)
            metrics = {"selection_type": "balanced", "dominant_notes": dominant_notes}
        else:
            # Fallback: select the first candidate
            selected_name = candidates[0][0]
            selected_info, selected_score = candidates[0]
            reasoning = "Selected " + selected_name + " as default (only criterion: " + criteria.value + ")"
            metrics = {"selection_type": criteria.value, "note": "Using " + criteria.value + " criterion with limited data"}

        return selected_name, reasoning, metrics

    def route_for_task(self, task_description: str,
                       criteria: RoutingCriteria = RoutingCriteria.BALANCED,
                       excluded_models: Optional[List[str]] = None) -> RoutingResult:
        """Route a model for a given task description.

        In a full implementation, the task description would be analyzed
        to infer the best criteria. For now, uses the specified criteria.

        Args:
            task_description: Description of the task (e.g., "code generation",
                "text summarization", "image classification")
            criteria: Routing criteria to optimize for
            excluded_models: Models to exclude from consideration

        Returns:
            RoutingResult with the selected model and reasoning
        """
        # Task-based heuristic for criteria selection
        task_lower = task_description.lower()

        # Map task types to preferred criteria
        task_criteria_map: Dict[str, RoutingCriteria] = {
            "code": RoutingCriteria.LATENCY,
            "summarization": RoutingCriteria.THROUGHPUT,
            "analysis": RoutingCriteria.BALANCED,
            "classification": RoutingCriteria.SUCCESS_RATE,
            "translation": RoutingCriteria.BALANCED,
            "creative": RoutingCriteria.BALANCED,
            "agent": RoutingCriteria.BALANCED,
        }

        # Use task-inferred criteria or default
        selected_criteria = task_criteria_map.get(task_lower, criteria)

        return self.route(criteria=selected_criteria, rejected=excluded_models)


# Provide a convenience function
def create_router(arena: ModelArena) -> ModelRouter:
    """Create a ModelRouter instance for the given ModelArena."""
    return ModelRouter(arena)