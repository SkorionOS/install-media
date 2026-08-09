"""Deploy plan / stub contract tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "skorionos/airootfs/usr/local/lib"
STUB = ROOT / "scripts/installer-stubs/frzr-deploy"
sys.path.insert(0, str(LIB))

from installer.engine import DeployService, InstallPlan, deploy_spec, deploy_target  # noqa: E402


def test_online_deploy_target_nv():
    plan = InstallPlan(
        disk="sda",
        mode="fresh",
        source="online",
        channel="testing",
        desktop="kde",
        nvidia=True,
    )
    assert deploy_target(plan) == "3003n/skorionos:testing:kde-nv"
    argv, env = deploy_spec(plan)
    assert argv[-1] == "3003n/skorionos:testing:kde-nv"
    assert env == {}


def test_online_deploy_debug_env():
    plan = InstallPlan(disk="sda", mode="fresh", source="online", advanced={"debug": True})
    _, env = deploy_spec(plan)
    assert env["DEBUG"] == "1"


def test_local_deploy_requires_file(tmp_path):
    missing = tmp_path / "nope.img"
    plan = InstallPlan(disk="sda", mode="fresh", source="local", local_file=missing)
    errs = plan.validate_for_deploy()
    assert errs


def test_local_deploy_ok(tmp_path):
    f = tmp_path / "img.tar.zst"
    f.write_bytes(b"x")
    plan = InstallPlan(disk="sda", mode="fresh", source="local", local_file=f)
    argv, _ = deploy_spec(plan)
    assert argv[-1] == str(f)


def test_stub_deploy(tmp_path, monkeypatch):
    record = tmp_path / "dep.json"
    monkeypatch.delenv("INSTALLER_DRY_RUN", raising=False)
    monkeypatch.setenv("INSTALLER_FRZR_DEPLOY", str(STUB))
    monkeypatch.setenv("INSTALLER_STUB_RECORD_DEPLOY", str(record))
    monkeypatch.setenv("INSTALLER_STUB_SLEEP", "0")
    monkeypatch.setenv("INSTALLER_REQUIRE_STUB", "1")
    plan = InstallPlan(
        disk="nvme0n1",
        mode="fresh",
        source="online",
        channel="stable",
        desktop="gnome",
        nvidia=False,
    )
    result = DeployService().run(plan, log_file=str(tmp_path / "d.log"))
    assert result.returncode == 0
    data = json.loads(record.read_text())
    assert data["argv"] == ["3003n/skorionos:stable:gnome"]


def test_gui_tui_plan_parity_bootstrap_deploy():
    """Same InstallPlan must produce identical specs for GUI/TUI."""
    plan = InstallPlan(
        disk="nvme0n1",
        mode="dual",
        dual_op="shrink",
        shrink_partition="/dev/nvme0n1p3",
        shrink_size_gb=60,
        source="online",
        channel="stable",
        desktop="gnome",
        nvidia=True,
    )
    from installer.engine import bootstrap_spec

    b1, e1 = bootstrap_spec(plan)
    d1, de1 = deploy_spec(plan)
    # Rebuild "as if" from another UI with same fields
    plan2 = InstallPlan(**plan.__dict__)
    b2, e2 = bootstrap_spec(plan2)
    d2, de2 = deploy_spec(plan2)
    assert (b1, e1, d1, de1) == (b2, e2, d2, de2)
    assert e1["FRZR_SHRINK_SIZE"] == "60"
    assert d1[-1].endswith("-nv")
