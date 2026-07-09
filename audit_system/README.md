# ZT-SR Audit and Refactor System

This is the automated auditing and refactoring system for the Zero Trust SD-WAN Secure Routing (ZT-SR) codebase.
It performs phase-gated execution to:
1. **Phase A/B**: Audit code against Knowledge Item (KI) specifications.
2. **Phase C**: Build a unified dataset using CAIDA traffic traces and NVD vulnerabilities.
3. **Phase D**: Patch code dynamically and run baseline comparisons across 5 algorithms.
4. **Phase E/F**: Orchestrate the flow and generate markdown reports.

## Structure
- `engine/`: Parses KI files and inspects Python AST for discrepancies.
- `dataset/`: Fetches mock/real CAIDA and NVD data, mapped to InternetMCI graph.
- `deployment/`: Modifies code using string patches and runs baseline execution.
- `orchestrator/`: Controls the Phase 1 -> 4 gating and checkpoints.

## Running Tests
```bash
python -m unittest discover tests/
```
