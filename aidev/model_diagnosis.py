"""Local AI diagnosis for AI DevTools - deterministic diagnostics for agents.

Provides deterministic diagnostics for agent execution patterns, detecting
anti-patterns such as repeated file inspection, repeated identical tool calls,
repeated test failures, context bloat, excessive repository exploration,
excessive retries, failure to run tests, unchanged actions between iterations,
and other concerning patterns.

All diagnostics are based on traced span data, never on ML predictions or
black-box heuristics. Diagnostics are explicit, explainable, and falsifiable.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set

from aidev.trace import Span, SpanStatus


class DiagnosisResult:
    """Result of agent diagnosis, containing detected patterns and recommendations."""

    def __init__(self, agent_id: str, total_spans: int):
        self.agent_id = agent_id
        self.total_spans = total_spans
        self.repeated_inspections: int = 0
        self.repeated_tool_calls: int = 0
        self.repeated_test_failures: int = 0
        self.context_bloat: bool = False
        self.excessive_exploration: bool = False
        self.excessive_retries: int = 0
        self.failure_to_run_tests: bool = False
        self.unchanged_actions: int = 0
        self.detected_patterns: List[str] = []
        self.recommendations: List[str] = []
        self.severity: str = "low"  # low, medium, high


class AgentDiagnosis:
    """Deterministic diagnostics for agent execution patterns.

    Analyzes traced spans to detect concerning agent behavior patterns.
    All findings are based on explicit count thresholds and observable
    patterns in the trace data, not on ML predictions or assumptions.
    """

    # Thresholds for diagnosis (tunable, evidence-based)
    THRESHOLD_REPEATED_INSPECTIONS: int = 3
    THRESHOLD_REPEATED_TOOL_CALLS: int = 3
    THRESHOLD_REPEATED_TEST_FAILURES: int = 2
    THRESHOLD_CONTEXT_BLOAT_TOKENS: int = 10000
    THRESHOLD_EXCESSIVE_EXPLORATION_STEPS: int = 20
    THRESHOLD_EXCESSIVE_RETRIES: int = 5
    THRESHOLD_UNCHANGED_ACTIONS: int = 3

    def diagnose(self, spans: List[Span], agent_id: str = "agent") -> DiagnosisResult:
        """Diagnose agent execution patterns from a list of spans.

        Args:
            spans: List of all spans from an agent execution
            agent_id: Identifier for the agent being diagnosed

        Returns:
            DiagnosisResult with detected patterns and recommendations
        """
        result = DiagnosisResult(agent_id=agent_id, total_spans=len(spans))

        if not spans:
            result.detected_patterns.append("no spans analyzed")
            return result

        # 1. Detect repeated inspections (same file inspected multiple times)
        result.repeated_inspections = self._count_repeated_inspections(spans)
        if result.repeated_inspections >= self.THRESHOLD_REPEATED_INSPECTIONS:
            result.detected_patterns.append(
                "repeated_file_inspections: file inspected "
                + str(result.repeated_inspections)
                + " times"
            )
            result.recommendations.append(
                "Consider caching file reads or reducing redundant inspections"
            )

        # 2. Detect repeated tool calls (identical tool calls)
        result.repeated_tool_calls = self._count_repeated_tool_calls(spans)
        if result.repeated_tool_calls >= self.THRESHOLD_REPEATED_TOOL_CALLS:
            result.detected_patterns.append(
                "repeated_tool_calls: "
                + str(result.repeated_tool_calls)
                + " identical tool calls detected"
            )
            result.recommendations.append(
                "Review tool logic to avoid redundant calls; consider caching"
            )

        # 3. Detect repeated test failures
        result.repeated_test_failures = self._count_repeated_test_failures(spans)
        if result.repeated_test_failures >= self.THRESHOLD_REPEATED_TEST_FAILURES:
            result.detected_patterns.append(
                "repeated_test_failures: "
                + str(result.repeated_test_failures)
                + " test failures detected"
            )
            result.detected_patterns.append(
                "tests_not_passed: agent repeatedly fails tests"
            )
            result.recommendations.append(
                "Review test conditions; check for flaky tests or environment issues"
            )
            result.failure_to_run_tests = True

        # 4. Detect context bloat (large total metadata/inputs across spans)
        total_tokens = self._count_total_tokens(spans)
        if total_tokens > self.THRESHOLD_CONTEXT_BLOAT_TOKENS:
            result.context_bloat = True
            result.detected_patterns.append(
                "context_bloat: total traced tokens "
                + str(total_tokens)
                + " exceed threshold "
                + str(self.THRESHOLD_CONTEXT_BLOAT_TOKENS)
            )
            result.recommendations.append(
                "Reduce context size; consider truncation or summarization"
            )

        # 5. Detect excessive exploration (many unique directories/files inspected)
        exploration_score = self._count_exploration(spans)
        if exploration_score > self.THRESHOLD_EXCESSIVE_EXPLORATION_STEPS:
            result.excessive_exploration = True
            result.detected_patterns.append(
                "excessive_exploration: "
                + str(exploration_score)
                + " unique exploration steps detected"
            )
            result.recommendations.append(
                "Define clearer search boundaries; use targeted file queries"
            )

        # 6. Detect excessive retries (repeated attempts on same span/task)
        result.excessive_retries = self._count_excessive_retries(spans)
        if result.excessive_retries >= self.THRESHOLD_EXCESSIVE_RETRIES:
            result.detected_patterns.append(
                "excessive_retries: "
                + str(result.excessive_retries)
                + " retry attempts detected"
            )
            result.recommendations.append(
                "Review retry logic; consider increasing timeouts or fixing root causes"
            )

        # 7. Detect failure to run tests
        if result.failure_to_run_tests:
            # Already added above, but ensure recommendation is clear
            pass

        # 8. Detect unchanged actions between iterations
        result.unchanged_actions = self._count_unchanged_actions(spans)
        if result.unchanged_actions >= self.THRESHOLD_UNCHANGED_ACTIONS:
            result.detected_patterns.append(
                "unchanged_actions: "
                + str(result.unchanged_actions)
                + " iterations with no observable changes"
            )
            result.recommendations.append(
                "Review agent logic; it may be stuck in a loop without progress"
            )

        # Set severity based on number and severity of patterns
        severity_score = 0
        if result.repeated_inspections >= self.THRESHOLD_REPEATED_INSPECTIONS:
            severity_score += 1
        if result.repeated_tool_calls >= self.THRESHOLD_REPEATED_TOOL_CALLS:
            severity_score += 1
        if result.repeated_test_failures >= self.THRESHOLD_REPEATED_TEST_FAILURES:
            severity_score += 2
        if result.context_bloat:
            severity_score += 1
        if result.excessive_exploration:
            severity_score += 1
        if result.excessive_retries >= self.THRESHOLD_EXCESSIVE_RETRIES:
            severity_score += 1
        if result.failure_to_run_tests:
            severity_score += 2
        if result.unchanged_actions >= self.THRESHOLD_UNCHANGED_ACTIONS:
            severity_score += 1

        if severity_score >= 5:
            result.severity = "high"
        elif severity_score >= 2:
            result.severity = "medium"
        else:
            result.severity = "low"

        return result

    # --- Internal helper methods ---

    def _count_repeated_inspections(self, spans: List[Span]) -> int:
        """Count how many times the same file was inspected across spans.

        Looks at metadata keys like 'file_path', 'path', 'filename' across all spans.
        """
        file_counts: Counter = Counter()
        for span in spans:
            # Check various possible metadata keys for file paths
            metadata = span.metadata
            for key in ["file_path", "path", "filename", "file"]:
                if key in metadata:
                    file_counts[str(metadata[key])] += 1
                    break  # count each span once

        # Count how many files were inspected more than once
        repeated = sum(1 for count in file_counts.values() if count > 1)
        return repeated

    def _count_repeated_tool_calls(self, spans: List[Span]) -> int:
        """Count how many spans have identical tool call signatures.

        Looks at metadata keys like 'tool', 'function', 'operation' and their
        arguments to identify truly identical calls.
        """
        tool_signatures: Counter = Counter()
        for span in spans:
            metadata = span.metadata
            # Build a signature from tool-related metadata keys
            sig_parts = []
            for key in ["tool", "function", "operation"]:
                if key in metadata:
                    val = str(metadata[key])
                    sig_parts.append(val)
            # Also include any args-like metadata
            for key in ["arguments", "params", "input"]:
                if key in metadata:
                    val = str(metadata[key])
                    sig_parts.append(val)

            if sig_parts:
                signature = "|".join(sig_parts)
                tool_signatures[signature] += 1

        # Count signatures that appear more than once
        repeated = sum(1 for count in tool_signatures.values() if count > 1)
        return repeated

    def _count_repeated_test_failures(self, spans: List[Span]) -> int:
        """Count spans with test failures that indicate repeated test failures.

        Looks at error messages indicating test failures across spans.
        """
        test_failure_keywords = ["test", "assert", "pytest", "unittest", "failed"]
        failure_count = 0
        for span in spans:
            errors = span.errors
            if not errors:
                continue
            for error in errors:
                error_lower = error.lower()
                if any(keyword in error_lower for keyword in test_failure_keywords):
                    failure_count += 1
                    break  # count each span once

        return failure_count

    def _count_total_tokens(self, spans: List[Span]) -> int:
        """Count total tokens across all spans from inputs, outputs, and metadata sizes.

        Note: This is a heuristic estimate since tokens aren't always explicitly
        tracked. Uses metadata size as a proxy.
        """
        total = 0
        for span in spans:
            # Add model_token_count if available
            if span.model_token_count is not None:
                total += span.model_token_count
            # Heuristic: count metadata key-value pairs as approximate tokens
            if span.metadata:
                total += len(span.metadata)
            # Heuristic: count inputs/outputs size
            if span.inputs is not None:
                total += len(str(span.inputs))
            if span.outputs is not None:
                total += len(str(span.outputs))
        return total

    def _count_exploration(self, spans: List[Span]) -> int:
        """Count unique exploration steps across spans.

        Looks at metadata for directory navigation, file listing, or exploration
        patterns to count unique exploration steps.
        """
        exploration_steps: Set[str] = set()
        for span in spans:
            metadata = span.metadata
            # Check for exploration-related keys
            for key in ["dir", "directory", "path", "listing", "explore"]:
                if key in metadata:
                    val = str(metadata[key])
                    exploration_steps.add(val)

        return len(exploration_steps)

    def _count_excessive_retries(self, spans: List[Span]) -> int:
        """Count retry attempts across spans.

        Looks for patterns indicating retry behavior, such as spans with
        the same name appearing multiple times with error status, or metadata
        indicating retry counts.
        """
        retry_count = 0
        for span in spans:
            # Check if span has error status
            if span.status == SpanStatus.ERROR:
                retry_count += 1
            # Check metadata for retry count
            metadata = span.metadata
            for key in ["retry_count", "attempt", "retries"]:
                if key in metadata:
                    try:
                        count = int(metadata[key])
                        if count > 1:
                            retry_count += count - 1  # count extras
                    except (ValueError, TypeError):
                        pass
        return retry_count

    def _count_unchanged_actions(self, spans: List[Span]) -> int:
        """Count iterations where agent actions showed no observable change.

        Looks at span metadata or errors indicating no progress between
        consecutive similar operations.
        """
        # Simple heuristic: count spans with error "no change" or similar
        no_change_count = 0
        for span in spans:
            if span.errors:
                for error in span.errors:
                    error_lower = error.lower()
                    if any(
                        kw in error_lower
                        for kw in ["no change", "unchanged", "stagnant", "same as before"]
                    ):
                        no_change_count += 1
                        break
        return no_change_count