import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from audit_system.models.deployment import ComparisonReport, BaselineResult


class MetricsCollector:
    @staticmethod
    def generate_comparison_report(
        results: list[BaselineResult], dataset_source: str
    ) -> ComparisonReport:
        df = pd.DataFrame([r.__dict__ for r in results])
        pivot = df.pivot_table(
            index="algorithm",
            columns="scenario",
            values=["avg_latency", "min_trust_on_path", "reroute_time_ms"],
        )
        return ComparisonReport(
            results=results,
            comparison_table=pivot,
            timestamp=datetime.now(),
            dataset_source=dataset_source,
        )

    @staticmethod
    def save_charts(report: ComparisonReport, output_dir: Path):
        df = pd.DataFrame([r.__dict__ for r in report.results])
        
        # Save the actual results to CSV so we can view them
        csv_path = output_dir / "benchmark_results_v2.csv"
        df.to_csv(csv_path, index=False)

        plt.figure(figsize=(10, 6))
        avg_lat = df.groupby("algorithm")["avg_latency"].mean().sort_values()
        avg_lat.plot(kind="bar", color="skyblue")
        plt.title("Average Latency by Algorithm")
        plt.ylabel("Latency (ms)")
        plt.tight_layout()
        plt.savefig(output_dir / "latency_comparison.png")
        plt.close()

        plt.figure(figsize=(10, 6))
        trust = (
            df.groupby("algorithm")["min_trust_on_path"]
            .mean()
            .sort_values(ascending=False)
        )
        trust.plot(kind="bar", color="lightgreen")
        plt.title("Average Minimum Trust on Path by Algorithm")
        plt.ylabel("Trust Score [0-1]")
        plt.tight_layout()
        plt.savefig(output_dir / "trust_comparison.png")
        plt.close()
