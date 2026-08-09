"""Unit tests for InstallPlan / bootstrap argv+env contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "skorionos/airootfs/usr/local/lib"
STUB = ROOT / "scripts/installer-stubs/frzr-bootstrap"
sys.path.insert(0, str(LIB))

from installer.engine import InstallPlan, bootstrap_env, bootstrap_argv, bootstrap_spec  # noqa: E402
from installer.engine.bootstrap import BootstrapService  # noqa: E402


def test_fresh_bootstrap_spec():
    plan = InstallPlan(disk="nvme0n1", mode="fresh")
    argv, env = bootstrap_spec(plan)
    assert argv[1:] == ["gamer", "/dev/nvme0n1", "fresh"]
    assert env == {"FRZR_NONINTERACTIVE": "1"}


def test_dual_shrink_bootstrap_spec():
    plan = InstallPlan(
        disk="sda",
        mode="dual",
        dual_op="shrink",
        shrink_partition="/dev/sda3",
        shrink_size_gb=100,
    )
    argv, env = bootstrap_spec(plan)
    assert argv[-1] == "dual"
    assert env["FRZR_NONINTERACTIVE"] == "1"
    assert env["FRZR_SHRINK_PARTITION"] == "/dev/sda3"
    assert env["FRZR_SHRINK_SIZE"] == "100"
    assert "FRZR_DELETE_PARTITION" not in env


def test_dual_delete_bootstrap_spec():
    plan = InstallPlan(
        disk="sda",
        mode="dual",
        dual_op="delete",
        delete_partition="/dev/sda2",
    )
    _, env = bootstrap_spec(plan)
    assert env["FRZR_DELETE_PARTITION"] == "/dev/sda2"


def test_validate_shrink_requires_fields():
    plan = InstallPlan(disk="sda", mode="dual", dual_op="shrink")
    errs = plan.validate_for_bootstrap()
    assert any("shrink_partition" in e for e in errs)
    assert any("shrink_size" in e for e in errs)


def test_dry_run_does_not_need_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTALLER_DRY_RUN", "1")
    monkeypatch.delenv("INSTALLER_FRZR_BOOTSTRAP", raising=False)
    plan = InstallPlan(disk="nvme0n1", mode="repair")
    log = tmp_path / "boot.log"
    result = BootstrapService().run(plan, log_file=str(log))
    assert result.returncode == 0
    assert result.dry_run is True
    assert "DRY-RUN" in result.output
    assert "FRZR_NONINTERACTIVE=1" in result.output


def test_stub_records_env(tmp_path, monkeypatch):
    record = tmp_path / "rec.json"
    monkeypatch.delenv("INSTALLER_DRY_RUN", raising=False)
    monkeypatch.setenv("INSTALLER_FRZR_BOOTSTRAP", str(STUB))
    monkeypatch.setenv("INSTALLER_STUB_RECORD", str(record))
    monkeypatch.setenv("INSTALLER_STUB_SLEEP", "0")
    monkeypatch.setenv("INSTALLER_REQUIRE_STUB", "1")

    plan = InstallPlan(
        disk="nvme0n1",
        mode="dual",
        dual_op="shrink",
        shrink_partition="/dev/nvme0n1p3",
        shrink_size_gb=60,
    )
    result = BootstrapService().run(plan, log_file=str(tmp_path / "l.log"))
    assert result.returncode == 0
    assert result.dry_run is False
    data = json.loads(record.read_text())
    assert data["argv"] == ["gamer", "/dev/nvme0n1", "dual"]
    assert data["env"]["FRZR_NONINTERACTIVE"] == "1"
    assert data["env"]["FRZR_SHRINK_PARTITION"] == "/dev/nvme0n1p3"
    assert data["env"]["FRZR_SHRINK_SIZE"] == "60"


def test_disk_path_helpers():
    assert InstallPlan(disk="sda").disk_path() == "/dev/sda"
    assert InstallPlan(disk="/dev/sda").disk_path() == "/dev/sda"
    assert InstallPlan(disk="/dev/nvme0n1").disk_name() == "nvme0n1"
