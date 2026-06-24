"""Tests for the [ui] config section and UIConfig defaults."""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from oraculovision.config import AppConfig, UIConfig, load_config


class TestUIConfigDefaults:
    def test_default_mode_is_pro(self):
        cfg = UIConfig()
        assert cfg.mode == "pro"

    def test_default_theme_is_oracle(self):
        cfg = UIConfig()
        assert cfg.theme == "oracle"

    def test_default_transitions_true(self):
        cfg = UIConfig()
        assert cfg.screen_transitions is True

    def test_default_splash_true(self):
        cfg = UIConfig()
        assert cfg.splash is True

    def test_default_tooltips_true(self):
        cfg = UIConfig()
        assert cfg.tooltips is True

    def test_default_sparkline_samples(self):
        cfg = UIConfig()
        assert cfg.sparkline_samples == 60


class TestAppConfigHasUI:
    def test_app_config_has_ui_field(self):
        cfg = AppConfig()
        assert hasattr(cfg, "ui")
        assert isinstance(cfg.ui, UIConfig)


class TestLoadConfigUISection:
    def _load_with_toml(self, toml_str: str) -> AppConfig:
        data = tomllib.loads(toml_str)
        with patch("oraculovision.config._config_paths") as mock_paths:
            tmp = Path("/tmp/_test_config_ui.toml")
            tmp.write_text(toml_str)
            mock_paths.return_value = [tmp]
            try:
                return load_config()
            finally:
                tmp.unlink(missing_ok=True)

    def test_load_lite_mode(self):
        cfg = self._load_with_toml('[ui]\nmode = "lite"\n')
        assert cfg.ui.mode == "lite"

    def test_load_stream_theme(self):
        cfg = self._load_with_toml('[ui]\ntheme = "stream"\n')
        assert cfg.ui.theme == "stream"

    def test_load_transitions_false(self):
        cfg = self._load_with_toml('[ui]\nscreen_transitions = false\n')
        assert cfg.ui.screen_transitions is False

    def test_invalid_mode_falls_back_to_pro(self):
        cfg = self._load_with_toml('[ui]\nmode = "banana"\n')
        assert cfg.ui.mode == "pro"

    def test_invalid_theme_falls_back_to_oracle(self):
        cfg = self._load_with_toml('[ui]\ntheme = "neon"\n')
        assert cfg.ui.theme == "oracle"

    def test_sparkline_samples_clamped(self):
        cfg = self._load_with_toml('[ui]\nsparkline_samples = 5\n')
        assert cfg.ui.sparkline_samples == 10  # clamped to min 10

    def test_no_ui_section_keeps_defaults(self):
        cfg = self._load_with_toml("[refresh]\ninterval_seconds = 30\n")
        assert cfg.ui.mode == "pro"
        assert cfg.ui.theme == "oracle"
        assert cfg.ui.screen_transitions is True

    def test_all_ui_keys(self):
        toml = (
            "[ui]\n"
            'mode = "lite"\n'
            'theme = "stream"\n'
            "screen_transitions = false\n"
            "splash = false\n"
            "tooltips = false\n"
            "sparkline_samples = 30\n"
        )
        cfg = self._load_with_toml(toml)
        assert cfg.ui.mode == "lite"
        assert cfg.ui.theme == "stream"
        assert cfg.ui.screen_transitions is False
        assert cfg.ui.splash is False
        assert cfg.ui.tooltips is False
        assert cfg.ui.sparkline_samples == 30
