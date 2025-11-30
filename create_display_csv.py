#!/usr/bin/env python3
"""
Create a simplified display CSV from the full roster export.

This script takes the full TSV export and creates a cleaner version with:
- Only essential columns
- Abbreviated stat column names (e.g., "K" instead of "Kills", "MP" instead of "Matches Played")
- Unprotected values (removes Excel =" protection)
"""

import pandas as pd
import re


def excel_unprotect(val: str) -> str:
    """
    Remove Excel protection formatting (="...") from a value.
    """
    if not isinstance(val, str):
        return val
    # Remove ="..." wrapping
    match = re.match(r'^="(.*)"$', val)
    if match:
        return match.group(1)
    return val


# Column mapping: (source_column, display_column_name)
COLUMN_MAPPING = [
    ("Team", "Team"),
    ("Conference", "Conference"),
    ("Team Rpi Rank", "Rank"),
    ("Team Overall Record", "Record"),
    ("Name", "Name"),
    ("Position", "Position"),
    ("Class", "Class"),
    ("Height", "Height"),
    ("Matches Started", "MS"),
    ("Matches Played", "MP"),
    ("Sets Played", "SP"),
    ("Points", "PTS"),
    ("Points Per Set", "PTS/S"),
    ("Kills", "K"),
    ("Kills Per Set", "K/S"),
    ("Attack Errors", "AE"),
    ("Total Attacks", "TA"),
    ("Hitting Pct", "HIT%"),
    ("Assists", "A"),
    ("Assists Per Set", "A/S"),
    ("Aces", "SA"),
    ("Aces Per Set", "SA/S"),
    ("Service Errors", "SE"),
    ("Digs", "D"),
    ("Digs Per Set", "D/S"),
    ("Reception Errors", "RE"),
    ("Block Solos", "BS"),
    ("Block Assists", "BA"),
    ("Total Blocks", "TB"),
    ("Blocks Per Set", "B/S"),
    ("Ball Handling Errors", "BHE"),
]

# Optional columns that might not exist in source
OPTIONAL_COLUMNS = ["Rec%", "Block Errors"]


def create_display_csv(input_file: str, output_csv: str, output_tsv: str = None):
    """
    Create simplified display CSV from full roster export.
    
    Args:
        input_file: Path to input TSV file (full export)
        output_csv: Path to output CSV file
        output_tsv: Optional path to output TSV file
    """
    print(f"Reading data from: {input_file}")
    df = pd.read_csv(input_file, sep="\t")
    
    print(f"Input: {len(df)} rows, {len(df.columns)} columns")
    
    # Build list of columns to extract
    output_columns = []
    renamed_columns = {}
    
    for source_col, display_col in COLUMN_MAPPING:
        if source_col in df.columns:
            output_columns.append(source_col)
            renamed_columns[source_col] = display_col
        else:
            print(f"Warning: Column '{source_col}' not found in input")
    
    # Add optional columns if they exist
    for col in OPTIONAL_COLUMNS:
        if col in df.columns:
            output_columns.append(col)
            renamed_columns[col] = col  # Keep same name
    
    # Extract and rename columns
    display_df = df[output_columns].copy()
    display_df.rename(columns=renamed_columns, inplace=True)
    
    # Unprotect Excel-protected values (remove =" wrapping)
    for col in display_df.columns:
        if display_df[col].dtype == "object":
            display_df[col] = display_df[col].apply(
                lambda x: excel_unprotect(str(x)) if pd.notna(x) else x
            )
    
    print(f"Output: {len(display_df)} rows, {len(display_df.columns)} columns")
    
    # Write CSV
    display_df.to_csv(output_csv, index=False)
    print(f"Wrote CSV to: {output_csv}")
    
    # Write TSV if requested
    if output_tsv:
        display_df.to_csv(output_tsv, sep="\t", index=False)
        print(f"Wrote TSV to: {output_tsv}")
    
    # Print column summary
    print("\nColumns in output:")
    for i, col in enumerate(display_df.columns, 1):
        non_null = display_df[col].notna().sum()
        pct = 100 * non_null / len(display_df)
        print(f"  {i:2}. {col:12} ({non_null}/{len(display_df)} = {pct:.1f}%)")


if __name__ == "__main__":
    input_file = "exports/d1_rosters_2026_with_stats_and_incoming.tsv"
    output_csv = "exports/d1_display_2026.csv"
    output_tsv = "exports/d1_display_2026.tsv"
    
    create_display_csv(input_file, output_csv, output_tsv)
