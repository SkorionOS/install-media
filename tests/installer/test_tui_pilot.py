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
            await _activate(pilot, app, "#next")

    asyncio.run(_run())

    boot = json.loads(boot_rec.read_text())
    dep = json.loads(dep_rec.read_text())
    assert boot["env"]["FRZR_NONINTERACTIVE"] == "1"
    assert boot["argv"][0] == "gamer"
    assert boot["argv"][2] == "fresh"
    assert dep["argv"][0].startswith("3003n/skorionos:")


def test_tui_nav_arrows_move_button_focus(monkeypatch):
    """Left/right must move focus across #nav buttons (not Tab-only)."""
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.delenv("INSTALLER_SIM_AUTO", raising=False)
    monkeypatch.delenv("INSTALLER_WINDOW_SHOT", raising=False)
    monkeypatch.setenv(
        "INSTALLER_FRZR_BOOTSTRAP", str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    )
    monkeypatch.setenv(
        "INSTALLER_FRZR_DEPLOY", str(ROOT / "scripts/installer-stubs/frzr-deploy")
    )

    from installer.tui.app import InstallerTui

    async def _run():
        app = InstallerTui()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.3)
            assert app.focused is not None
            assert app.focused.id == "start"
            await pilot.press("left")
            await pilot.pause(0.05)
            assert app.focused.id == "exit", app.focused
            await pilot.press("right")
            await pilot.pause(0.05)
            assert app.focused.id == "start"
            await pilot.press("enter")
            await pilot.pause(0.2)
            # network: many buttons — arrows must walk them
            assert app.focused.id == "next"
            await pilot.press("left")
            await pilot.pause(0.05)
            assert app.focused.id == "disconnect"
            await pilot.press("left")
            await pilot.pause(0.05)
            assert app.focused.id == "reconnect"
            # reach disk: focus starts in RadioSet — left/right must enter #nav
            await pilot.press("enter")  # next from reconnect? need next
            # focus reconnect; walk to next then enter
            while getattr(app.focused, "id", None) != "next":
                await pilot.press("right")
                await pilot.pause(0.03)
            await pilot.press("enter")
            await pilot.pause(0.25)
            from textual.widgets import RadioSet

            app.screen.query_one("#disk_set", RadioSet).focus()
            await pilot.pause(0.05)
            assert isinstance(app.focused, RadioSet)
            await pilot.press("right")
            await pilot.pause(0.05)
            assert app.focused.id == "next", app.focused
            await pilot.press("left")
            await pilot.pause(0.05)
            assert app.focused.id == "back"

    asyncio.run(_run())
