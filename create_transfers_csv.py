#!/usr/bin/env python3
"""Export transfers from transfers_config.py to CSV file."""

import csv
import os
from pathlib import Path
from settings import OUTGOING_TRANSFERS


def export_to_csv():
    """Export OUTGOING_TRANSFERS to CSV file."""
    # Create exports directory if it doesn't exist
    exports_dir = Path(__file__).parent / "exports"
    exports_dir.mkdir(exist_ok=True)
    
    # Define output file path
    output_file = exports_dir / "outgoing_transfers.csv"
    
    # Write to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["name", "old_team", "new_team"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(OUTGOING_TRANSFERS)
    
    print(f"✓ Exported {len(OUTGOING_TRANSFERS)} transfers to {output_file}")


if __name__ == "__main__":
    export_to_csv()
