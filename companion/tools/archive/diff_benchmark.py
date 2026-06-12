#!/usr/bin/env python3
"""
Diff Benchmark Tool - Compares outputs from generate tools

Usage:
  diff_benchmark.py --baseline <dir> --candidate <dir>
  diff_benchmark.py (-h | --help)

Options:
  -b --baseline <dir>   Reference directory (ground truth)
  -c --candidate <dir>  Directory to evaluate
  -h --help             Show this screen
"""
てｓｔ
import os
import sys
import argparse
from difflib import unified_diff
from collections import namedtuple

Result = namedtuple('Result', 'files_total files_missing files_extra lines_added lines_removed')

def compare_directories(baseline: str, candidate: str) -> Result:
    """Compare two directories and return metrics"""
    baseline_files = set(os.listdir(baseline))
    candidate_files = set(os.listdir(candidate))
    
    files_missing = baseline_files - candidate_files
    files_extra = candidate_files - baseline_files
    common_files = baseline_files & candidate_files
    
    lines_added = 0
    lines_removed = 0
    
    for file in common_files:
        base_path = os.path.join(baseline, file)
        cand_path = os.path.join(candidate, file)
        
        if not os.path.isfile(base_path) or not os.path.isfile(cand_path):
            continue
            
        with open(base_path) as f1, open(cand_path) as f2:
            diff = unified_diff(
                f1.readlines(),
                f2.readlines(),
                fromfile='baseline',
                tofile='candidate'
            )
            
            for line in diff:
                if line.startswith('+ ') and not line.startswith('+++'):
                    lines_added += 1
                elif line.startswith('- ') and not line.startswith('---'):
                    lines_removed += 1
    
    return Result(
        files_total=len(baseline_files),
        files_missing=len(files_missing),
        files_extra=len(files_extra),
        lines_added=lines_added,
        lines_removed=lines_removed
    )

def main():
    parser = argparse.ArgumentParser(description='Generate tool output diff benchmark')
    parser.add_argument('--baseline', required=True, help='Reference directory')
    parser.add_argument('--candidate', required=True, help='Directory to evaluate')
    args = parser.parse_args()
    
    if not os.path.isdir(args.baseline) or not os.path.isdir(args.candidate):
        print("Error: Both baseline and candidate must be valid directories")
        sys.exit(1)
    
    result = compare_directories(args.baseline, args.candidate)
    
    print(f"Diff Benchmark Report")
    print(f"=====================")
    print(f"Total files:        {result.files_total}")
    print(f"Missing files:      {result.files_missing}")
    print(f"Extra files:        {result.files_extra}")
    print(f"Lines added:        {result.lines_added}")
    print(f"Lines removed:      {result.lines_removed}")
    print(f"Net change:         {result.lines_added - result.lines_removed}")

if __name__ == "__main__":
    main()