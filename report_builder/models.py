from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Any, Dict


@dataclass
class GuideConfig:
    """Paths and options for building the Ultimate Guide PDF."""

    team_pivot_csv: Path
    rosters_stats_csv: Path
    logos_dir: Path
    output_pdf: Path
    us_map_image: Path
    coaches_cache_path: Path
    player_settings_path: Optional[Path] = None

    @classmethod
    def default(cls, root: Path | None = None) -> "GuideConfig":
        root = Path(root) if root else Path(__file__).resolve().parent.parent
        return cls(
            team_pivot_csv=root / "exports" / "team_pivot.csv",
            rosters_stats_csv=root / "exports" / "rosters_and_stats.csv",
            logos_dir=root / "report_builder" / "logos",
            output_pdf=root / "report_builder" / "exports" / "Ultimate_School_Guide_FULL_LOCAL.pdf",
            us_map_image=root / "report_builder" / "assets" / "us_map_blank.png",
            coaches_cache_path=root / "settings" / "coaches_cache.json",
            player_settings_path=root / "report_builder" / "config" / "players" / "molly_beatty.yml",
        )


@dataclass
class PlayerSettings:
    """Per-player configuration for the guide."""

    name: str
    height: Optional[str] = None
    handedness: Optional[str] = None
    position: Optional[str] = None
    home_city: Optional[str] = None
    home_state: Optional[str] = None
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    schools: List[str] = None
    risk_watchouts: Dict[str, str] = None
    airport_info: Dict[str, Dict[str, str]] = None
    politics_label_overrides: Dict[str, str] = None
    team_name_aliases: Dict[str, str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerSettings":
        player = data.get("player", {})
        schools = data.get("schools", [])
        overrides = data.get("overrides", {}) or {}
        return cls(
            name=player.get("name", "Player"),
            height=player.get("height"),
            handedness=player.get("handedness"),
            position=player.get("position"),
            home_city=player.get("home_city"),
            home_state=player.get("home_state"),
            home_lat=player.get("home_lat"),
            home_lon=player.get("home_lon"),
            schools=schools or [],
            risk_watchouts=overrides.get("risk_watchouts", {}),
            airport_info=overrides.get("airport_info", {}),
            politics_label_overrides=overrides.get("politics_label_overrides", {}),
            team_name_aliases=overrides.get("team_name_aliases", {}),
        )
