#!/usr/bin/env python3
"""
Run PromptSmith improvement cycle after test execution.
This script is intended to be called from the CI pipeline.
"""

import sys
from pathlib import Path
from codecrafter.promptsmith.orchestrator import PromptSmithOrchestrator

def main():
    # Default paths
    unit_report = "reports/unit.json"
    e2e_report = "reports/e2e.json"

    # CLI arguments: optional unit report path and optional e2e report path
    if len(sys.argv) > 1:
        unit_report = sys.argv[1]
    if len(sys.argv) > 2:
        e2e_report = sys.argv[2]

    orchestrator = PromptSmithOrchestrator(unit_report_path=unit_report, e2e_report_path=e2e_report)
    orchestrator.run_improvement_cycle()

if __name__ == "__main__":
    main()