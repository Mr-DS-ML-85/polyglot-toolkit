"""
Central configuration — loads config.yaml, provides sensible defaults
optimized for Ryzen 7 7700 + RTX 4060 + 32 GB RAM.
"""

import os, yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

_DEFAULTS = {
    "model": {
        "path": "models/polyglot_shield.cbm",
        "task_type": "GPU",
        "iterations": 1200,
        "learning_rate": 0.04,
        "depth": 8,
        "l2_leaf_reg": 5,
        "border_count": 254,
        "random_seed": 42,
        "eval_metric": "Logloss",
        "early_stopping_rounds": 80,
        "verbose": 0,
        "class_weights": [1.0, 3.0],
        "gpu_ram_fraction": 0.7,
    },
    "features": {
        "max_file_size_mb": 100,
        "chunk_count": 16,
        "string_min_len": 4,
    },
    "yara": {
        "rules_dir": "rules",
        "auto_generate": True,
    },
    "monitor": {
        "watch_dirs": [os.path.expanduser("~/Downloads")],
        "recursive": True,
        "scan_delay_sec": 1.5,
        "max_workers": 4,
    },
    "quarantine": {
        "dir": "quarantine",
        "encrypt_names": True,
        "max_size_mb": 500,
        "retain_days": 30,
    },
    "notifications": {
        "enabled": True,
        "sound": True,
        "critical_only": False,
        "popup_duration_sec": 8,
    },
    "logging": {
        "level": "INFO",
        "file": "logs/polyglot_shield.log",
        "max_bytes": 10_000_000,
        "backup_count": 5,
    },
    "thresholds": {
        "detect": 0.65,
        "quarantine": 0.80,
        "alert": 0.50,
    },
    "gui": {
        "theme": "dark",
        "font_family": "Segoe UI",
        "font_size": 10,
        "window_width": 1280,
        "window_height": 800,
    },
}


@dataclass
class Config:
    model: dict = field(default_factory=lambda: dict(_DEFAULTS["model"]))
    features: dict = field(default_factory=lambda: dict(_DEFAULTS["features"]))
    yara: dict = field(default_factory=lambda: dict(_DEFAULTS["yara"]))
    monitor: dict = field(default_factory=lambda: dict(_DEFAULTS["monitor"]))
    quarantine: dict = field(default_factory=lambda: dict(_DEFAULTS["quarantine"]))
    notifications: dict = field(default_factory=lambda: dict(_DEFAULTS["notifications"]))
    logging: dict = field(default_factory=lambda: dict(_DEFAULTS["logging"]))
    thresholds: dict = field(default_factory=lambda: dict(_DEFAULTS["thresholds"]))
    gui: dict = field(default_factory=lambda: dict(_DEFAULTS["gui"]))

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        cfg = cls()
        if path and Path(path).exists():
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
            for key in _DEFAULTS:
                if key in raw and isinstance(raw[key], dict):
                    merged = {**_DEFAULTS[key], **raw[key]}
                    setattr(cfg, key, merged)
        return cfg

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {k: getattr(self, k) for k in _DEFAULTS}
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @staticmethod
    def create_default(path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(_DEFAULTS, f, default_flow_style=False, sort_keys=False)
