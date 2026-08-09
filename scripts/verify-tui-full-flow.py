#!/usr/bin/env python3
"""
Drive the REAL Textual installer through a full wizard (welcome->...->install)
with stub frzr only for destructive commands. Assert recorded argv/env.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "skorionos/airootfs/usr/local/lib"
sys.path.insert(0, str(LIB))


async def run_flow(mode: str, dual_op: str | None, expect_boot: dict, expect_dep_prefix: str, tmp: Path):
    boot_rec = tmp / f"boot-{mode}-{dual_op or 'none'}.json"
    dep_rec = tmp / f"dep-{mode}-{dual_op or 'none'}.json"
    os.environ["INSTALLER_DEV"] = "1"
    os.environ.pop("INSTALLER_DRY_RUN", None)
    os.environ["INSTALLER_FRZR_BOOTSTRAP"] = str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    os.environ["INSTALLER_FRZR_DEPLOY"] = str(ROOT / "scripts/installer-stubs/frzr-deploy")
    os.environ["INSTALLER_STUB_RECORD"] = str(boot_rec)
    os.environ["INSTALLER_STUB_RECORD_DEPLOY"] = str(dep_rec)
    os.environ["INSTALLER_STUB_SLEEP"] = "0"
    os.environ["INSTALLER_REQUIRE_STUB"] = "1"
    os.environ["INSTALLER_LOG_FILE"] = str(tmp / "tui.log")

    from installer.tui.app import InstallerTui

    app = InstallerTui()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.click("#start")
        await pilot.pause()
        # disk
        await pilot.click("#next")
        await pilot.pause()
        # mode list: fresh=0, repair=1, dual=2
        modes = {"fresh": 0, "repair": 1, "dual": 2}
        lv = app.screen.query_one("#modes")
        lv.index = modes[mode]
        await pilot.pause()
        await pilot.click("#next")
        await pilot.pause()
        if mode == "dual":
            ops = {"auto": 0, "shrink": 1, "delete": 2}
            app.screen.query_one("#dualops").index = ops[dual_op or "auto"]
            await pilot.pause()
            await pilot.click("#next")
            await pilot.pause()
        # version — pick nvidia gnome stable (index 1)
        app.screen.query_one("#versions").index = 1
        await pilot.pause()
        await pilot.click("#next")
        await pilot.pause()
        await pilot.click("#go")
        for _ in range(100):
            await pilot.pause(0.05)
            if boot_rec.exists() and dep_rec.exists():
                break

    assert boot_rec.exists(), f"missing bootstrap record for {mode}/{dual_op}"
    assert dep_rec.exists(), f"missing deploy record for {mode}/{dual_op}"
    boot = json.loads(boot_rec.read_text())
    dep = json.loads(dep_rec.read_text())
    assert boot["argv"][2] == expect_boot["mode"]
    for k, v in expect_boot.get("env", {}).items():
        assert boot["env"].get(k) == v, (boot["env"], k, v)
    assert dep["argv"][0].startswith(expect_dep_prefix), dep
    print(f"[PASS] full TUI flow mode={mode} dual_op={dual_op} boot={boot} dep={dep}")


def main() -> int:
    tmp = Path("/tmp/installer-full-tui-verify")
    tmp.mkdir(parents=True, exist_ok=True)
    flows = [
        ("fresh", None, {"mode": "fresh", "env": {"FRZR_NONINTERACTIVE": "1"}}, "3003n/skorionos:stable:gnome-nv"),
        ("repair", None, {"mode": "repair", "env": {"FRZR_NONINTERACTIVE": "1"}}, "3003n/skorionos:stable:gnome-nv"),
        (
            "dual",
            "shrink",
            {
                "mode": "dual",
                "env": {
                    "FRZR_NONINTERACTIVE": "1",
                    "FRZR_SHRINK_SIZE": "60",
                },
            },
            "3003n/skorionos:stable:gnome-nv",
        ),
        (
            "dual",
            "delete",
            {"mode": "dual", "env": {"FRZR_NONINTERACTIVE": "1"}},
            "3003n/skorionos:stable:gnome-nv",
        ),
    ]
    for mode, dual_op, expect_boot, dep_prefix in flows:
        asyncio.run(run_flow(mode, dual_op, expect_boot, dep_prefix, tmp))
        # shrink must include partition key
        if mode == "dual" and dual_op == "shrink":
            boot = json.loads((tmp / f"boot-{mode}-{dual_op}.json").read_text())
            assert "FRZR_SHRINK_PARTITION" in boot["env"], boot
            assert boot["env"]["FRZR_SHRINK_PARTITION"].startswith("/dev/")
        if mode == "dual" and dual_op == "delete":
            boot = json.loads((tmp / f"boot-{mode}-{dual_op}.json").read_text())
            assert "FRZR_DELETE_PARTITION" in boot["env"], boot
    print("ALL FULL TUI FLOWS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
