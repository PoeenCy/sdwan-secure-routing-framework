# ZT-SR Audit and Refactor System

## Overview

This directory contains the comprehensive auditing and refactoring system for the Zero Trust SD-WAN Secure Routing (ZT-SR) codebase. The system implements a phase-gated workflow that audits existing code against locked Knowledge Item specifications, builds real datasets from CAIDA and NVD sources, and deploys corrections with baseline comparisons.

## Mission

1. **Audit** code against 4 Knowledge Item (KI) specification files
2. **Build** training datasets from real data sources (CAIDA traffic, NVD CVE)
3. **Fix** discrepancies with checkpoint confirmations
4. **Run** baseline comparisons on corrected implementation

## Directory Structure

```
audit_system/
├── __init__.py                 # Package initialization and exports
├── README.md                   # This file
│
├── engine/                     # Phase 1: Audit Engine
│   ├── __init__.py
│   ├── formula_validator.py   # Validates formulas against KI specs
│   ├── code_inspector.py      # Analyzes source code for discrepancies
│   └── discrepancy_reporter.py # Generates audit reports
│
├── dataset/                    # Phase 2: Dataset Builder
│   ├── __init__.py
│   ├── caida_fetcher.py       # Downloads CAIDA traffic data
│   ├── nvd_fetcher.py         # Retrieves NVD CVE/CVSS data
│   ├── schema_mapper.py       # Maps external data to state vector
│   └── consistency_checker.py # Validates dataset integrity
│
├── deployment/                 # Phase 3 & 4: Deployment Pipeline
│   ├── __init__.py
│   ├── code_patcher.py        # Applies code fixes
│   ├── baseline_runner.py     # Executes baseline algorithms
│   ├── metrics_collector.py   # Gathers performance metrics
│   └── report_generator.py    # Creates comparison reports
│
├── orchestrator/               # Workflow Orchestration
│   ├── __init__.py
│   ├── phase_controller.py    # Coordinates phase transitions
│   ├── checkpoint_manager.py  # Manages approval checkpoints
│   └── progress_tracker.py    # Monitors execution status
│
├── models/                     # Data Models
│   ├── __init__.py
│   ├── discrepancy.py         # Discrepancy data structure
│   ├── audit_report.py        # Audit report model
│   ├── traffic_data.py        # CAIDA traffic data model
│   ├── vulnerability_data.py  # NVD CVE data model
│   ├── baseline_result.py     # Baseline metrics model
│   └── checkpoint_status.py   # Checkpoint tracking model
│
├── config/                     # Configuration Files
│   ├── __init__.py
│   ├── audit_params.yaml      # Audit engine parameters
│   ├── dataset_sources.yaml   # Data source endpoints
│   ├── severity_rules.yaml    # Discrepancy severity rules
│   ├── baseline_config.yaml   # Baseline algorithm config
│   └── phase_workflow.yaml    # Phase definitions
│
└── utils/                      # Utility Functions
    ├── __init__.py
    ├── file_utils.py          # File I/O helpers
    ├── formula_parser.py      # Formula parsing utilities
    ├── logging_utils.py       # Logging configuration
    ├── validators.py          # Common validators
    └── path_utils.py          # Path resolution helpers
```

## Phase-Gated Workflow

```
PHASE 1: AUDIT
   KI Files → Formula Validator → Discrepancy List → [CHECKPOINT] → User Review

PHASE 2: DATASET BUILD
   CAIDA API → Fetcher → Traffic Data
   NVD API → Fetcher → CVE Data
   → Schema Mapper → Unified Dataset → Consistency Check → [CHECKPOINT]

PHASE 3: CODE FIX
   Discrepancy List → Code Patcher → Modified Codebase → Test Suite → [CHECKPOINT]

PHASE 4: BASELINE EVALUATION
   5 Algorithms × Same Dataset → Metrics Collector → Comparison Report
```

## Design Principles

- **Phase-gated execution**: Mandatory checkpoints between phases
- **KI files as single source of truth**: All specifications locked in Knowledge Items
- **Real data integration**: CAIDA traffic and NVD CVE data, not synthetic
- **Discrepancy tracking**: Severity classification (Critical/Medium/Light)
- **Comprehensive audit**: Complete audit before any modifications

## Key Components

### 1. Audit Engine (Phase 1)
Audits existing codebase against KI specifications:
- Trust Score formula validation
- Action Masking completeness check
- Dynamic threshold verification
- Reward function component audit
- 16 Basta metrics validation

### 2. Dataset Builder (Phase 2)
Builds real training datasets:
- CAIDA traffic data (InternetMCI topology)
- NVD CVE/CVSS vulnerability records
- Controlled synthetic behavior scenarios
- Complete state vector per KI_04 §8

### 3. Deployment Pipeline (Phases 3 & 4)
Deploys fixes and runs evaluations:
- Code patching with fix tracking
- 5 baseline algorithms (SP, QoS, Seg, ZT, ZT-SR-DRL)
- Metrics collection (latency, BN, Trust, MSPL, re-route time)
- Comparison report generation

### 4. Orchestrator
Manages workflow execution:
- Phase coordination
- Checkpoint enforcement
- Progress monitoring
- Status reporting

## Target Environment

- **Existing codebase**: `zt_sr_sdwan/` directory
- **Topology**: InternetMCI 19-node WAN from Topology Zoo
- **Framework**: NetworkX for graph operations
- **ML Framework**: PyTorch for DRL (Double DQN)
- **Python**: 3.9+

## Usage

The audit system will be executed through the orchestrator:

```python
from audit_system.orchestrator import PhaseController

# Initialize phase controller
controller = PhaseController()

# Execute phase-gated workflow
controller.run_phase_1_audit()      # Audit code against KI files
# [User reviews audit report at checkpoint]

controller.run_phase_2_dataset()    # Build real datasets
# [User validates dataset at checkpoint]

controller.run_phase_3_fixes()      # Apply code corrections
# [User tests fixes at checkpoint]

controller.run_phase_4_baseline()   # Run baseline comparisons
# [Final report generated]
```

## Implementation Status

**Phase A: Core Infrastructure (Week 1-2)** - In Progress
- [x] Task 1.1: Directory structure created
- [ ] Task 1.2: Data models implementation
- [ ] Task 1.3: Configuration files setup
- [ ] Task 1.4: Utility functions implementation

## Related Documentation

- **Requirements**: `.kiro/specs/zt-sr-audit-refactor/requirements.md`
- **Design**: `.kiro/specs/zt-sr-audit-refactor/design.md`
- **Tasks**: `.kiro/specs/zt-sr-audit-refactor/tasks.md`
- **KI Files**: `Knowledge/KI_*.md` (specification source of truth)

## Notes

- All formulas and parameters must match KI files exactly
- KI files are always correct; discrepancies in code are bugs
- Real data sources (CAIDA, NVD) must be used for training datasets
- No arbitrary hardcoded values without justification
- Phase transitions require explicit checkpoint approval
