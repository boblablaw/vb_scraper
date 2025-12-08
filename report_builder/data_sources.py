from __future__ import annotations

import json
try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None
from pathlib import Path
import re
from typing import Any, Dict
from .models import PlayerSettings

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "guide.yml"
DEFAULTS_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "guide.defaults.yml"
TEAMS_JSON_PATH = Path(__file__).resolve().parents[1] / "settings" / "teams.json"


def load_yaml_config(path: Path | None = None) -> Dict[str, Any]:
    """
    Load a single guide YAML config. Returns empty dict if file is missing
    or PyYAML is unavailable.
    """
    if yaml is None:
        return {}
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def merge_overrides(target: dict, override: dict):
    """
    Shallow merge of override dict into target; modifies target in place.
    """
    if not override:
        return
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            target[k].update(v)
        else:
            target[k] = v


def apply_path_overrides(module, cfg: Dict[str, Any]):
    paths = cfg.get("paths") or {}
    for key, attr in [
        ("team_pivot_csv", "TEAM_PIVOT_CSV"),
        ("rosters_stats_csv", "ROSTERS_STATS_CSV"),
        ("logos_dir", "LOGOS_DIR"),
        ("output_pdf", "OUTPUT_PDF"),
        ("us_map_image", "US_MAP_IMAGE"),
        ("coaches_cache_path", "COACHES_CACHE_PATH"),
        ("player_settings_path", "PLAYER_SETTINGS_PATH"),
    ]:
        if key in paths and getattr(module, attr, None) is not None:
            # Respect caller-provided overrides:
            # - Don't override output_pdf if caller set OUTPUT_PDF_WAS_OVERRIDDEN
            if attr == "OUTPUT_PDF" and getattr(module, "OUTPUT_PDF_WAS_OVERRIDDEN", False):
                continue
            # - Don't override player_settings_path if caller already set it
            if attr == "PLAYER_SETTINGS_PATH" and getattr(module, attr, None):
                continue
            setattr(module, attr, module.ROOT_DIR / paths[key])
    # Keep PNG_DIR aligned with logos_dir
    if getattr(module, "LOGOS_DIR", None) is not None:
        module.PNG_DIR = module.LOGOS_DIR


def apply_data_overrides(module, cfg: Dict[str, Any]):
    merge_overrides(module.TEAM_NAME_ALIASES, cfg.get("team_name_aliases", {}))
    merge_overrides(module.POLITICS_LABEL_OVERRIDES, cfg.get("politics_label_overrides", {}))
    merge_overrides(module.COACH_OVERRIDES, cfg.get("coach_overrides", {}))
    merge_overrides(module.AIRPORT_INFO, cfg.get("airport_info", {}))
    merge_overrides(module.RISK_WATCHOUTS, cfg.get("risk_watchouts", {}))
    merge_overrides(module.LOGO_MAP, cfg.get("logo_map", {}))


def load_and_apply_config(module, path: Path | None = None):
    """
    Load defaults + overrides, then apply to the provided module.
    - Defaults live in guide.defaults.yml
    - User/project overrides live in guide.yml (or a custom `path`)
    """
    merged_cfg: Dict[str, Any] = {}
    # 1) Load baked-in defaults
    merge_overrides(merged_cfg, load_yaml_config(DEFAULTS_CONFIG_PATH))
    # 2) Apply user overrides (if present)
    merge_overrides(merged_cfg, load_yaml_config(path))

    apply_path_overrides(module, merged_cfg)
    apply_data_overrides(module, merged_cfg)
    return merged_cfg


# ---------------- Player settings ----------------

def load_player_settings(path: Path | None) -> PlayerSettings:
    """
    Load per-player settings from YAML. Returns defaults if missing.
    """
    if path is None or not path.exists() or yaml is None:
        return PlayerSettings.from_dict({})
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return PlayerSettings.from_dict(data)


__all__ = [
    "load_yaml_config",
    "apply_path_overrides",
    "apply_data_overrides",
    "load_and_apply_config",
    "DEFAULT_CONFIG_PATH",
    "DEFAULTS_CONFIG_PATH",
    "load_player_settings",
    "merge_overrides",
    "load_schools_data",
    "load_niche_data",
]


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _slugify(name: str) -> str:
    name = name.lower()
    name = name.replace("&", " and ")
    name = re.sub(r"[^a-z0-9\\s-]", " ", name)
    name = re.sub(r"\\s+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def load_schools_data(path: Path | None = None):
    """
    Load school metadata from the consolidated settings/teams.json.
    Backwards compatible with prior schools.json shape by projecting
    the needed fields.
    """
    data = _load_json(path or TEAMS_JSON_PATH) or []
    schools: list[dict] = []
    for entry in data:
        name = entry.get("team")
        if not name:
            continue
        schools.append(
            {
                "name": name,
                "short": entry.get("short_name") or entry.get("short") or name,
                "city_state": entry.get("city_state", ""),
                "conference": entry.get("conference", ""),
                "tier": entry.get("tier", ""),
                "offense_type": "",  # will be filled from team_pivot CSV
                "lat": entry.get("lat"),
                "lon": entry.get("lon"),
                "notes": entry.get("notes", ""),
                "map_x": entry.get("map_x"),
                "map_y": entry.get("map_y"),
                "airport_name": entry.get("airport_name", ""),
                "airport_code": entry.get("airport_code", ""),
                "airport_drive_time": entry.get("airport_drive_time", ""),
                "airport_notes": entry.get("airport_notes", ""),
                "political_label": entry.get("political_label", ""),
                "ncaa_logo_light": entry.get("ncaa_logo_light", ""),
                "team_name_aliases": entry.get("team_name_aliases", []),
                "niche_data_slug": entry.get("niche_data_slug") or _slugify(name),
                "niche": entry.get("niche", {}),
                "risk_watchouts": entry.get("risk_watchouts", ""),
            }
        )
    return schools


def load_niche_data(path: Path | None = None):
    """
    Niche data now lives inside teams.json under each team's 'niche' field.
    """
    data = _load_json(path or TEAMS_JSON_PATH) or []
    niche: dict[str, dict] = {}
    for entry in data:
        name = entry.get("team")
        if name and entry.get("niche"):
            niche[name] = entry["niche"]
    return niche
