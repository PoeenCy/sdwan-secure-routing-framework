"""
Data models for baseline evaluation and comparison reporting.

Covers baseline algorithm execution and performance comparison.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List
import pandas as pd


@dataclass
class BaselineResult:
    """
    Result from executing a baseline algorithm on a scenario.

    Attributes:
        algorithm: Name of the algorithm (SP-Routing, QoS-Routing, Seg-Routing, ZT-Routing, ZT-SR-DRL)
        scenario: Scenario identifier (S1, S2, S3, S4, S5)
        avg_latency: Average path latency in milliseconds
        avg_bn_on_path: Average Betweenness Number on selected path
        min_trust_on_path: Minimum trust score on selected path
        mspl_g_final: Final Mean Shortest Path Length on attack graph G
        reroute_time_ms: Time taken for route computation in milliseconds
        metadata: Additional algorithm-specific metadata
    """

    algorithm: str
    scenario: str
    avg_latency: float
    avg_bn_on_path: float
    min_trust_on_path: float
    mspl_g_final: float
    reroute_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate baseline result data."""
        valid_algorithms = {
            "SP-Routing",
            "QoS-Routing",
            "Seg-Routing",
            "ZT-Routing",
            "ZT-SR-DRL",
        }
        if self.algorithm not in valid_algorithms:
            raise ValueError(
                f"algorithm must be one of {valid_algorithms}, got {self.algorithm}"
            )

        valid_scenarios = {"S1", "S2", "S3", "S4", "S5"}
        if self.scenario not in valid_scenarios:
            raise ValueError(
                f"scenario must be one of {valid_scenarios}, got {self.scenario}"
            )

        # Validate metric ranges
        if self.avg_latency < 0:
            raise ValueError(
                f"avg_latency must be non-negative, got {self.avg_latency}"
            )

        if self.avg_bn_on_path < 0:
            raise ValueError(
                f"avg_bn_on_path must be non-negative, got {self.avg_bn_on_path}"
            )

        if not 0 <= self.min_trust_on_path <= 1:
            raise ValueError(
                f"min_trust_on_path must be in [0, 1], got {self.min_trust_on_path}"
            )

        if self.mspl_g_final < 0:
            raise ValueError(
                f"mspl_g_final must be non-negative, got {self.mspl_g_final}"
            )

        if self.reroute_time_ms < 0:
            raise ValueError(
                f"reroute_time_ms must be non-negative, got {self.reroute_time_ms}"
            )


@dataclass
class ComparisonReport:
    """
    Comprehensive comparison report across all baseline algorithms and scenarios.

    Attributes:
        results: List of all baseline execution results
        comparison_table: Pandas DataFrame with pivoted comparison data
        timestamp: When the comparison was generated
        dataset_source: Identifier of the dataset used for evaluation
        summary_statistics: Optional summary statistics across algorithms
    """

    results: List[BaselineResult]
    comparison_table: pd.DataFrame
    timestamp: datetime
    dataset_source: str
    summary_statistics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate comparison report."""
        if not self.results:
            raise ValueError("results list cannot be empty")

        if self.comparison_table is None or self.comparison_table.empty:
            raise ValueError("comparison_table must be a non-empty DataFrame")

    @classmethod
    def from_results(
        cls, results: List[BaselineResult], dataset_source: str
    ) -> "ComparisonReport":
        """
        Create a ComparisonReport from a list of baseline results.

        Automatically generates comparison table and summary statistics.

        Args:
            results: List of BaselineResult objects
            dataset_source: Identifier of the dataset used

        Returns:
            ComparisonReport with generated tables and statistics
        """
        if not results:
            raise ValueError("results list cannot be empty")

        # Convert results to DataFrame
        df = pd.DataFrame(
            [
                {
                    "algorithm": r.algorithm,
                    "scenario": r.scenario,
                    "avg_latency": r.avg_latency,
                    "avg_bn_on_path": r.avg_bn_on_path,
                    "min_trust_on_path": r.min_trust_on_path,
                    "mspl_g_final": r.mspl_g_final,
                    "reroute_time_ms": r.reroute_time_ms,
                }
                for r in results
            ]
        )

        # Create pivot table for easy comparison
        comparison_table = df.pivot_table(
            index="algorithm",
            columns="scenario",
            values=[
                "avg_latency",
                "avg_bn_on_path",
                "min_trust_on_path",
                "mspl_g_final",
                "reroute_time_ms",
            ],
        )

        # Calculate summary statistics
        summary_stats = {
            "total_runs": len(results),
            "algorithms_tested": df["algorithm"].nunique(),
            "scenarios_tested": df["scenario"].nunique(),
            "avg_latency_overall": df["avg_latency"].mean(),
            "avg_trust_overall": df["min_trust_on_path"].mean(),
            "avg_mspl_overall": df["mspl_g_final"].mean(),
            "avg_reroute_time_overall": df["reroute_time_ms"].mean(),
        }

        return cls(
            results=results,
            comparison_table=comparison_table,
            timestamp=datetime.now(),
            dataset_source=dataset_source,
            summary_statistics=summary_stats,
        )

    @property
    def best_algorithm_by_latency(self) -> str:
        """Identify algorithm with lowest average latency across all scenarios."""
        df = pd.DataFrame(
            [
                {"algorithm": r.algorithm, "avg_latency": r.avg_latency}
                for r in self.results
            ]
        )
        return df.groupby("algorithm")["avg_latency"].mean().idxmin()

    @property
    def best_algorithm_by_trust(self) -> str:
        """Identify algorithm with highest average minimum trust across all scenarios."""
        df = pd.DataFrame(
            [
                {"algorithm": r.algorithm, "min_trust_on_path": r.min_trust_on_path}
                for r in self.results
            ]
        )
        return df.groupby("algorithm")["min_trust_on_path"].mean().idxmax()

    @property
    def best_algorithm_by_mspl(self) -> str:
        """Identify algorithm with highest average MSPL (most secure) across all scenarios."""
        df = pd.DataFrame(
            [
                {"algorithm": r.algorithm, "mspl_g_final": r.mspl_g_final}
                for r in self.results
            ]
        )
        return df.groupby("algorithm")["mspl_g_final"].mean().idxmax()

    def get_results_for_scenario(self, scenario: str) -> List[BaselineResult]:
        """Get all results for a specific scenario."""
        return [r for r in self.results if r.scenario == scenario]

    def get_results_for_algorithm(self, algorithm: str) -> List[BaselineResult]:
        """Get all results for a specific algorithm."""
        return [r for r in self.results if r.algorithm == algorithm]
