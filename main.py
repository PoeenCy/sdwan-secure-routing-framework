import sys
from pathlib import Path
from audit_system.orchestrator.controller import Orchestrator
from audit_system.deployment.metrics import MetricsCollector


def main():
    base_dir = Path(__file__).resolve().parent
    ki_dir = base_dir / "Knowledge"
    code_dir = base_dir / "zt_sr_sdwan"
    output_dir = code_dir / "results"

    if not ki_dir.exists():
        print("Knowledge/ is not included in the public repository.")
        print("Run the core benchmark instead:")
        print("  cd zt_sr_sdwan")
        print("  python scripts/run_baselines.py")
        print("  python scripts/export_calculation_csvs.py")
        return

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    orchestrator = Orchestrator(ki_dir, code_dir, output_dir)

    print("Executing Phase 1: Audit...")
    audit_report = orchestrator.execute_phase_1_audit()
    print(f"Audit completed. Found {len(audit_report.discrepancies)} discrepancies.")

    print("Executing Phase 2: Dataset Generation...")
    dataset = orchestrator.execute_phase_2_dataset()
    print("Dataset built successfully.")

    print("Executing Phase 3: Fixing Code...")
    patch_report = orchestrator.execute_phase_3_fix(audit_report)
    print(f"Applied {len(patch_report.patches)} patches.")

    print("Executing Phase 4: Baseline Comparison...")
    report = orchestrator.execute_phase_4_baseline(dataset)
    print("Baselines completed.")

    MetricsCollector.save_charts(report, output_dir)
    print("Charts saved to output directory.")


if __name__ == "__main__":
    main()
