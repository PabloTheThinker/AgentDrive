"""Tests for savant.config and constants (isolated home)"""

from savant.config import load_config, get_config_value, save_config, set_config_value
from savant.constants import get_savant_home


def test_home_is_isolated(isolated_savant_home):
    home = get_savant_home()
    assert str(home) == str(isolated_savant_home)
    assert home.exists()


def test_default_config():
    cfg = load_config()
    assert cfg["savant"]["log_level"] in ("INFO", "DEBUG")
    assert "orchestrator" in cfg


def test_config_roundtrip_and_get_set():
    # set a value
    set_config_value("tui.skin", "dark")
    val = get_config_value("tui.skin")
    assert val == "dark"

    # reload fresh
    cfg = load_config(force_reload=True)
    assert cfg["tui"]["skin"] == "dark"
