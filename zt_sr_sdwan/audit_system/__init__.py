"""
ZT-SR Audit and Refactor System

This package implements a comprehensive auditing and refactoring system for the 
Zero Trust SD-WAN Secure Routing (ZT-SR) codebase.

Mission:
- Audit code against 4 Knowledge Item (KI) specification files
- Build training datasets from real data sources (CAIDA traffic, NVD CVE)
- Fix discrepancies with checkpoint confirmations
- Run baseline comparisons on corrected implementation

Package Structure:
- engine/: Audit engine with formula validators and code inspectors
- dataset/: Dataset builder with CAIDA/NVD fetchers and schema mappers
- deployment/: Deployment pipeline with code patcher and baseline runner
- orchestrator/: Phase controller and checkpoint manager
- models/: Data classes for reports, discrepancies, and configurations
- config/: Configuration files for audit parameters and thresholds
- utils/: Utility functions and helpers
"""

__version__ = "0.1.0"
__author__ = "ZT-SR Audit System"

# Export key components when available
# from .engine import AuditEngine
# from .dataset import DatasetBuilder
# from .deployment import DeploymentPipeline
# from .orchestrator import PhaseController
