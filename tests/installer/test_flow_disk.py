"""Product-flow gates must not depend on Gtk/Textual."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skorionos/airootfs/usr/local/lib"))

from installer.flow.disk import after_disk_selected, after_dual_selected, after_frzr_check
from installer.flow.power import poweroff, reboot


def test_sim_disk_skips_host_safety(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.delenv("INSTALLER_SIM_FRZR", raising=False)
    gate = after_disk_selected("nvme0n1")
    assert gate.step == "mode"
    assert gate.has_existing is False


def test_sim_frzr_complete_offers_repair(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_FRZR", "complete")
    gate = after_disk_selected("nvme0n1")
    assert gate.step == "mode"
    assert gate.has_existing is True


def test_sim_frzr_incomplete(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_FRZR", "incomplete")
    gate = after_disk_selected("sda")
    assert gate.step == "incomplete"


def test_after_frzr_check_complete(monkeypatch):
    monkeypatch.delenv("INSTALLER_SIMULATION", raising=False)
    monkeypatch.setattr(
        "installer.backend.disk_utils.check_existing_frzr_installation",
        lambda disk: "complete",
    )
    gate = after_frzr_check("nvme0n1")
    assert gate.step == "mode" and gate.has_existing is True


def test_after_disk_too_small(monkeypatch):
    monkeypatch.delenv("INSTALLER_SIMULATION", raising=False)
    monkeypatch.setattr("installer.backend.disk_utils.is_disk_smaller_than", lambda *_a, **_k: True)
    monkeypatch.setattr("installer.backend.disk_utils.is_disk_external", lambda *_a, **_k: False)
    gate = after_disk_selected("sda", skip_safety=False)
    assert gate.step == "too_small"


def test_after_disk_external(monkeypatch):
    monkeypatch.delenv("INSTALLER_SIMULATION", raising=False)
    monkeypatch.setattr("installer.backend.disk_utils.is_disk_smaller_than", lambda *_a, **_k: False)
    monkeypatch.setattr("installer.backend.disk_utils.is_disk_external", lambda *_a, **_k: True)
    gate = after_disk_selected("sdb", skip_safety=False)
    assert gate.step == "external"


def test_dual_sim_stays_on_partition_adjust(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.delenv("INSTALLER_SIM_DUAL", raising=False)
    d = after_dual_selected("nvme0n1")
    assert d.step == "partition_adjust"


def test_sim_disk_gate_too_small(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK_GATE", "too_small")
    gate = after_disk_selected("sda")
    assert gate.step == "too_small"


def test_sim_disk_gate_external(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DISK_GATE", "external")
    gate = after_disk_selected("sdb")
    assert gate.step == "external"


def test_sim_dual_auto(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DUAL", "auto")
    d = after_dual_selected("nvme0n1")
    assert d.step == "confirm_auto"
    assert d.dual_op == "auto"


def test_sim_dual_no_shrink(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.setenv("INSTALLER_SIM_DUAL", "no_shrink")
    from installer.flow.disk import shrinkable_partitions

    assert shrinkable_partitions("nvme0n1") == []


def test_dual_free_space_auto(monkeypatch):
    monkeypatch.delenv("INSTALLER_SIMULATION", raising=False)
    monkeypatch.setattr(
        "installer.backend.disk_utils.check_free_space",
        lambda disk: [{"size_gb": 80}],
    )
    d = after_dual_selected("nvme0n1")
    assert d.step == "confirm_auto"
    assert d.dual_op == "auto"


def test_power_skipped_in_dev(monkeypatch):
    monkeypatch.setenv("INSTALLER_DEV", "1")
    assert reboot() == "skipped"
    assert poweroff() == "skipped"


def test_power_skipped_in_sim(monkeypatch):
    monkeypatch.delenv("INSTALLER_DEV", raising=False)
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    assert reboot() == "skipped"
    assert poweroff() == "skipped"


def test_sim_shrinkable_uses_p3(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    from installer.flow.disk import shrinkable_partitions

    parts = shrinkable_partitions("nvme0n1")
    assert parts[0]["path"] == "/dev/nvme0n1p3"


def test_after_frzr_check_sim_skips_host(monkeypatch):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    monkeypatch.delenv("INSTALLER_SIM_FRZR", raising=False)

    def boom(*_a, **_k):
        raise AssertionError("sim must not probe host disks")

    monkeypatch.setattr(
        "installer.backend.disk_utils.check_existing_frzr_installation", boom
    )
    gate = after_frzr_check("nvme0n1")
    assert gate.step == "mode" and gate.has_existing is False


def test_apply_advanced_skipped_in_sim(monkeypatch, tmp_path):
    monkeypatch.setenv("INSTALLER_SIMULATION", "1")
    notes: list[str] = []
    from installer.flow.lifecycle import apply_advanced_options

    apply_advanced_options(
        {"debug": True, "cdn": True},
        log=notes.append,
    )
    assert notes and "sim" in notes[0]
    assert not (tmp_path / "device-quirks").exists()
