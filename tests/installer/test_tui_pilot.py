"""Headless Textual pilot: GUI-ordered wizard through InstallEngine stubs."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "skorionos/airootfs/usr/local/lib"
sys.path.insert(0, str(LIB))

pytest.importorskip("textual")


@pytest.fixture(autouse=True)
def _clear_sim_product_flags(monkeypatch):
    for key in (
        "INSTALLER_SIM_FRZR",
        "INSTALLER_SIM_MODE",
        "INSTALLER_SIM_ADVANCED",
        "INSTALLER_SIM_AUTO",
        "INSTALLER_SIM_DISK_GATE",
        "INSTALLER_SIM_DUAL",
        "INSTALLER_WINDOW_SHOT",
        "INSTALLER_PAGE_MARKER",
    ):
        monkeypatch.delenv(key, raising=False)


async def _activate(pilot, app, widget_id: str) -> None:
    """Click if on-screen; otherwise focus + Enter (tall pages)."""
    try:
        await pilot.click(widget_id)
    except Exception:
        app.screen.query_one(widget_id).focus()
        await pilot.press("enter")
    await pilot.pause()


def test_tui_wizard_runs_stubs(tmp_path, monkeypatch):
    boot_rec = tmp_path / "b.json"
    dep_rec = tmp_path / "d.json"
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.delenv("INSTALLER_DRY_RUN", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )
    monkeypatch.setenv("INSTALLER_STUB_RECORD", str(boot_rec))
    monkeypatch.setenv("INSTALLER_STUB_RECORD_DEPLOY", str(dep_rec))
    monkeypatch.setenv("INSTALLER_STUB_SLEEP", "0")
    monkeypatch.setenv("INSTALLER_REQUIRE_STUB", "1")
    monkeypatch.setenv("INSTALLER_LOG_FILE", str(tmp_path / "tui.log"))
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.setenv("INSTALLER_SIM_MODE", "fresh")
    monkeypatch.delenv("INSTALLER_SIM_FRZR", raising=False)
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.delenv("INSTALLER_PAGE_MARKER", raising=False)

    from installer.tui.app import InstallerTui

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 48)) as pilot:
            await _activate(pilot, app, "#start")
            await _activate(pilot, app, "#next")  # network
            await _activate(pilot, app, "#next")  # disk
            await _activate(pilot, app, "#next")  # mode
            await _activate(pilot, app, "#go")  # confirm
            for _ in range(100):
                await pilot.pause(0.05)
                if boot_rec.exists():
                    break
            assert boot_rec.exists(), "bootstrap did not run"
            for _ in range(40):
                await pilot.pause(0.05)
                try:
                    if not app.screen.query_one("#next").disabled:
                        break
                except Exception:
                    pass
            await _activate(pilot, app, "#next")  # after bootstrap
            await _activate(pilot, app, "#next")  # version
            for _ in range(100):
                await pilot.pause(0.05)
                if dep_rec.exists():
                    break
            assert dep_rec.exists(), "deploy did not run"
            for _ in range(40):
                await pilot.pause(0.05)
                try:
                    if not app.screen.query_one("#next").disabled:
                        break
                except Exception:
                    pass
            await _activate(pilot, app, "#next")  # after deploy → complete
            await _activate(pilot, app, "#reboot")

    asyncio.run(_run())

    boot = json.loads(boot_rec.read_text())
    dep = json.loads(dep_rec.read_text())
    assert boot["env"]["FRZR_NONINTERACTIVE"] == "1"
    assert boot["argv"][0] == "gamer"
    assert boot["argv"][2] == "fresh"
    assert dep["argv"][0].startswith("3003n/skorionos:")


def test_tui_gamepad_dpad_no_tab(monkeypatch):
    """Handheld contract: ↑↓←→ + Enter only — never require Tab."""
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.setenv("INSTALLER_SIM_ONLINE", "1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )

    from textual.widgets import Button, OptionList, RadioSet

    from installer.tui.app import InstallerTui, PartitionAdjustScreen

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.3)
            assert app.focused.id == "start"
            await pilot.press("left")
            await pilot.pause(0.05)
            assert app.focused.id == "exit"
            await pilot.press("right")
            await pilot.pause(0.05)
            assert app.focused.id == "start"
            await pilot.press("enter")
            await pilot.pause(0.25)
            # Network: Up from nav reaches WiFi list (no Tab)
            assert app.focused.id == "next"
            await pilot.press("up")
            await pilot.pause(0.1)
            assert isinstance(app.focused, OptionList), app.focused
            # Down past last SSID reaches nav
            await pilot.press("down")
            await pilot.pause(0.05)
            await pilot.press("down")
            await pilot.pause(0.05)
            await pilot.press("down")
            await pilot.pause(0.1)
            assert isinstance(app.focused, Button), app.focused
            app.screen.query_one("#next", Button).focus()
            await pilot.press("enter")
            await pilot.pause(0.3)
            # Disk: ↑↓ select without Tab; Down to nav; Enter continues
            assert isinstance(app.focused, RadioSet)
            rs = app.screen.query_one("#disk_set", RadioSet)
            first = rs.pressed_button.id
            await pilot.press("down")
            await pilot.pause(0.1)
            # single sim disk may wrap; either way RadioSet stays usable
            assert isinstance(app.focused, RadioSet) or isinstance(app.focused, Button)
            # Enter on RadioSet must NOT advance — ↓ to nav then Enter
            app.screen.query_one("#disk_set", RadioSet).focus()
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert type(app.screen).__name__ == "DiskScreen"
            await pilot.press("down")  # may wrap or go nav with 1 disk
            await pilot.pause(0.1)
            if not isinstance(app.focused, Button):
                app.screen.query_one("#next", Button).focus()
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "ModeScreen"
            # Partition adjust: ↑↓ must CHANGE selection (not cursor-only)
            app.push_screen(PartitionAdjustScreen())
            await pilot.pause(0.4)
            rs = app.screen.query_one("#dual_set", RadioSet)
            assert rs.pressed_button.id == "dual_shrink"
            await pilot.press("down")
            await pilot.pause(0.15)
            assert rs.pressed_button.id == "dual_delete", rs.pressed_button.id
            # Next list is size radios (60/100/200), not nav.
            await pilot.press("down")
            await pilot.pause(0.15)
            size_rs = app.screen.query_one("#size_set", RadioSet)
            assert app.screen.query_one("#size_100",).value
            assert isinstance(app.focused, RadioSet) or (
                getattr(app.focused, "id", "").startswith("size_")
            )
            # Down past last size → nav button
            size_rs.focus()
            await pilot.press("down")
            await pilot.pause(0.05)
            await pilot.press("down")
            await pilot.pause(0.05)
            await pilot.press("down")
            await pilot.pause(0.15)
            assert isinstance(app.focused, Button), app.focused
            # Up returns to size radios
            await pilot.press("up")
            await pilot.pause(0.15)
            assert isinstance(app.focused, RadioSet) or (
                getattr(app.focused, "id", "").startswith("size_")
            )

    asyncio.run(_run())


def test_tui_next_works_after_back(monkeypatch):
    """Popping back must clear _armed so 继续 works again."""
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.setenv("INSTALLER_SIM_ONLINE", "1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )

    from textual.widgets import Button

    from installer.tui.app import InstallerTui

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("enter")  # network
            await pilot.pause(0.2)
            app.screen.query_one("#next", Button).focus()
            await pilot.press("enter")  # disk
            await pilot.pause(0.25)
            assert type(app.screen).__name__ == "DiskScreen"
            await pilot.press("escape")
            await pilot.pause(0.25)
            assert type(app.screen).__name__ == "NetworkScreen"
            assert app.screen._armed is False
            app.screen.query_one("#next", Button).focus()
            await pilot.press("enter")
            await pilot.pause(0.25)
            assert type(app.screen).__name__ == "DiskScreen"

    asyncio.run(_run())


def test_tui_wifi_connect_sim(monkeypatch):
    """「连接」must call WifiService (sim) — not a re-ping stub."""
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_WIFI", "1")
    monkeypatch.setenv("INSTALLER_SIM_ONLINE", "0")
    monkeypatch.delenv("INSTALLER_SIM_WIFI_SSID", raising=False)
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )

    import os

    from textual.widgets import OptionList

    from installer.tui.app import InstallerTui

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("enter")  # start → network
            await pilot.pause(0.3)
            assert getattr(app.focused, "id", None) == "next"
            app.screen.query_one("#wifi_list", OptionList).focus()
            await pilot.pause(0.05)
            # First sim AP is open (Skorion-Guest) — Enter connects without password
            await pilot.press("enter")
            for _ in range(40):
                await pilot.pause(0.05)
                if os.environ.get("INSTALLER_SIM_WIFI_SSID") == "Skorion-Guest":
                    break
            assert os.environ.get("INSTALLER_SIM_WIFI_SSID") == "Skorion-Guest"
            assert os.environ.get("INSTALLER_SIM_ONLINE") == "1"
            # Secured AP → password screen, then connect
            app.screen.query_one("#wifi_list", OptionList).focus()
            await pilot.press("down")
            await pilot.pause(0.05)
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert type(app.screen).__name__ == "WifiPasswordScreen"
            await pilot.press(*"lab-pass")
            await pilot.press("enter")
            for _ in range(40):
                await pilot.pause(0.05)
                if os.environ.get("INSTALLER_SIM_WIFI_SSID") == "Skorion-Lab":
                    break
            assert os.environ.get("INSTALLER_SIM_WIFI_SSID") == "Skorion-Lab"

    asyncio.run(_run())


def test_tui_repair_when_existing_frzr(monkeypatch):
    """INSTALLER_SIM_FRZR=complete must offer 修复安装."""
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.setenv("INSTALLER_SIM_FRZR", "complete")
    monkeypatch.setenv("INSTALLER_SIM_ONLINE", "1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )

    from textual.widgets import Button, RadioButton

    from installer.tui.app import InstallerTui

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("enter")
            await pilot.pause(0.2)
            app.screen.query_one("#next", Button).focus()
            await pilot.press("enter")
            await pilot.pause(0.25)
            assert type(app.screen).__name__ == "DiskScreen"
            app.screen.query_one("#next", Button).focus()
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert type(app.screen).__name__ == "ModeScreen"
            assert app.has_existing_installation is True
            repair = app.screen.query_one("#mode_repair", RadioButton)
            assert repair.value is True

    asyncio.run(_run())


def test_tui_advanced_defaults(monkeypatch):
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )

    from textual.widgets import Checkbox

    from installer.tui.app import AdvancedScreen, InstallerTui

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 36)) as pilot:
            app.push_screen(AdvancedScreen())
            await pilot.pause(0.2)
            assert app.screen.query_one("#adv_firmware_overrides", Checkbox).value is False
            assert app.screen.query_one("#adv_cdn", Checkbox).value is False
            assert app.screen.query_one("#adv_fallback_url", Checkbox).value is True
            assert app.screen.query_one("#adv_debug", Checkbox).value is False

    asyncio.run(_run())


def test_tui_advanced_checkbox_opens_page(monkeypatch):
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.setenv("INSTALLER_SIM_ONLINE", "1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )
    monkeypatch.setenv("INSTALLER_STUB_SLEEP", "0")
    monkeypatch.setenv("INSTALLER_REQUIRE_STUB", "1")
    monkeypatch.setenv("INSTALLER_LOG_FILE", "/tmp/tui-adv.log")

    from textual.widgets import Button, Checkbox

    from installer.tui.app import AdvancedScreen, InstallerTui

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 48)) as pilot:
            await _activate(pilot, app, "#start")
            await _activate(pilot, app, "#next")  # network
            await _activate(pilot, app, "#next")  # disk
            await _activate(pilot, app, "#next")  # mode
            await _activate(pilot, app, "#go")  # confirm
            for _ in range(80):
                await pilot.pause(0.05)
                try:
                    if not app.screen.query_one("#next").disabled:
                        break
                except Exception:
                    pass
            await _activate(pilot, app, "#next")  # version
            assert type(app.screen).__name__ == "VersionScreen"
            box = app.screen.query_one("#opt_advanced", Checkbox)
            box.value = True
            await _activate(pilot, app, "#next")
            assert isinstance(app.screen, AdvancedScreen)
            assert app.screen.query_one("#adv_fallback_url", Checkbox).value is True
            await _activate(pilot, app, "#next")
            assert type(app.screen).__name__ == "InstallScreen"

    asyncio.run(_run())


def test_tui_sim_mode_dual_lists_partitions(monkeypatch):
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.setenv("INSTALLER_SIM_MODE", "dual")
    monkeypatch.setenv("INSTALLER_SIM_ONLINE", "1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )

    from textual.widgets import Button, RadioButton

    from installer.tui.app import InstallerTui, PartitionAdjustScreen

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 36)) as pilot:
            await _activate(pilot, app, "#start")
            await _activate(pilot, app, "#next")
            await _activate(pilot, app, "#next")
            assert type(app.screen).__name__ == "ModeScreen"
            await _activate(pilot, app, "#next")
            assert isinstance(app.screen, PartitionAdjustScreen)
            assert app.screen.query_one("#part_0", RadioButton)
            assert app.screen.query_one("#dual_shrink", RadioButton)

    asyncio.run(_run())
