"""Walk every catalog case through the Textual TUI. Not INSTALLER_SIM_AUTO."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "skorionos/airootfs/usr/local/lib"
sys.path.insert(0, str(LIB))

pytest.importorskip("textual")

from coverage_catalog import (  # noqa: E402
    CASES,
    Case,
    Expect,
    REQUIRED_COMPLETE_STATUS,
    REQUIRED_CONFIRM_SHAPES,
    REQUIRED_MESSAGE_STEPS,
    REQUIRED_SCREENS,
    UNIQUE_SHOTS,
    catalog_complete_status,
    catalog_message_steps,
    catalog_screens,
    catalog_shots,
)

STUB_BOOT = ROOT / "scripts/installer-stubs/frzr-bootstrap"
STUB_DEPLOY = ROOT / "scripts/installer-stubs/frzr-deploy"


@pytest.fixture(autouse=True)
def _isolate_sim(monkeypatch, tmp_path):
    for key in (
        "INSTALLER_SIM_FRZR",
        "INSTALLER_SIM_MODE",
        "INSTALLER_SIM_ADVANCED",
        "INSTALLER_SIM_AUTO",
        "INSTALLER_SIM_DISK_GATE",
        "INSTALLER_SIM_DUAL",
        "INSTALLER_WINDOW_SHOT",
        "INSTALLER_PAGE_MARKER",
        "INSTALLER_STUB_EXIT",
        "INSTALLER_STUB_DEPLOY_EXIT",
        "INSTALLER_SIM_LOCAL",
        "INSTALLER_SIM_WIFI",
        "INSTALLER_SIM_WIFI_SSID",
        "INSTALLER_SHOT_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("INSTALLER_DEV", "1")
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK", "nvme0n1")
    monkeypatch.setenv("INSTALLER_FRZR_BOOTSTRAP", str(STUB_BOOT))
    monkeypatch.setenv("INSTALLER_FRZR_DEPLOY", str(STUB_DEPLOY))
    monkeypatch.setenv("INSTALLER_STUB_SLEEP", "0")
    monkeypatch.setenv("INSTALLER_REQUIRE_STUB", "1")
    monkeypatch.setenv("INSTALLER_LOG_FILE", str(tmp_path / "coverage.log"))
    monkeypatch.setenv("INSTALLER_STUB_RECORD", str(tmp_path / "boot.json"))
    monkeypatch.setenv("INSTALLER_STUB_RECORD_DEPLOY", str(tmp_path / "deploy.json"))
    monkeypatch.delenv("INSTALLER_DRY_RUN", raising=False)


def test_catalog_covers_required_branches():
    screens = catalog_screens()
    missing = REQUIRED_SCREENS - screens
    assert not missing, f"catalog missing screens: {sorted(missing)}"
    assert catalog_message_steps() == REQUIRED_MESSAGE_STEPS
    assert catalog_complete_status() == REQUIRED_COMPLETE_STATUS
    shots = catalog_shots()
    missing_shots = UNIQUE_SHOTS - shots
    assert not missing_shots, f"catalog missing unique shots: {sorted(missing_shots)}"
    extra = shots - UNIQUE_SHOTS
    assert not extra, f"catalog has unlisted shots: {sorted(extra)}"
    assert REQUIRED_CONFIRM_SHAPES <= shots


async def _activate(pilot, app, widget_id: str) -> None:
    try:
        await pilot.click(widget_id)
    except Exception:
        app.screen.query_one(widget_id).focus()
        await pilot.press("enter")
    await pilot.pause(0.08)


async def _wait_until(pilot, predicate, *, timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last is True:
            return
        await pilot.pause(0.05)
    raise AssertionError(f"timeout waiting for {what}; last={last!r}")


async def _wait_exec(pilot, app) -> None:
    def ready() -> bool:
        name = type(app.screen).__name__
        if name == "CompleteScreen":
            return True
        try:
            return not app.screen.query_one("#next").disabled
        except Exception:
            return False

    await _wait_until(pilot, ready, timeout=12.0, what="exec ready or complete")


async def _wait_complete(pilot, app) -> None:
    await _wait_until(
        pilot,
        lambda: type(app.screen).__name__ == "CompleteScreen",
        timeout=12.0,
        what="CompleteScreen",
    )


def _body_text(app) -> str:
    chunks: list[str] = []
    for node in app.screen.query("Static, Label"):
        try:
            chunks.append(str(node.renderable))
        except Exception:
            chunks.append(str(getattr(node, "content", "") or ""))
    return "\n".join(chunks)


def _assert_expect(app, expect: Expect) -> None:
    name = type(app.screen).__name__
    assert name == expect.screen, f"want {expect.screen}, got {name}"
    if expect.step:
        if name == "ProductMessageScreen":
            assert app.screen.step == expect.step, app.screen.step
        elif name == "CompleteScreen":
            assert app.screen.status == expect.step, app.screen.status
        else:
            raise AssertionError(f"step= set on {name}")
    if expect.copy:
        body = _body_text(app)
        assert expect.copy in body, f"{expect.copy!r} not in\n{body}"
    for wid in expect.widgets:
        app.screen.query_one(wid)
    for bid in expect.buttons:
        app.screen.query_one(f"#{bid}")
    for key, want in expect.plan.items():
        got = getattr(app.plan, key)
        assert got == want, f"plan.{key}={got!r} want {want!r}"


_SHOTS_TAKEN: set[str] = set()


def _maybe_shot(app, expect: Expect) -> None:
    dest = os.environ.get("INSTALLER_COVERAGE_SHOTS", "").strip()
    if not dest or not expect.shot:
        return
    if expect.shot in _SHOTS_TAKEN:
        return
    try:
        svg = app.export_screenshot()
    except Exception:
        return
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)
    svg_path = out / f"{expect.shot}.svg"
    png_path = out / f"{expect.shot}.png"
    svg_path.write_text(svg, encoding="utf-8")
    subprocess.run(["magick", str(svg_path), str(png_path)], check=False, capture_output=True)
    _SHOTS_TAKEN.add(expect.shot)


async def _apply(pilot, app, action: str, monkeypatch) -> None:
    if action == "noop":
        await pilot.pause(0.05)
        return
    if action == "wait_exec":
        await _wait_exec(pilot, app)
        return
    if action == "wait_complete":
        await _wait_complete(pilot, app)
        return
    if action.startswith("click:"):
        await _activate(pilot, app, action.split(":", 1)[1])
        return
    if action.startswith("select:"):
        wid = action.split(":", 1)[1]
        app.screen.query_one(wid).value = True
        await pilot.pause(0.08)
        return
    if action.startswith("check:"):
        wid = action.split(":", 1)[1]
        app.screen.query_one(wid).value = True
        await pilot.pause(0.08)
        return
    if action.startswith("focus:"):
        app.screen.query_one(action.split(":", 1)[1]).focus()
        await pilot.pause(0.08)
        return
    if action.startswith("press:"):
        keys = action.split(":", 1)[1].split(",")
        await pilot.press(*keys)
        await pilot.pause(0.15)
        return
    if action.startswith("setenv:"):
        raw = action.split(":", 1)[1]
        key, value = raw.split("=", 1)
        monkeypatch.setenv(key, value)
        os.environ[key] = value
        return
    raise ValueError(f"unknown action {action!r}")


async def _run_case(case: Case, monkeypatch) -> None:
    for key, value in case.env.items():
        monkeypatch.setenv(key, value)
        os.environ[key] = value

    from installer.tui.app import InstallerTui

    app = InstallerTui()
    async with app.run_test(size=(120, 48)) as pilot:
        await pilot.pause(0.15)
        for action, expect in case.path:
            await _apply(pilot, app, action, monkeypatch)
            await pilot.pause(0.05)
            if (
                expect.screen == "CompleteScreen"
                and type(app.screen).__name__ != "CompleteScreen"
            ):
                await _wait_complete(pilot, app)
            _assert_expect(app, expect)
            _maybe_shot(app, expect)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_tui_case(case: Case, monkeypatch):
    asyncio.run(_run_case(case, monkeypatch))
