#!/usr/bin/env python3
"""
Run the complete volleyball scraping pipeline.

This script executes all steps in order:
1. Run main scraper (collect roster and stats data)
2. Merge manual rosters (for JavaScript-rendered sites)
3. Merge manual stats (for teams with manual stats files)
4. Create team pivot (generate team-level analysis)

Usage:
    python scripts/run_full_pipeline.py
    python scripts/run_full_pipeline.py --skip-scraper    # Skip step 1
    python scripts/run_full_pipeline.py --year 2025       # Specify season year
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_command(description: str, cmd: list, check: bool = True) -> bool:
    """
    Run a command and report progress.
    
    Args:
        description: Human-readable description of the step
        cmd: Command as list of strings
        check: Whether to exit on error (default: True)
        
    Returns:
        bool: True if command succeeded, False otherwise
    """
    print()
    print("=" * 80)
    print(f"STEP: {description}")
    print("=" * 80)
    print(f"Command: {' '.join(cmd)}")
    print()
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, check=check, cwd=str(project_root))
        elapsed = time.time() - start_time
        
        print()
        print(f"✓ Completed in {elapsed:.1f} seconds")
        return result.returncode == 0
        
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print()
        print(f"✗ Failed after {elapsed:.1f} seconds")
        print(f"Exit code: {e.returncode}")
        
        if check:
            print()
            print("Pipeline stopped due to error. Fix the issue and try again.")
            sys.exit(e.returncode)
        
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run the complete volleyball scraping pipeline"
    )
    parser.add_argument(
        "--skip-scraper",
        action="store_true",
        help="Skip the main scraper step (use existing rosters_and_stats.csv)"
    )
    parser.add_argument(
        "--skip-manual-rosters",
        action="store_true",
        help="Skip the manual roster merge step"
    )
    parser.add_argument(
        "--skip-manual-stats",
        action="store_true",
        help="Skip the manual stats merge step"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Season year for scraping (e.g., 2025)"
    )
    parser.add_argument(
        "--team",
        action="append",
        dest="teams",
        help="Specific team(s) to scrape (can be used multiple times)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't use coaches cache in team pivot"
    )
    parser.add_argument(
        "--refresh-coaches",
        action="store_true",
        help="Fetch coaches live instead of using cache"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("VOLLEYBALL SCRAPING PIPELINE")
    print("=" * 80)
    print()
    print("This will run the following steps:")
    if not args.skip_scraper:
        print("  1. Run main scraper")
    if not args.skip_manual_rosters:
        print("  2. Merge manual rosters")
    if not args.skip_manual_stats:
        print("  3. Merge manual stats")
    print("  4. Create team pivot")
    print()
    
    # Track overall start time
    pipeline_start = time.time()
    
    # Step 1: Run main scraper
    if not args.skip_scraper:
        cmd = [sys.executable, "-m", "src.run_scraper"]
        
        if args.year:
            cmd.extend(["--year", str(args.year)])
        
        if args.teams:
            for team in args.teams:
                cmd.extend(["--team", team])
        
        success = run_command("Run main scraper", cmd)
        if not success:
            return
    else:
        print()
        print("⊘ Skipping main scraper (using existing data)")
    
    # Step 2: Merge manual rosters
    if not args.skip_manual_rosters:
        cmd = [sys.executable, "-m", "src.merge_manual_rosters"]
        success = run_command("Merge manual rosters", cmd)
        if not success:
            return
    else:
        print()
        print("⊘ Skipping manual roster merge")
    
    # Step 3: Merge manual stats
    if not args.skip_manual_stats:
        cmd = [sys.executable, "-m", "src.merge_manual_stats"]
        # Note: This might fail if no stats/ directory exists, but that's okay
        success = run_command("Merge manual stats", cmd, check=False)
        if not success:
            print("Note: Manual stats merge had warnings or no stats files found")
    else:
        print()
        print("⊘ Skipping manual stats merge")
    
    # Step 4: Create team pivot
    cmd = [sys.executable, "-m", "src.create_team_pivot_csv"]
    
    if args.no_cache:
        cmd.append("--no-cache")
    elif args.refresh_coaches:
        cmd.append("--refresh-coaches")
    
    success = run_command("Create team pivot", cmd)
    if not success:
        return
    
    # Pipeline complete
    pipeline_elapsed = time.time() - pipeline_start
    
    print()
    print("=" * 80)
    print("PIPELINE COMPLETE!")
    print("=" * 80)
    print(f"Total time: {pipeline_elapsed:.1f} seconds ({pipeline_elapsed/60:.1f} minutes)")
    print()
    print("Output files:")
    print("  - exports/rosters_and_stats.csv (per-player data)")
    print("  - exports/team_pivot.csv (team-level analysis)")
    print()


if __name__ == "__main__":
    main()
