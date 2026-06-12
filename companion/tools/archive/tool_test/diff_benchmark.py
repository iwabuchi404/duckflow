import docopt
import difflib
import json
import os
import sys

USAGE = """
Diff Benchmark Tool

Usage:
  diff_benchmark.py <dir1> <dir2>
  diff_benchmark.py (-h | --help)

Options:
  -h --help  Show this screen.
"""

def main():
    args = docopt.docopt(USAGE)
    dir1 = args['<dir1>']
    dir2 = args['<dir2>']
    
    # Validate directory existence
    if not os.path.isdir(dir1):
        print(json.dumps({
            "status": "error",
            "metrics": {
                "files": {"total": 0, "different": 0},
                "lines": {"added": 0, "removed": 0},
                "similarity": 0.0
            }
        }))
        sys.exit(1)
    if not os.path.isdir(dir2):
        print(json.dumps({
            "status": "error",
            "metrics": {
                "files": {"total": 0, "different": 0},
                "lines": {"added": 0, "removed": 0},
                "similarity": 0.0
            }
        }))
        sys.exit(1)
    
    # Get top-level files in both directories
    files1 = set(f for f in os.listdir(dir1) 
                if os.path.isfile(os.path.join(dir1, f)))
    files2 = set(f for f in os.listdir(dir2) 
                if os.path.isfile(os.path.join(dir2, f)))
    
    common_files = files1 & files2
    total_files = len(common_files)
    
    different_files = 0
    total_added = 0
    total_removed = 0
    total_similarity = 0.0
    
    for fname in common_files:
        path1 = os.path.join(dir1, fname)
        path2 = os.path.join(dir2, fname)
        
        try:
            with open(path1, 'r') as f1, open(path2, 'r') as f2:
                lines1 = f1.readlines()
                lines2 = f2.readlines()
        except (OSError, UnicodeDecodeError):
            different_files += 1
            continue
        
        # Calculate line differences
        diff = difflib.Differ().compare(lines1, lines2)
        added = removed = 0
        for line in diff:
            if line.startswith('+ '):
                added += 1
            elif line.startswith('- '):
                removed += 1
        
        if added > 0 or removed > 0:
            different_files += 1
            
        total_added += added
        total_removed += removed
        
        # Calculate similarity ratio
        ratio = difflib.SequenceMatcher(None, lines1, lines2).ratio()
        total_similarity += ratio
    
    # Compute average similarity
    avg_similarity = total_similarity / total_files if total_files > 0 else 0.0
    
    metrics = {
        "files": {
            "total": total_files,
            "different": different_files
        },
        "lines": {
            "added": total_added,
            "removed": total_removed
        },
        "similarity": round(avg_similarity, 4)
    }
    
    print(json.dumps({
        "status": "ok",
        "metrics": metrics
    }))

if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({
            "status": "error",
            "metrics": {
                "files": {"total": 0, "different": 0},
                "lines": {"added": 0, "removed": 0},
                "similarity": 0.0
            }
        }))
        sys.exit(1)