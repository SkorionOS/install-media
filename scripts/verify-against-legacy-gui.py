#!/usr/bin/env python3
"""
Independent oracle: rebuild argv/env using the PRE-refactor GUI logic
copied from git HEAD, then compare to InstallEngine.

This is not a self-referential unit test of the engine.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skorionos/airootfs/usr/local/lib"))

from installer.engine import InstallPlan, bootstrap_spec, deploy_spec  # noqa: E402


def legacy_bootstrap(app) -> tuple[list[str], dict[str, str]]:
    """Exact contract from old BootstrapPage.execute (git HEAD)."""
    disk = app.selected_disk
    mode = app.install_mode
    cmd = ["frzr-bootstrap", "gamer", f"/dev/{disk}", mode]
    env = {"FRZR_NONINTERACTIVE": "1"}
    if mode == "dual":
        dual_mode = getattr(app, "dual_mode", "auto")
        if dual_mode == "shrink":
            env["FRZR_SHRINK_PARTITION"] = app.shrink_partition
            env["FRZR_SHRINK_SIZE"] = str(app.shrink_size)
        elif dual_mode == "delete":
            env["FRZR_DELETE_PARTITION"] = app.delete_partition
    return cmd, env


def legacy_deploy(selections: dict) -> list[str]:
    """Exact contract from old InstallPage._build_install_command (git HEAD)."""
    install_mode = selections.get("install_mode", "online")
    if install_mode == "local":
        local_file = selections.get("local_file")
        if not local_file or not os.path.exists(local_file):
            raise Exception(f"本地镜像文件不存在: {local_file}")
        return ["frzr-deploy", local_file]
    channel = selections.get("channel", "stable")
    desktop = selections.get("desktop", "gnome")
    nvidia = selections.get("nvidia", False)
    if nvidia:
        target = f"{channel}:{desktop}-nv"
    else:
        target = f"{channel}:{desktop}"
    return ["frzr-deploy", f"3003n/skorionos:{target}"]


CASES = [
    SimpleNamespace(
        name="fresh",
        selected_disk="nvme0n1",
        install_mode="fresh",
        dual_mode=None,
        shrink_partition=None,
        shrink_size=None,
        delete_partition=None,
        version_selections={
            "install_mode": "online",
            "channel": "stable",
            "desktop": "gnome",
            "nvidia": False,
        },
        advanced_options={},
    ),
    SimpleNamespace(
        name="repair",
        selected_disk="sda",
        install_mode="repair",
        dual_mode=None,
        shrink_partition=None,
        shrink_size=None,
        delete_partition=None,
        version_selections={
            "install_mode": "online",
            "channel": "testing",
            "desktop": "kde",
            "nvidia": False,
        },
        advanced_options={},
    ),
    SimpleNamespace(
        name="dual-auto",
        selected_disk="nvme0n1",
        install_mode="dual",
        dual_mode="auto",
        shrink_partition=None,
        shrink_size=None,
        delete_partition=None,
        version_selections={
            "install_mode": "online",
            "channel": "stable",
            "desktop": "gnome",
            "nvidia": True,
        },
        advanced_options={"debug": True},
    ),
    SimpleNamespace(
        name="dual-shrink",
        selected_disk="nvme0n1",
        install_mode="dual",
        dual_mode="shrink",
        shrink_partition="/dev/nvme0n1p3",
        shrink_size=100,
        delete_partition=None,
        version_selections={
            "install_mode": "online",
            "channel": "unstable",
            "desktop": "gnome",
            "nvidia": True,
        },
        advanced_options={},
    ),
    SimpleNamespace(
        name="dual-delete",
        selected_disk="sda",
        install_mode="dual",
        dual_mode="delete",
        shrink_partition=None,
        shrink_size=None,
        delete_partition="/dev/sda2",
        version_selections={
            "install_mode": "online",
            "channel": "stable",
            "desktop": "kde",
            "nvidia": False,
        },
        advanced_options={},
    ),
]


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "local.img.tar.zst"
        local.write_bytes(b"x")
        local_case = SimpleNamespace(
            name="local",
            selected_disk="nvme0n1",
            install_mode="fresh",
            dual_mode=None,
            shrink_partition=None,
            shrink_size=None,
            delete_partition=None,
            version_selections={"install_mode": "local", "local_file": str(local)},
            advanced_options={},
        )
        cases = list(CASES) + [local_case]

        print("=== Oracle: legacy GUI vs InstallEngine ===")
        for app in cases:
            plan = InstallPlan.from_app_state(app)
            eng_b_argv, eng_b_env = bootstrap_spec(plan)
            # Engine argv[0] may be overridden by INSTALLER_FRZR_*; compare tail + FRZR env
            eng_b_tail = eng_b_argv[1:]
            leg_b_argv, leg_b_env = legacy_bootstrap(app)
            leg_b_tail = leg_b_argv[1:]

            eng_d_argv, eng_d_env = deploy_spec(plan)
            leg_d_argv = legacy_deploy(app.version_selections)

            ok = True
            if eng_b_tail != leg_b_tail:
                print(f"[FAIL] {app.name} bootstrap argv: engine={eng_b_tail} legacy={leg_b_tail}")
                ok = False
            # Compare only FRZR_* keys (legacy used full environ copy)
            if eng_b_env != leg_b_env:
                print(f"[FAIL] {app.name} bootstrap env: engine={eng_b_env} legacy={leg_b_env}")
                ok = False
            if eng_d_argv[1:] != leg_d_argv[1:]:
                print(f"[FAIL] {app.name} deploy argv: engine={eng_d_argv[1:]} legacy={leg_d_argv[1:]}")
                ok = False
            # debug env only in engine overlay when advanced.debug
            if app.advanced_options.get("debug") and eng_d_env.get("DEBUG") != "1":
                print(f"[FAIL] {app.name} missing DEBUG=1")
                ok = False
            if ok:
                print(f"[PASS] {app.name}: bootstrap={eng_b_tail} deploy={eng_d_argv[1:]} env={eng_b_env}")
            else:
                failures += 1

    # Real frzr binary contract: does system frzr-bootstrap accept our argv shape?
    print("\n=== Real frzr-bootstrap argv acceptance (no disk write expected) ===")
    import subprocess

    frzr = "/usr/bin/frzr-bootstrap"
    if not Path(frzr).exists():
        print("[SKIP] /usr/bin/frzr-bootstrap not installed")
    else:
        env = os.environ.copy()
        env["FRZR_NONINTERACTIVE"] = "1"
        # Use a non-existent disk path — must fail AFTER accepting INSTALL_TYPE, not usage error
        proc = subprocess.run(
            [frzr, "gamer", "/dev/skorionos-does-not-exist", "fresh"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        print(f"exit={proc.returncode}")
        print(out[-800:] if len(out) > 800 else out)
        # Usage errors typically mention Usage: ; disk errors mention no such / not found / does-not-exist
        if "Usage:" in out and "INSTALL_TYPE" in out and "does-not-exist" not in out.lower():
            print("[FAIL] frzr rejected argv shape as usage error")
            failures += 1
        elif proc.returncode == 0:
            print("[FAIL] unexpected success on missing disk")
            failures += 1
        else:
            print("[PASS] real frzr-bootstrap accepted noninteractive argv and failed on missing disk")

    print("\n=== Summary ===")
    if failures:
        print(f"FAILED ({failures})")
        return 1
    print("ALL ORACLE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
