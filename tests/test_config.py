"""Tests for agentdrive.config and constants (isolated home)"""

from agentdrive.config import (
    get_config_value,
    get_instance_name,
    load_config,
    set_config_value,
    set_instance_name,
)
from agentdrive.constants import get_agentdrive_home, get_agentdrive_instance_name


def test_home_is_isolated(isolated_agentdrive_home):
    home = get_agentdrive_home()
    assert str(home) == str(isolated_agentdrive_home)
    assert home.exists()


def test_default_config():
    cfg = load_config()
    assert cfg["agentdrive"]["log_level"] in ("INFO", "DEBUG")
    assert "orchestrator" in cfg


def test_config_roundtrip_and_get_set():
    # set a value
    set_config_value("tui.skin", "dark")
    val = get_config_value("tui.skin")
    assert val == "dark"

    # reload fresh
    cfg = load_config(force_reload=True)
    assert cfg["tui"]["skin"] == "dark"


def test_instance_name_respects_env_on_first_run(isolated_agentdrive_home):
    """AGENTDRIVE_INSTANCE_NAME must be honored even before any config.yaml or onboarding."""
    import os

    # Fresh home from fixture has no config yet in practice for this test
    original = os.environ.get("AGENTDRIVE_INSTANCE_NAME")
    try:
        os.environ["AGENTDRIVE_INSTANCE_NAME"] = "My Fresh Drive"
        # get_instance_name falls back to live env when no config value
        name = get_instance_name()
        assert name == "My Fresh Drive"
        # The live getter also
        assert get_agentdrive_instance_name() == "My Fresh Drive"
    finally:
        if original is None:
            os.environ.pop("AGENTDRIVE_INSTANCE_NAME", None)
        else:
            os.environ["AGENTDRIVE_INSTANCE_NAME"] = original


def test_set_instance_name_updates_live_name_and_module(isolated_agentdrive_home):
    """After set_instance_name, both get_instance_name and direct const import see update (first-run naming flow)."""
    import os
    import sys

    original = os.environ.get("AGENTDRIVE_INSTANCE_NAME")
    try:
        os.environ.pop("AGENTDRIVE_INSTANCE_NAME", None)  # start clean
        set_instance_name("Test First Run Instance")
        assert get_instance_name() == "Test First Run Instance"
        # Live getter
        assert get_agentdrive_instance_name() == "Test First Run Instance"
        # The module attr was synced so from-import gets it
        from agentdrive.constants import AGENTDRIVE_INSTANCE_NAME as NAME

        assert NAME == "Test First Run Instance"
        # And the module attr itself
        mod = sys.modules["agentdrive.constants"]
        assert getattr(mod, "AGENTDRIVE_INSTANCE_NAME") == "Test First Run Instance"
    finally:
        if original is None:
            os.environ.pop("AGENTDRIVE_INSTANCE_NAME", None)
        else:
            os.environ["AGENTDRIVE_INSTANCE_NAME"] = original
