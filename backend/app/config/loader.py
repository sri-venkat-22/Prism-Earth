"""Configuration-driven loader for ``configs/*.yaml`` (SRS §10, §11.8, §13.23).

Per the Configuration-Driven Design principle (SRS §11.2), no region- or
dataset-specific values are hardcoded. This module reads the YAML config files
(``india.yaml``, ``telangana.yaml``, ``datasets.yaml``) and exposes them as
plain dictionaries. Phase 0 ships stub configs; later phases populate them.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConfigError(RuntimeError):
    """Raised when a required configuration file is missing or invalid."""


def _config_dir() -> Path:
    return get_settings().config_dir


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping: {path}")
    return data


def load_region_config(name: str) -> dict[str, Any]:
    """Load a region config by name, e.g. ``"india"`` or ``"telangana"``."""
    return _read_yaml(_config_dir() / f"{name}.yaml")


def load_datasets_config() -> dict[str, Any]:
    """Load ``datasets.yaml``."""
    return _read_yaml(_config_dir() / "datasets.yaml")


@lru_cache(maxsize=1)
def load_all_configs() -> dict[str, Any]:
    """Load and cache all known config files."""
    configs = {
        "india": load_region_config("india"),
        "telangana": load_region_config("telangana"),
        "datasets": load_datasets_config(),
    }
    logger.info("config.loaded", files=sorted(configs.keys()))
    return configs
