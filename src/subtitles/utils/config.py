#!/usr/bin/env python3
"""Configuration management for subtitle generation tools.

Supports optional YAML configuration file with sensible defaults.
Config file location: config.yaml in the script directory.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None


# DEFAULT CONFIGURATION - Used when no config file is present
DEFAULT_CONFIG: Dict[str, Any] = {
    "video": {
        "formats": [
            "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "mpg", "mpeg"
        ]
    },
    "translation": {
        "max_batch_characters": 5000,
        "batch_size_subtitles": 50,
        "source_language": "en",
        "target_language": "es",
        "delimiter": "\n|||SUBTITLE_DELIMITER|||\n",
        "parallel_workers": 2
    },
    "detection": {
        "english_keywords": [
            " the ", " and ", " to ", " of ", " in ",
            " is ", " are ", " was ", " were ", " that ", " this ", " with "
        ],
        "language_codes": {
            "english": ["eng", "en", "english"],
            "spanish": ["spa", "es", "spanish"]
        }
    }
}

LANGUAGE_CODE_MAP = {
    'es': ['es', 'spa'],
    'en': ['en', 'eng'],
    'fr': ['fr', 'fra'],
    'de': ['de', 'deu'],
    'it': ['it', 'ita'],
    'pt': ['pt', 'por'],
    'ru': ['ru', 'rus'],
    'zh': ['zh', 'zho', 'chi'],
    'ja': ['ja', 'jpn'],
    'ko': ['ko', 'kor'],
    'ar': ['ar', 'ara'],
    'hi': ['hi', 'hin'],
    'nl': ['nl', 'nld'],
    'pl': ['pl', 'pol'],
    'tr': ['tr', 'tur']
}


class Config:
    """Configuration loader with YAML support and defaults."""

    def __init__(self, config_file: Optional[str | Path] = None):
        """Initialize configuration.

        Args:
            config_file: Optional path to YAML config file. If not provided,
                        searches for 'config.yaml' in current directory.
        """
        self.config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self.config_file: Optional[Path] = None

        if config_file:
            self.config_file = Path(config_file)
        else:
            # Auto-detect config.yaml in current directory
            default_location = Path("config.yaml")
            if default_location.exists():
                self.config_file = default_location

        if self.config_file and self.config_file.exists():
            self._load_yaml()

    def _load_yaml(self) -> None:
        """Load and merge YAML config file with defaults."""
        if yaml is None:
            print(f"⚠️  Warning: PyYAML not installed, ignoring config file")
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f) or {}

            # Deep merge config file over defaults
            self._deep_merge(self.config, file_config)
        except Exception as e:
            print(f"⚠️  Warning: Failed to load config {self.config_file}: {e}")

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> None:
        """Deep merge override dict into base dict (modifies base in-place)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path like 'translation.max_batch_characters'
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default

    # Convenience accessors
    @property
    def video_formats(self) -> list:
        return [f".{fmt}" if not fmt.startswith('.') else fmt
                for fmt in self.get("video.formats", DEFAULT_CONFIG["video"]["formats"])]

    @property
    def max_batch_chars(self) -> int:
        return self.get("translation.max_batch_characters", 5000)

    @property
    def batch_size(self) -> int:
        return self.get("translation.batch_size_subtitles", 50)

    @property
    def parallel_workers(self) -> int:
        """Number of parallel workers for batch translation (default 2, max recommended 3)."""
        workers = self.get("translation.parallel_workers", 2)
        # Ensure within reasonable bounds
        return max(1, min(workers, 4))

    @property
    def use_emoji(self) -> bool:
        return self.get("output.use_emoji", True)

    @property
    def log_file(self) -> Optional[str]:
        return self.get("output.log_file")

    @property
    def verbose(self) -> bool:
        return self.get("output.verbose", False)

    @property
    def english_keywords(self) -> list:
        return self.get("detection.english_keywords", DEFAULT_CONFIG["detection"]["english_keywords"])

    @property
    def english_codes(self) -> list:
        return self.get("detection.language_codes.english", ["eng", "en", "english"])

    @property
    def spanish_codes(self) -> list:
        return self.get("detection.language_codes.spanish", ["spa", "es", "spanish"])


# Global config instance
_global_config: Optional[Config] = None


def load_config(config_file: Optional[str | Path] = None) -> Config:
    """Load or reload global configuration.

    Args:
        config_file: Optional path to config YAML file

    Returns:
        Global Config instance
    """
    global _global_config
    _global_config = Config(config_file)
    return _global_config


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        Global Config instance (initializes with defaults if not loaded)
    """
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config
