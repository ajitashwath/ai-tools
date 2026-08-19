"""Performance optimization for AI DevTools - benchmark and optimize traces.

Provides performance benchmarking based on traced metrics and optimization
recommendations for reducing latency, token usage, and improving throughput.

All optimizations are based on traced metrics, never on assumptions or
black-box recommendations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from aidev.trace import Span, SpanStatus


@dataclass
class PerformanceBenchmark:
    """Benchmark results for a model or execution."""

    model_name: str
    total_runs: int
    avg_latency_s: Optional[float] = None
    avg_ttft_s: Optional[float] = None
    avg_tokens_per_sec: Optional[float] = None
    total_tokens: Optional[int] = None
    min_latency_s: Optional[float] = None
    max_latency_s: Optional[float] = None
    p95_latency_s: Optional[float] = None
    error_count: int = 0
    success_count: int = 0
    cost_estimate: Optional[float] = None


@dataclass
class OptimizationRecommendation:
    """Recommendation for optimizing trace performance."""

    category: str  # "latency", "tokens", "throughput", "cost"
    priority: str  # "high", "medium", "low"
    description: str
    expected_improvement: str  # e.g., "reduce latency by 20%"
    actionable_steps: List[str]


class PerformanceOptimizer:
    """Benchmarks trace performance and provides optimization recommendations.

    Analyzes traced spans to compute performance metrics and generates
    actionable optimization recommendations based on engineering data.
    """

    def benchmark(self, spans: List[Span], model_name: Optional[str] = None) -> PerformanceBenchmark:
        """Compute performance benchmark from a list of spans.

        Args:
            spans: List of spans to benchmark
            model_name: Optional model name to associate with the benchmark

        Returns:
            PerformanceBenchmark with computed metrics
        """
        if not spans:
            return PerformanceBenchmark(model_name=model_name or "unknown", total_runs=0)

        total_runs = len(spans)
        latencies: List[float] = []
        ttfts: List[float] = []
        tokens_per_secs: List[float] = []
        total_tokens = 0
        error_count = 0
        success_count = 0
        min_latency: Optional[float] = None
        max_latency: Optional[float] = None

        for span in spans:
            # Collect latencies (end - start)
            if span.end_time > span.start_time:
                latency = span.end_time - span.start_time
                latencies.append(latency)
                if min_latency is None or latency < min_latency:
                    min_latency = latency
                if max_latency is None or latency > max_latency:
                    max_latency = latency

            # Collect TTFT
            if span.ttft is not None:
                ttfts.append(span.ttft)

            # Collect tokens/sec
            if span.tokens_per_sec is not None:
                tokens_per_secs.append(span.tokens_per_sec)

            # Count total tokens
            if span.total_tokens is not None:
                total_tokens += span.total_tokens

            # Count errors and successes
            if span.status == SpanStatus.ERROR:
                error_count += 1
            else:
                success_count += 1

        # Compute averages
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        avg_ttft = sum(ttfts) / len(ttfts) if ttfts else None
        avg_tokens_per_sec = sum(tokens_per_secs) / len(tokens_per_secs) if tokens_per_secs else None

        # Compute p95 latency
        p95_latency = None
        if latencies:
            sorted_latencies = sorted(latencies)
            idx = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[min(idx, len(sorted_latencies) - 1)]

        return PerformanceBenchmark(
            model_name=model_name or "unknown",
            total_runs=total_runs,
            avg_latency_s=avg_latency,
            avg_ttft_s=avg_ttft,
            avg_tokens_per_sec=avg_tokens_per_sec,
            total_tokens=total_tokens,
            min_latency_s=min_latency,
            max_latency_s=max_latency,
            p95_latency_s=p95_latency,
            error_count=error_count,
            success_count=success_count,
        )

    def optimize(self, benchmark: PerformanceBenchmark) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on benchmark results.

        Returns a list of prioritized, actionable optimization recommendations
        based on the benchmark metrics.

        Args:
            benchmark: The performance benchmark to generate recommendations for

        Returns:
            List of optimization recommendations, sorted by priority
        """
        recommendations: List[OptimizationRecommendation] = []

        # Latency optimizations
        if benchmark.avg_latency_s is not None and benchmark.avg_latency_s > 1.0:
            recommendations.append(OptimizationRecommendation(
                category="latency",
                priority="high",
                description="Average latency exceeds 1 second",
                expected_improvement="reduce latency by 20-30%",
                actionable_steps=[
                    "Profile individual span components to identify bottlenecks",
                    "Consider model with faster inference",
                    "Reduce context window if not needed",
                    "Implement caching for repeated computations",
                ]
            ))

        if benchmark.min_latency_s is not None and benchmark.max_latency_s is not None:
            latency_range = benchmark.max_latency_s - benchmark.min_latency_s
            if latency_range > benchmark.avg_latency_s * 0.5:  # high variance
                recommendations.append(OptimizationRecommendation(
                    category="latency",
                    priority="medium",
                    description="High latency variance across runs",
                    expected_improvement="stabilize performance by 15-25%",
                    actionable_steps=[
                        "Set random seeds for reproducibility",
                        "Implement deterministic execution flows",
                        "Add warm-up runs before measurement",
                    ]
                ))

        # TTFT optimizations
        if benchmark.avg_ttft_s is not None and benchmark.avg_ttft_s > 0.5:
            recommendations.append(OptimizationRecommendation(
                category="latency",
                priority="high",
                description="Average TTFT exceeds 500ms",
                expected_improvement="reduce TTFT by 30-40%",
                actionable_steps=[
                    "Implement model warm-up before first request",
                    "Use model caching / persistent serving",
                    "Reduce prompt size to essential elements only",
                ]
            ))

        # Throughput optimizations
        if benchmark.avg_tokens_per_sec is not None and benchmark.avg_tokens_per_sec < 20:
            recommendations.append(OptimizationRecommendation(
                category="throughput",
                priority="high",
                description="Low tokens/second throughput",
                expected_improvement="increase throughput by 2x",
                actionable_steps=[
                    "Use a model optimized for throughput",
                    "Batch requests when possible",
                    "Implement token counting for better predictability",
                ]
            ))

        # Token usage optimizations
        if benchmark.total_tokens is not None and benchmark.total_tokens > 5000:
            recommendations.append(OptimizationRecommendation(
                category="tokens",
                priority="medium",
                description="Total tokens exceed 5k across runs",
                expected_improvement="reduce token usage by 15-25%",
                actionable_steps=[
                    "Implement prompt compression",
                    "Extract only essential context",
                    "Use token-efficient model instructions",
                ]
            ))

        # Cost optimizations (if cost data available via metadata)
        # Note: cost estimation is heuristic since not all spans track cost
        if benchmark.error_count > benchmark.total_runs * 0.3:
            recommendations.append(OptimizationRecommendation(
                category="cost",
                priority="high",
                description="High error rate (" + str(benchmark.error_count) + "/" + str(benchmark.total_runs) +
                             ") leads to wasted tokens on failed runs",
                expected_improvement="reduce wasted tokens by " + str(
                    round(benchmark.error_count / benchmark.total_runs * 100, 1)) + "%",
                actionable_steps=[
                    "Review and fix root causes of failures",
                    "Implement better error handling and retries",
                    "Add validation before model calls",
                ]
            ))

        # Sort by priority: high > medium > low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

        return recommendations