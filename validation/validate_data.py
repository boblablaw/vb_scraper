#!/usr/bin/env python3
"""
Comprehensive data validation for D1 volleyball roster scraper.

Validates:
- Position normalization and completeness
- Height format and completeness
- Class year normalization and completeness
- Detection of non-players (coaches, staff)
- Team-level data quality
- Duplicate detection
"""

import re
import os
import argparse
from typing import Dict, List, Tuple, Set
from collections import defaultdict, Counter
import pandas as pd
from datetime import datetime

# Import settings to get team list
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import TEAMS

# Validation rules
VALID_POSITIONS = {'S', 'OH', 'RS', 'MB', 'DS', 'L'}
VALID_CLASSES = {'Fr', 'So', 'Jr', 'Sr', 'R-Fr', 'R-So', 'R-Jr', 'R-Sr', 'Gr', 'Fifth'}
# Accept dash or apostrophe heights for 4–7 feet (e.g., 6-1, 6'1")
HEIGHT_PATTERN = re.compile(r'^[4-7]-\d{1,2}$|^[4-7]\'\s*\d{1,2}"?$')
NON_PLAYER_KEYWORDS = [
    'coach', 'assistant', 'director', 'coordinator', 'manager', 
    'trainer', 'admin', 'staff', 'volunteer', 'graduate assistant'
]
# Primary stat columns expected in exports
STAT_COLUMNS = [
    'MS', 'MP', 'SP', 'PTS', 'PTS/S', 'K', 'K/S', 'AE', 'TA', 'HIT%',
    'A', 'A/S', 'SA', 'SA/S', 'SE', 'D', 'D/S', 'RE', 'TRE', 'Rec%',
    'BS', 'BA', 'TB', 'B/S', 'BHE'
]
# Defensive/digs-focused columns (any populated value counts as present)
DIG_COLUMNS = ['D', 'D/S', 'digs_def', 'digs_per_set_def']

class DataValidator:
    def __init__(self, csv_path: str, log_path: str = None):
        # If relative path, resolve from parent directory (project root)
        if not os.path.isabs(csv_path) and not os.path.exists(csv_path):
            csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), csv_path)
        self.csv_path = csv_path
        self.log_path = log_path
        self.df = None
        self.issues = defaultdict(list)
        self.stats = defaultdict(int)
        self.team_issues = defaultdict(list)
        
    def load_data(self):
        """Load the CSV data."""
        print(f"Loading data from {self.csv_path}...")
        self.df = pd.read_csv(self.csv_path)
        print(f"Loaded {len(self.df)} rows, {len(self.df.columns)} columns")
        print(f"Teams: {self.df['Team'].nunique()}")
        self.stats['total_rows'] = len(self.df)
        self.stats['total_teams'] = self.df['Team'].nunique()
        
    def validate_positions(self):
        """Validate position normalization."""
        print("\n=== Validating Positions ===")
        
        # Check for missing positions
        missing_pos = self.df[self.df['Position'].isna() | (self.df['Position'] == '')]
        self.stats['missing_position'] = len(missing_pos)
        
        if not missing_pos.empty:
            print(f"⚠️  {len(missing_pos)} players missing position")
            teams_missing = missing_pos.groupby('Team').size().sort_values(ascending=False)

            print("\nTeams with most missing positions:")
            for team, count in teams_missing.head(10).items():
                print(f"  {team}: {count}")

            # Track all teams with missing positions so they appear in problem_teams
            for team, count in teams_missing.items():
                self.team_issues[team].append(f"Missing {count} positions")

            # Keep specific players for the report
            cols = [c for c in ['Team', 'Name', 'Position Raw'] if c in missing_pos.columns]
            self.issues['missing_position_players'] = missing_pos[cols].to_dict('records')
        else:
            print("✓ No players missing positions")
        
        # Check position format
        invalid_positions = []
        for idx, row in self.df.iterrows():
            pos = str(row['Position'])
            if pos and pos != 'nan':
                # Should be slash-separated valid codes
                codes = pos.split('/')
                invalid_codes = [c for c in codes if c not in VALID_POSITIONS]
                if invalid_codes:
                    invalid_positions.append({
                        'team': row['Team'],
                        'name': row['Name'],
                        'position': pos,
                        'invalid_codes': invalid_codes
                    })
        
        self.stats['invalid_positions'] = len(invalid_positions)
        self.issues['invalid_positions'] = invalid_positions[:50]  # Limit to 50
        
        if invalid_positions:
            print(f"⚠️  {len(invalid_positions)} players with invalid position codes")
        else:
            print("✓ All positions use valid codes")
        
        # Check for players with raw position but no normalized position (normalization failed)
        failed_pos_normalization = []
        for idx, row in self.df.iterrows():
            pos = str(row['Position']).strip()
            pos_raw = str(row.get('Position Raw', '')).strip()
            
            # Has raw position but missing or empty normalized position
            if pos_raw and pos_raw != 'nan' and pos_raw != '' and (not pos or pos == 'nan' or pos == ''):
                failed_pos_normalization.append({
                    'team': row['Team'],
                    'name': row['Name'],
                    'position_raw': pos_raw
                })
        
        self.stats['failed_position_normalization'] = len(failed_pos_normalization)
        self.issues['failed_position_normalization'] = failed_pos_normalization[:100]
        
        if failed_pos_normalization:
            print(f"⚠️  {len(failed_pos_normalization)} players with raw position but failed normalization")
            print("\nExamples of unnormalized raw positions:")
            raw_values = {item['position_raw'] for item in failed_pos_normalization[:50]}
            for raw in sorted(raw_values)[:20]:
                count = sum(1 for item in failed_pos_normalization if item['position_raw'] == raw)
                print(f"  '{raw}' ({count}x)")
        else:
            print("✓ All raw positions successfully normalized")
            
        # Position distribution with mapping from Position Raw
        from scraper.utils import extract_position_codes
        
        position_raw_mapping = defaultdict(int)
        for idx, row in self.df.iterrows():
            pos_raw = str(row.get('Position Raw', '')).strip()
            if pos_raw and pos_raw != 'nan' and pos_raw != '':
                position_raw_mapping[pos_raw] += 1
        
        print("\nPosition Raw -> Normalized mapping:")
        for pos_raw in sorted(position_raw_mapping.keys()):
            codes = extract_position_codes(pos_raw)
            if codes:
                normalized = '/'.join(sorted(codes))
            else:
                normalized = 'Skip'
            count = position_raw_mapping[pos_raw]
            print(f"  {pos_raw}: {count} = {normalized}")
        
        # Position distribution (normalized)
        position_counts = defaultdict(int)
        for pos in self.df['Position'].dropna():
            if str(pos) != 'nan':
                for code in str(pos).split('/'):
                    position_counts[code] += 1
        
        print("\nNormalized position distribution:")
        for pos in sorted(position_counts.keys()):
            print(f"  {pos}: {position_counts[pos]}")
            self.stats[f'position_{pos}'] = position_counts[pos]
    
    def validate_heights(self):
        """Validate height normalization."""
        print("\n=== Validating Heights ===")
        
        # Check for missing heights
        missing_height = self.df[self.df['Height'].isna() | (self.df['Height'] == '')]
        self.stats['missing_height'] = len(missing_height)
        
        print(f"Missing heights: {len(missing_height)} ({len(missing_height)/len(self.df)*100:.1f}%)")
        
        if not missing_height.empty:
            # Group by team
            teams_missing = missing_height.groupby('Team').size().sort_values(ascending=False)
            print(f"\nTeams with most missing heights:")
            for team, count in teams_missing.head(10).items():
                print(f"  {team}: {count}")

            # Track every team with any missing heights (not just top 10) so they appear in problem_teams
            for team, count in teams_missing.items():
                self.team_issues[team].append(f"Missing {count} heights")

            # Keep a trimmed list of specific players missing heights for the report
            self.issues['missing_height_players'] = missing_height[['Team', 'Name']].to_dict('records')
        
        # Check height format
        invalid_heights = []
        for idx, row in self.df.iterrows():
            height = str(row['Height']).strip()
            if height and height != 'nan' and height != '':
                # Remove Excel protection if present
                if height.startswith('="') and height.endswith('"'):
                    height = height[2:-1]
                
                # Check format: should be F-I or F' I"
                if not HEIGHT_PATTERN.match(height):
                    invalid_heights.append({
                        'team': row['Team'],
                        'name': row['Name'],
                        'height': height,
                        'height_raw': row.get('Height Raw', '')
                    })
        
        self.stats['invalid_height_format'] = len(invalid_heights)
        self.issues['invalid_heights'] = invalid_heights[:50]
        
        if invalid_heights:
            print(f"⚠️  {len(invalid_heights)} players with invalid height format")
        else:
            print("✓ All heights in valid format")
        
        # Check for players with raw height but no normalized height (normalization failed)
        failed_height_normalization = []
        for idx, row in self.df.iterrows():
            height = str(row['Height']).strip()
            height_raw = str(row.get('Height Raw', '')).strip()
            
            # Remove Excel protection for comparison
            if height.startswith('="') and height.endswith('"'):
                height = height[2:-1].strip()
            
            # Has raw height but missing or empty normalized height
            if height_raw and height_raw != 'nan' and height_raw != '' and (not height or height == 'nan' or height == ''):
                failed_height_normalization.append({
                    'team': row['Team'],
                    'name': row['Name'],
                    'height_raw': height_raw
                })
        
        self.stats['failed_height_normalization'] = len(failed_height_normalization)
        self.issues['failed_height_normalization'] = failed_height_normalization[:100]
        
        if failed_height_normalization:
            print(f"⚠️  {len(failed_height_normalization)} players with raw height but failed normalization")
            print("\nExamples of unnormalized raw heights:")
            raw_values = {item['height_raw'] for item in failed_height_normalization[:50]}
            for raw in sorted(raw_values)[:20]:
                count = sum(1 for item in failed_height_normalization if item['height_raw'] == raw)
                print(f"  '{raw}' ({count}x)")
        else:
            print("✓ All raw heights successfully normalized")
    
    def validate_classes(self):
        """Validate class year normalization."""
        print("\n=== Validating Class Years ===")
        
        # Check for missing classes
        missing_class = self.df[self.df['Class'].isna() | (self.df['Class'] == '')]
        self.stats['missing_class'] = len(missing_class)
        
        print(f"Missing class: {len(missing_class)} ({len(missing_class)/len(self.df)*100:.1f}%)")

        if not missing_class.empty:
            teams_missing = missing_class.groupby('Team').size().sort_values(ascending=False)
            print("\nTeams with most missing classes:")
            for team, count in teams_missing.head(10).items():
                print(f"  {team}: {count}")

            # Track all teams with missing classes so they appear in problem_teams
            for team, count in teams_missing.items():
                self.team_issues[team].append(f"Missing {count} classes")

            # Keep specific players for the report
            cols = [c for c in ['Team', 'Name', 'Class Raw'] if c in missing_class.columns]
            self.issues['missing_class_players'] = missing_class[cols].to_dict('records')
        
        # Check for players with raw class but no normalized class (normalization failed)
        failed_normalization = []
        for idx, row in self.df.iterrows():
            cls = str(row['Class']).strip()
            cls_raw = str(row.get('Class Raw', '')).strip()
            
            # Has raw class but missing or empty normalized class
            if cls_raw and cls_raw != 'nan' and cls_raw != '' and (not cls or cls == 'nan' or cls == ''):
                failed_normalization.append({
                    'team': row['Team'],
                    'name': row['Name'],
                    'class_raw': cls_raw
                })
        
        self.stats['failed_class_normalization'] = len(failed_normalization)
        self.issues['failed_class_normalization'] = failed_normalization[:100]
        
        if failed_normalization:
            print(f"⚠️  {len(failed_normalization)} players with raw class but failed normalization")
            print("\nExamples of unnormalized raw classes:")
            raw_values = {item['class_raw'] for item in failed_normalization[:50]}
            for raw in sorted(raw_values)[:20]:
                count = sum(1 for item in failed_normalization if item['class_raw'] == raw)
                print(f"  '{raw}' ({count}x)")
        else:
            print("✓ All raw classes successfully normalized")
        
        # Check class format
        invalid_classes = []
        for idx, row in self.df.iterrows():
            cls = str(row['Class']).strip()
            if cls and cls != 'nan' and cls != '':
                if cls not in VALID_CLASSES:
                    invalid_classes.append({
                        'team': row['Team'],
                        'name': row['Name'],
                        'class': cls,
                        'class_raw': row.get('Class Raw', '')
                    })
        
        self.stats['invalid_class'] = len(invalid_classes)
        self.issues['invalid_classes'] = invalid_classes[:50]
        
        if invalid_classes:
            print(f"⚠️  {len(invalid_classes)} players with invalid class format")
        else:
            print("✓ All classes in valid format")
        
        # Class distribution
        class_counts = self.df['Class'].value_counts()
        print("\nClass distribution:")
        for cls, count in class_counts.items():
            if str(cls) != 'nan':
                print(f"  {cls}: {count}")
    
    def detect_non_players(self):
        """Detect potential non-players (coaches, staff)."""
        print("\n=== Detecting Non-Players ===")
        
        suspected_non_players = []
        
        for idx, row in self.df.iterrows():
            name = str(row['Name']).lower()
            pos_raw = str(row.get('Position Raw', '')).lower()
            class_raw = str(row.get('Class Raw', '')).lower()
            
            # Check for coach/staff keywords in name or position
            for keyword in NON_PLAYER_KEYWORDS:
                if keyword in name or keyword in pos_raw or keyword in class_raw:
                    suspected_non_players.append({
                        'team': row['Team'],
                        'name': row['Name'],
                        'position_raw': row.get('Position Raw', ''),
                        'class_raw': row.get('Class Raw', ''),
                        'keyword': keyword
                    })
                    break
        
        self.stats['suspected_non_players'] = len(suspected_non_players)
        self.issues['non_players'] = suspected_non_players
        
        if suspected_non_players:
            print(f"⚠️  {len(suspected_non_players)} suspected non-players found")
            print("\nExamples:")
            for item in suspected_non_players[:10]:
                print(f"  {item['team']}: {item['name']} (keyword: {item['keyword']})")
        else:
            print("✓ No obvious non-players detected")
    
    def check_duplicates(self):
        """Check for duplicate players."""
        print("\n=== Checking for Duplicates ===")
        
        # Check for duplicate names within same team
        duplicates = []
        for team in self.df['Team'].unique():
            team_df = self.df[self.df['Team'] == team]
            name_counts = team_df['Name'].value_counts()
            dupes = name_counts[name_counts > 1]
            if not dupes.empty:
                for name, count in dupes.items():
                    duplicates.append({
                        'team': team,
                        'name': name,
                        'count': count
                    })
        
        self.stats['duplicate_players'] = len(duplicates)
        self.issues['duplicates'] = duplicates
        
        if duplicates:
            print(f"⚠️  {len(duplicates)} duplicate player names found")
            for dup in duplicates[:20]:
                print(f"  {dup['team']}: {dup['name']} ({dup['count']}x)")
        else:
            print("✓ No duplicate players found")
    
    def validate_team_data(self):
        """Validate team-level data quality."""
        print("\n=== Validating Team Data ===")
        
        teams_with_issues = []
        
        for team_name in self.df['Team'].unique():
            team_df = self.df[self.df['Team'] == team_name]
            issues = []
            
            # Check roster size
            roster_size = len(team_df)
            if roster_size < 10:
                issues.append(f"Small roster: {roster_size} players")
            elif roster_size > 25:
                issues.append(f"Large roster: {roster_size} players")
            
            # Check missing data percentage
            missing_pos_pct = (team_df['Position'].isna() | (team_df['Position'] == '')).sum() / len(team_df)
            if missing_pos_pct > 0.5:
                issues.append(f"Missing {missing_pos_pct*100:.0f}% positions")
            
            missing_height_pct = (team_df['Height'].isna() | (team_df['Height'] == '')).sum() / len(team_df)
            if missing_height_pct > 0.5:
                issues.append(f"Missing {missing_height_pct*100:.0f}% heights")
            
            missing_class_pct = (team_df['Class'].isna() | (team_df['Class'] == '')).sum() / len(team_df)
            if missing_class_pct > 0.5:
                issues.append(f"Missing {missing_class_pct*100:.0f}% classes")
            
            if issues:
                teams_with_issues.append({
                    'team': team_name,
                    'roster_size': roster_size,
                    'issues': issues
                })
                self.team_issues[team_name].extend(issues)
        
        self.stats['teams_with_issues'] = len(teams_with_issues)
        self.issues['team_quality'] = teams_with_issues
        
        if teams_with_issues:
            print(f"⚠️  {len(teams_with_issues)} teams with data quality issues")
            print("\nTop issues:")
            for team_data in sorted(teams_with_issues, key=lambda x: len(x['issues']), reverse=True)[:15]:
                print(f"  {team_data['team']} ({team_data['roster_size']} players):")
                for issue in team_data['issues']:
                    print(f"    - {issue}")
        else:
            print("✓ All teams have good data quality")

    def check_stats_completeness(self):
        """Detect teams missing overall stats or defensive digs."""
        print("\n=== Checking Stats Completeness ===")

        stat_cols = [c for c in STAT_COLUMNS if c in self.df.columns]
        dig_cols = [c for c in DIG_COLUMNS if c in self.df.columns]

        missing_stats_teams = []
        missing_digs_teams = []

        for team_name in self.df['Team'].unique():
            team_df = self.df[self.df['Team'] == team_name]

            def has_data(cols):
                """Return True if any column in cols has at least one non-empty value."""
                if not cols:
                    return False
                for col in cols:
                    if col not in team_df.columns:
                        continue
                    series = team_df[col]
                    # Drop NaN, then check for any non-empty string after stripping
                    cleaned = series.dropna().astype(str).str.strip()
                    cleaned = cleaned[cleaned.str.lower() != 'nan']
                    if not cleaned.empty and (cleaned != '').any():
                        return True
                return False

            if not has_data(stat_cols):
                missing_stats_teams.append(team_name)
                self.team_issues[team_name].append("No player stat columns populated")

            if not has_data(dig_cols):
                missing_digs_teams.append(team_name)
                self.team_issues[team_name].append("Missing digs (defensive stats)")

        self.stats['teams_missing_stats'] = len(missing_stats_teams)
        self.stats['teams_missing_digs'] = len(missing_digs_teams)
        self.issues['teams_missing_stats'] = sorted(missing_stats_teams)
        self.issues['teams_missing_digs'] = sorted(missing_digs_teams)

        reports_dir = os.path.join("validation", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if missing_stats_teams:
            stats_path = os.path.join(reports_dir, f"missing_stats_{timestamp}.txt")
            with open(stats_path, "w") as f:
                f.write(f"# Teams with no stats columns populated ({len(missing_stats_teams)})\n\n")
                for team in sorted(missing_stats_teams):
                    f.write(team + "\n")
            print(f"⚠️  {len(missing_stats_teams)} teams have no stats; list written to {stats_path}")
        else:
            print("✓ All teams have some stat data")

        if missing_digs_teams:
            digs_path = os.path.join(reports_dir, f"missing_defensive_stats_{timestamp}.txt")
            with open(digs_path, "w") as f:
                f.write(f"# Teams missing digs (defensive stats) ({len(missing_digs_teams)})\n\n")
                for team in sorted(missing_digs_teams):
                    f.write(team + "\n")
            print(f"⚠️  {len(missing_digs_teams)} teams missing digs; list written to {digs_path}")
        else:
            print("✓ All teams have digs recorded")
    
    def analyze_log_file(self):
        """Analyze scraper log for errors and warnings."""
        if not self.log_path or not os.path.exists(self.log_path):
            print("\n⚠️  No log file available for analysis")
            return
        
        print("\n=== Analyzing Scraper Log ===")
        
        with open(self.log_path, 'r') as f:
            log_lines = f.readlines()
        
        errors = []
        warnings = []
        teams_analyzed = set()
        teams_with_errors = set()
        
        for line in log_lines:
            if 'ERROR' in line:
                errors.append(line.strip())
                # Extract team name if present
                match = re.search(r'team[:\s]+([^:]+?)(?::|$)', line, re.IGNORECASE)
                if match:
                    teams_with_errors.add(match.group(1).strip())
            elif 'WARNING' in line or 'Could not' in line:
                warnings.append(line.strip())
            elif 'Analyzing team:' in line:
                match = re.search(r'Analyzing team:\s+(.+)', line)
                if match:
                    teams_analyzed.add(match.group(1).strip())
        
        self.stats['log_errors'] = len(errors)
        self.stats['log_warnings'] = len(warnings)
        self.stats['teams_scraped'] = len(teams_analyzed)
        self.stats['teams_with_errors'] = len(teams_with_errors)
        
        print(f"Teams attempted: {len(teams_analyzed)}")
        print(f"Errors: {len(errors)}")
        print(f"Warnings: {len(warnings)}")
        
        if errors:
            print("\nRecent errors:")
            for error in errors[-10:]:
                print(f"  {error[:150]}")
        
        if teams_with_errors:
            print(f"\nTeams with scraping errors: {len(teams_with_errors)}")
            for team in sorted(teams_with_errors)[:20]:
                print(f"  - {team}")
            self.issues['teams_with_scrape_errors'] = sorted(teams_with_errors)
    
    def check_missing_teams(self):
        """Check which teams from config are missing from output."""
        print("\n=== Checking Missing Teams ===")
        
        expected_teams = {t['team'] for t in TEAMS}
        actual_teams = set(self.df['Team'].unique())
        
        missing_teams = expected_teams - actual_teams
        extra_teams = actual_teams - expected_teams
        
        self.stats['expected_teams'] = len(expected_teams)
        self.stats['missing_teams'] = len(missing_teams)
        self.stats['extra_teams'] = len(extra_teams)
        
        if missing_teams:
            print(f"⚠️  {len(missing_teams)} teams missing from output:")
            for team in sorted(missing_teams):
                print(f"  - {team}")
            self.issues['missing_teams'] = sorted(missing_teams)
            reports_dir = os.path.join("validation", "reports")
            os.makedirs(reports_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            missing_path = os.path.join(reports_dir, f"missing_teams_{timestamp}.txt")
            with open(missing_path, "w") as f:
                f.write(f"# Missing teams ({len(missing_teams)})\n\n")
                for team in sorted(missing_teams):
                    f.write(team + "\n")
            print(f"Missing teams list written to {missing_path}")
        else:
            print("✓ All expected teams present")
        
        if extra_teams:
            print(f"⚠️  {len(extra_teams)} unexpected teams in output:")
            for team in sorted(extra_teams):
                print(f"  - {team}")
    
    def generate_report(self):
        """Generate comprehensive validation report."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"validation/reports/validation_report_{timestamp}.md"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w') as f:
            f.write("# Data Validation Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary statistics
            f.write("## Summary Statistics\n\n")
            f.write(f"- Total rows: {self.stats['total_rows']}\n")
            f.write(f"- Total teams: {self.stats['total_teams']}\n")
            f.write(f"- Expected teams: {self.stats.get('expected_teams', 'N/A')}\n")
            f.write(f"- Missing teams: {self.stats.get('missing_teams', 0)}\n\n")
            
            # Data quality issues
            f.write("## Data Quality Issues\n\n")
            f.write(f"- Missing positions: {self.stats['missing_position']}\n")
            f.write(f"- Invalid positions: {self.stats['invalid_positions']}\n")
            f.write(f"- Failed position normalization: {self.stats.get('failed_position_normalization', 0)}\n")
            f.write(f"- Missing heights: {self.stats['missing_height']}\n")
            f.write(f"- Invalid heights: {self.stats['invalid_height_format']}\n")
            f.write(f"- Failed height normalization: {self.stats.get('failed_height_normalization', 0)}\n")
            f.write(f"- Missing classes: {self.stats['missing_class']}\n")
            f.write(f"- Invalid classes: {self.stats['invalid_class']}\n")
            f.write(f"- Failed class normalization: {self.stats.get('failed_class_normalization', 0)}\n")
            f.write(f"- Suspected non-players: {self.stats['suspected_non_players']}\n")
            f.write(f"- Duplicate players: {self.stats['duplicate_players']}\n")
            f.write(f"- Teams with issues: {self.stats['teams_with_issues']}\n")
            f.write(f"- Teams missing stats: {self.stats.get('teams_missing_stats', 0)}\n")
            f.write(f"- Teams missing digs: {self.stats.get('teams_missing_digs', 0)}\n\n")

            if self.issues.get('missing_position_players'):
                f.write("## Players Missing Positions\n\n")
                missing_players = self.issues['missing_position_players']
                max_list = 150
                for item in missing_players[:max_list]:
                    pos_raw = item.get('Position Raw', '')
                    extra = f" (raw: {pos_raw})" if pos_raw else ""
                    f.write(f"- **{item['Team']}**: {item['Name']}{extra}\n")
                if len(missing_players) > max_list:
                    f.write(f"- ... and {len(missing_players) - max_list} more\n")
                f.write("\n")

            if self.issues.get('missing_class_players'):
                f.write("## Players Missing Classes\n\n")
                missing_players = self.issues['missing_class_players']
                max_list = 150
                for item in missing_players[:max_list]:
                    cls_raw = item.get('Class Raw', '')
                    extra = f" (raw: {cls_raw})" if cls_raw else ""
                    f.write(f"- **{item['Team']}**: {item['Name']}{extra}\n")
                if len(missing_players) > max_list:
                    f.write(f"- ... and {len(missing_players) - max_list} more\n")
                f.write("\n")

            if self.issues.get('missing_height_players'):
                f.write("## Players Missing Heights\n\n")
                missing_players = self.issues['missing_height_players']
                max_list = 150
                for item in missing_players[:max_list]:
                    f.write(f"- **{item['Team']}**: {item['Name']}\n")
                if len(missing_players) > max_list:
                    f.write(f"- ... and {len(missing_players) - max_list} more\n")
                f.write("\n")
            
            # Detailed issues
            if self.issues.get('failed_position_normalization'):
                f.write("## Failed Position Normalization\n\n")
                f.write("Players with raw position data that failed to normalize:\n\n")
                from collections import defaultdict
                by_raw = defaultdict(list)
                for item in self.issues['failed_position_normalization'][:100]:
                    by_raw[item['position_raw']].append(f"{item['team']}: {item['name']}")
                
                for raw_pos in sorted(by_raw.keys())[:30]:
                    examples = by_raw[raw_pos][:5]
                    f.write(f"### Raw value: `{raw_pos}` ({len(by_raw[raw_pos])} occurrences)\n\n")
                    for example in examples:
                        f.write(f"- {example}\n")
                    if len(by_raw[raw_pos]) > 5:
                        f.write(f"- ... and {len(by_raw[raw_pos]) - 5} more\n")
                    f.write("\n")
            
            if self.issues.get('failed_height_normalization'):
                f.write("## Failed Height Normalization\n\n")
                f.write("Players with raw height data that failed to normalize:\n\n")
                from collections import defaultdict
                by_raw = defaultdict(list)
                for item in self.issues['failed_height_normalization'][:100]:
                    by_raw[item['height_raw']].append(f"{item['team']}: {item['name']}")
                
                for raw_height in sorted(by_raw.keys())[:30]:
                    examples = by_raw[raw_height][:5]
                    f.write(f"### Raw value: `{raw_height}` ({len(by_raw[raw_height])} occurrences)\n\n")
                    for example in examples:
                        f.write(f"- {example}\n")
                    if len(by_raw[raw_height]) > 5:
                        f.write(f"- ... and {len(by_raw[raw_height]) - 5} more\n")
                    f.write("\n")
            
            if self.issues.get('failed_class_normalization'):
                f.write("## Failed Class Normalization\n\n")
                f.write("Players with raw class data that failed to normalize:\n\n")
                # Group by raw class value
                from collections import defaultdict
                by_raw = defaultdict(list)
                for item in self.issues['failed_class_normalization'][:100]:
                    by_raw[item['class_raw']].append(f"{item['team']}: {item['name']}")
                
                for raw_class in sorted(by_raw.keys())[:30]:
                    examples = by_raw[raw_class][:5]
                    f.write(f"### Raw value: `{raw_class}` ({len(by_raw[raw_class])} occurrences)\n\n")
                    for example in examples:
                        f.write(f"- {example}\n")
                    if len(by_raw[raw_class]) > 5:
                        f.write(f"- ... and {len(by_raw[raw_class]) - 5} more\n")
                    f.write("\n")
            
            if self.issues.get('non_players'):
                f.write("## Suspected Non-Players\n\n")
                for item in self.issues['non_players'][:50]:
                    f.write(f"- **{item['team']}**: {item['name']} (keyword: {item['keyword']})\n")
                    f.write(f"  - Position raw: {item['position_raw']}\n")
                    f.write(f"  - Class raw: {item['class_raw']}\n")
                f.write("\n")
            
            if self.issues.get('duplicates'):
                f.write("## Duplicate Players\n\n")
                for item in self.issues['duplicates']:
                    f.write(f"- **{item['team']}**: {item['name']} ({item['count']}x)\n")
                f.write("\n")
            
            if self.issues.get('team_quality'):
                f.write("## Teams with Data Quality Issues\n\n")
                for team_data in sorted(self.issues['team_quality'], 
                                       key=lambda x: len(x['issues']), reverse=True)[:30]:
                    f.write(f"### {team_data['team']} ({team_data['roster_size']} players)\n\n")
                    for issue in team_data['issues']:
                        f.write(f"- {issue}\n")
                    f.write("\n")
            
            if self.issues.get('missing_teams'):
                f.write("## Missing Teams\n\n")
                missing_list = self.issues['missing_teams']
                for team in missing_list:
                    f.write(f"- {team}\n")
                f.write(f"\nTotal missing teams listed: {len(missing_list)}\n")
                f.write("\n")

            if self.issues.get('teams_missing_stats'):
                f.write("## Teams With No Stats\n\n")
                for team in self.issues['teams_missing_stats']:
                    f.write(f"- {team}\n")
                f.write(f"\nTotal teams with no stats: {self.stats.get('teams_missing_stats', 0)}\n\n")

            if self.issues.get('teams_missing_digs'):
                f.write("## Teams Missing Digs (Defensive Stats)\n\n")
                for team in self.issues['teams_missing_digs']:
                    f.write(f"- {team}\n")
                f.write(f"\nTotal teams missing digs: {self.stats.get('teams_missing_digs', 0)}\n\n")
            
            if self.issues.get('teams_with_scrape_errors'):
                f.write("## Teams with Scraping Errors\n\n")
                for team in self.issues['teams_with_scrape_errors'][:50]:
                    f.write(f"- {team}\n")
                f.write("\n")
        
        print(f"\n✓ Validation report written to: {report_path}")
        return report_path
    
    def export_problem_teams(self):
        """Export list of teams that need fixing."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Teams with issues
        problem_teams = set()
        for team, issues in self.team_issues.items():
            if issues:
                problem_teams.add(team)
        
        # Add teams with scraping errors
        if self.issues.get('teams_with_scrape_errors'):
            problem_teams.update(self.issues['teams_with_scrape_errors'])
        
        # Add missing teams
        if self.issues.get('missing_teams'):
            problem_teams.update(self.issues['missing_teams'])
        
        reports_dir = os.path.join("validation", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        output_path = os.path.join(reports_dir, f"problem_teams_{timestamp}.txt")
        with open(output_path, 'w') as f:
            f.write("# Teams that need attention\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(problem_teams)} teams\n\n")
            
            for team in sorted(problem_teams):
                f.write(f"{team}\n")
                if team in self.team_issues:
                    for issue in self.team_issues[team]:
                        f.write(f"  # {issue}\n")
        
        print(f"✓ Problem teams list written to: {output_path}")
        return output_path, len(problem_teams)
    
    def run_full_validation(self):
        """Run all validation checks."""
        print("=" * 70)
        print("D1 VOLLEYBALL ROSTER DATA VALIDATION")
        print("=" * 70)
        
        self.load_data()
        self.validate_positions()
        self.validate_heights()
        self.validate_classes()
        self.detect_non_players()
        self.check_duplicates()
        self.validate_team_data()
        self.check_stats_completeness()
        self.check_missing_teams()
        self.analyze_log_file()
        
        print("\n" + "=" * 70)
        print("GENERATING REPORTS")
        print("=" * 70)
        
        report_path = self.generate_report()
        problem_teams_path, problem_count = self.export_problem_teams()
        
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Total players: {self.stats['total_rows']}")
        print(f"Total teams: {self.stats['total_teams']}")
        print(f"Teams with issues: {problem_count}")
        print(f"\nData completeness:")
        print(f"  Positions: {(1 - self.stats['missing_position']/self.stats['total_rows'])*100:.1f}%")
        print(f"  Heights: {(1 - self.stats['missing_height']/self.stats['total_rows'])*100:.1f}%")
        print(f"  Classes: {(1 - self.stats['missing_class']/self.stats['total_rows'])*100:.1f}%")
        print(f"\nNormalization failures:")
        print(f"  Position: {self.stats.get('failed_position_normalization', 0)}")
        print(f"  Height: {self.stats.get('failed_height_normalization', 0)}")
        print(f"  Class: {self.stats.get('failed_class_normalization', 0)}")
        print(f"\nOther issues:")
        print(f"  Non-players: {self.stats['suspected_non_players']}")
        print(f"  Duplicates: {self.stats['duplicate_players']}")
        print(f"  Invalid positions: {self.stats['invalid_positions']}")
        print(f"  Invalid heights: {self.stats['invalid_height_format']}")
        print(f"  Invalid classes: {self.stats['invalid_class']}")
        
        return report_path, problem_teams_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate roster data output.")
    parser.add_argument(
        "-f",
        "--file",
        "--csv",
        dest="csv_path",
        default="exports/rosters_and_stats.csv",
        help="Path to roster CSV to validate (default: exports/rosters_and_stats.csv)",
    )
    parser.add_argument(
        "--log",
        dest="log_path",
        default="exports/scraper.log",
        help="Path to scraper log file (default: exports/scraper.log)",
    )
    args = parser.parse_args()

    validator = DataValidator(args.csv_path, args.log_path)
    validator.run_full_validation()
