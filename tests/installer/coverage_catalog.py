"""Product-branch catalog for installer TUI+GUI coverage.

Each case is a wizard path the Textual Pilot must walk. GUI coverage is the
same branch list mapped onto GTK page names — GTK is not launched from CI.

This file is the source of truth. test_tui_coverage.py drives TUI.
test_gui_coverage_map.py asserts every case has a GUI page and every TUI
screen class appears in at least one case.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Expect:
    screen: str
    step: str | None = None
    copy: str | None = None
    widgets: tuple[str, ...] = ()
    buttons: tuple[str, ...] = ()
    plan: dict[str, object] = field(default_factory=dict)
    shot: str | None = None


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    env: dict[str, str]
    path: tuple[tuple[str, Expect], ...]
    gui_pages: tuple[str, ...]


# Shared prefix: Welcome → Network → Disk
_W = ("click:#start", Expect("NetworkScreen", shot="network"))
_N = ("click:#next", Expect("DiskScreen", shot="disk"))


def _fresh_to_mode() -> tuple[tuple[str, Expect], ...]:
    return (
        _W,
        _N,
        ("click:#next", Expect("ModeScreen", widgets=("#mode_fresh", "#mode_dual"), shot="mode")),
    )


CASES: tuple[Case, ...] = (
    Case(
        id="happy_fresh_success",
        title="fresh online install reaches complete/success",
        env={"INSTALLER_SIM_MODE": "fresh", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("welcome", "network", "disk", "mode", "confirm", "bootstrap", "version", "install", "complete"),
        path=(
            ("noop", Expect("WelcomeScreen", shot="welcome")),
            *_fresh_to_mode(),
            ("click:#next", Expect("ConfirmScreen", copy="格式化整个磁盘", shot="confirm_fresh")),
            ("click:#go", Expect("BootstrapScreen", shot="bootstrap")),
            ("wait_exec", Expect("BootstrapScreen")),
            ("click:#next", Expect("VersionScreen", widgets=("#src_online", "#opt_advanced"), shot="version")),
            ("click:#next", Expect("InstallScreen", shot="install")),
            ("wait_exec", Expect("InstallScreen")),
            ("click:#next", Expect("CompleteScreen", step="success", buttons=("reboot", "exit", "shutdown"), shot="complete_success")),
        ),
    ),
    Case(
        id="fresh_advanced",
        title="version advanced checkbox opens advanced then install",
        env={"INSTALLER_SIM_MODE": "fresh", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("version", "advanced", "install"),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("ConfirmScreen")),
            ("click:#go", Expect("BootstrapScreen")),
            ("wait_exec", Expect("BootstrapScreen")),
            ("click:#next", Expect("VersionScreen")),
            ("check:#opt_advanced", Expect("VersionScreen")),
            ("click:#next", Expect("AdvancedScreen", widgets=("#adv_fallback_url",), shot="advanced")),
            ("click:#next", Expect("InstallScreen")),
        ),
    ),
    Case(
        id="fresh_local",
        title="local image source is accepted",
        env={
            "INSTALLER_SIM_MODE": "fresh",
            "INSTALLER_SIM_ONLINE": "1",
            "INSTALLER_SIM_LOCAL": "1",
        },
        gui_pages=("version",),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("ConfirmScreen")),
            ("click:#go", Expect("BootstrapScreen")),
            ("wait_exec", Expect("BootstrapScreen")),
            ("click:#next", Expect("VersionScreen", widgets=("#src_local",))),
            ("select:#src_local", Expect("VersionScreen", shot="version_local")),
            ("click:#next", Expect("InstallScreen", plan={"source": "local"})),
        ),
    ),
    Case(
        id="fresh_offline_version",
        title="online install while offline shows network-offline message",
        env={"INSTALLER_SIM_MODE": "fresh", "INSTALLER_SIM_ONLINE": "0"},
        gui_pages=("version", "message"),
        path=(
            _W,
            _N,
            ("click:#next", Expect("ModeScreen")),
            ("click:#next", Expect("ConfirmScreen")),
            ("click:#go", Expect("BootstrapScreen")),
            ("wait_exec", Expect("BootstrapScreen")),
            ("click:#next", Expect("VersionScreen")),
            (
                "click:#next",
                Expect(
                    "ProductMessageScreen",
                    step="offline",
                    copy="在线安装需要稳定的网络连接",
                    shot="msg_offline",
                ),
            ),
        ),
    ),
    Case(
        id="repair_success",
        title="existing frzr offers repair and confirm copy matches GUI",
        env={
            "INSTALLER_SIM_FRZR": "complete",
            "INSTALLER_SIM_MODE": "repair",
            "INSTALLER_SIM_ONLINE": "1",
        },
        gui_pages=("mode", "confirm", "bootstrap", "complete"),
        path=(
            _W,
            _N,
            (
                "click:#next",
                Expect(
                    "ModeScreen",
                    widgets=("#mode_repair", "#mode_fresh", "#mode_dual"),
                    shot="mode_repair",
                ),
            ),
            ("click:#next", Expect("ConfirmScreen", copy="保留用户数据", shot="confirm_repair")),
            ("click:#go", Expect("BootstrapScreen")),
            ("wait_exec", Expect("BootstrapScreen")),
            ("click:#next", Expect("VersionScreen")),
            ("click:#next", Expect("InstallScreen")),
            ("wait_exec", Expect("InstallScreen")),
            ("click:#next", Expect("CompleteScreen", step="success")),
        ),
    ),
    Case(
        id="dual_shrink",
        title="dual without free space → shrink 100GB like GUI default",
        env={"INSTALLER_SIM_MODE": "dual", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("mode", "partition_adjust", "confirm"),
        path=(
            *_fresh_to_mode(),
            (
                "click:#next",
                Expect(
                    "PartitionAdjustScreen",
                    widgets=(
                        "#part_0",
                        "#dual_shrink",
                        "#dual_delete",
                        "#size_60",
                        "#size_100",
                        "#size_200",
                    ),
                    shot="partition_adjust",
                ),
            ),
            (
                "click:#next",
                Expect(
                    "ConfirmScreen",
                    copy="缩小分区",
                    plan={"mode": "dual", "dual_op": "shrink", "shrink_size_gb": 100},
                    shot="confirm_dual_shrink",
                ),
            ),
        ),
    ),
    Case(
        id="dual_delete",
        title="dual partition adjust delete",
        env={"INSTALLER_SIM_MODE": "dual", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("partition_adjust", "confirm"),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("PartitionAdjustScreen")),
            ("select:#dual_delete", Expect("PartitionAdjustScreen")),
            (
                "click:#next",
                Expect(
                    "ConfirmScreen",
                    copy="删除分区",
                    plan={"mode": "dual", "dual_op": "delete"},
                    shot="confirm_dual_delete",
                ),
            ),
        ),
    ),
    Case(
        id="dual_auto",
        title="dual with enough free space skips partition adjust",
        env={
            "INSTALLER_SIM_MODE": "dual",
            "INSTALLER_SIM_DUAL": "auto",
            "INSTALLER_SIM_ONLINE": "1",
        },
        gui_pages=("mode", "confirm"),
        path=(
            *_fresh_to_mode(),
            (
                "click:#next",
                Expect(
                    "ConfirmScreen",
                    copy="未分配空间",
                    plan={"mode": "dual", "dual_op": "auto"},
                    shot="confirm_dual_auto",
                ),
            ),
        ),
    ),
    Case(
        id="dual_no_shrink",
        title="dual adjust with no shrinkable partitions",
        env={
            "INSTALLER_SIM_MODE": "dual",
            "INSTALLER_SIM_DUAL": "no_shrink",
            "INSTALLER_SIM_ONLINE": "1",
        },
        gui_pages=("partition_adjust", "message"),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("PartitionAdjustScreen")),
            (
                "click:#next",
                Expect(
                    "ProductMessageScreen",
                    step="no_shrink",
                    copy="没有找到可以操作的分区",
                    shot="msg_no_shrink",
                ),
            ),
        ),
    ),
    Case(
        id="disk_too_small",
        title="too-small disk is a dead end (back only)",
        env={"INSTALLER_SIM_DISK_GATE": "too_small", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("disk", "message"),
        path=(
            _W,
            _N,
            (
                "click:#next",
                Expect(
                    "ProductMessageScreen",
                    step="too_small",
                    copy="小于",
                    buttons=("back",),
                    shot="msg_too_small",
                ),
            ),
            ("click:#back", Expect("DiskScreen")),
        ),
    ),
    Case(
        id="disk_external",
        title="external disk warning then continue to mode",
        env={"INSTALLER_SIM_DISK_GATE": "external", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("disk", "message", "mode"),
        path=(
            _W,
            _N,
            (
                "click:#next",
                Expect(
                    "ProductMessageScreen",
                    step="external",
                    copy="外部设备",
                    shot="msg_external",
                ),
            ),
            ("click:#next", Expect("ModeScreen")),
        ),
    ),
    Case(
        id="disk_external_incomplete",
        title="external continue still hits incomplete frzr",
        env={
            "INSTALLER_SIM_DISK_GATE": "external",
            "INSTALLER_SIM_FRZR": "incomplete",
            "INSTALLER_SIM_ONLINE": "1",
        },
        gui_pages=("disk", "message"),
        path=(
            _W,
            _N,
            ("click:#next", Expect("ProductMessageScreen", step="external")),
            (
                "click:#next",
                Expect("ProductMessageScreen", step="incomplete", shot="msg_incomplete"),
            ),
        ),
    ),
    Case(
        id="disk_incomplete",
        title="incomplete frzr cleanup then mode without repair",
        env={"INSTALLER_SIM_FRZR": "incomplete", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("disk", "message", "mode"),
        path=(
            _W,
            _N,
            (
                "click:#next",
                Expect(
                    "ProductMessageScreen",
                    step="incomplete",
                    copy="不完整的 frzr",
                    buttons=("back", "next"),
                ),
            ),
            ("click:#next", Expect("ModeScreen", widgets=("#mode_fresh", "#mode_dual"))),
        ),
    ),
    Case(
        id="cancel_mode_exit",
        title="mode 退出 → complete/cancelled → reinstall",
        env={"INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("mode", "complete", "welcome"),
        path=(
            *_fresh_to_mode(),
            (
                "click:#exit",
                Expect(
                    "CompleteScreen",
                    step="cancelled",
                    buttons=("reinstall", "exit", "shutdown"),
                    shot="complete_cancel",
                ),
            ),
            ("click:#reinstall", Expect("WelcomeScreen", shot="welcome")),
        ),
    ),
    Case(
        id="bootstrap_fail",
        title="bootstrap stub failure opens complete/failed",
        env={
            "INSTALLER_SIM_MODE": "fresh",
            "INSTALLER_SIM_ONLINE": "1",
            "INSTALLER_STUB_EXIT": "1",
        },
        gui_pages=("bootstrap", "complete"),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("ConfirmScreen")),
            (
                "click:#go",
                Expect(
                    "CompleteScreen",
                    step="failed",
                    buttons=("reinstall", "exit", "shutdown"),
                    shot="complete_fail",
                ),
            ),
        ),
    ),
    Case(
        id="deploy_fail",
        title="deploy stub failure after version opens complete/failed",
        env={"INSTALLER_SIM_MODE": "fresh", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("install", "complete"),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("ConfirmScreen")),
            ("click:#go", Expect("BootstrapScreen")),
            ("wait_exec", Expect("BootstrapScreen")),
            ("click:#next", Expect("VersionScreen")),
            ("setenv:INSTALLER_STUB_EXIT=1", Expect("VersionScreen")),
            ("click:#next", Expect("CompleteScreen", step="failed")),
        ),
    ),
    Case(
        id="wifi_password",
        title="secured sim AP opens password screen",
        env={
            "INSTALLER_SIM_WIFI": "1",
            "INSTALLER_SIM_ONLINE": "0",
        },
        gui_pages=("network",),
        path=(
            _W,
            ("focus:#wifi_list", Expect("NetworkScreen", shot="network_offline")),
            ("press:down,enter", Expect("WifiPasswordScreen", shot="wifi_password")),
        ),
    ),
    Case(
        id="version_kde_nv",
        title="online KDE + NVIDIA selections land on the plan",
        env={"INSTALLER_SIM_MODE": "fresh", "INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("version",),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("ConfirmScreen")),
            ("click:#go", Expect("BootstrapScreen")),
            ("wait_exec", Expect("BootstrapScreen")),
            ("click:#next", Expect("VersionScreen", widgets=("#de_kde", "#nv_yes"))),
            ("select:#de_kde", Expect("VersionScreen")),
            ("select:#nv_yes", Expect("VersionScreen")),
            (
                "click:#next",
                Expect("InstallScreen", plan={"desktop": "kde", "nvidia": True, "channel": "stable"}),
            ),
        ),
    ),
    Case(
        id="confirm_back",
        title="confirm 返回 re-arms mode continue",
        env={"INSTALLER_SIM_ONLINE": "1"},
        gui_pages=("mode", "confirm"),
        path=(
            *_fresh_to_mode(),
            ("click:#next", Expect("ConfirmScreen")),
            ("click:#back", Expect("ModeScreen")),
            ("click:#next", Expect("ConfirmScreen")),
        ),
    ),
)


REQUIRED_SCREENS = {
    "WelcomeScreen",
    "NetworkScreen",
    "WifiPasswordScreen",
    "DiskScreen",
    "ProductMessageScreen",
    "ModeScreen",
    "PartitionAdjustScreen",
    "ConfirmScreen",
    "BootstrapScreen",
    "VersionScreen",
    "AdvancedScreen",
    "InstallScreen",
    "CompleteScreen",
}

REQUIRED_MESSAGE_STEPS = {"too_small", "external", "incomplete", "no_shrink", "offline"}
REQUIRED_COMPLETE_STATUS = {"success", "cancelled", "failed"}
REQUIRED_CONFIRM_SHAPES = {
    "confirm_fresh",
    "confirm_repair",
    "confirm_dual_auto",
    "confirm_dual_shrink",
    "confirm_dual_delete",
}

GUI_PAGE_NAMES = {
    "welcome",
    "network",
    "disk",
    "mode",
    "partition_adjust",
    "confirm",
    "bootstrap",
    "version",
    "advanced",
    "install",
    "complete",
    "message",
}

TUI_TO_GUI = {
    "WelcomeScreen": "welcome",
    "NetworkScreen": "network",
    "WifiPasswordScreen": "network",
    "DiskScreen": "disk",
    "ProductMessageScreen": "message",
    "ModeScreen": "mode",
    "PartitionAdjustScreen": "partition_adjust",
    "ConfirmScreen": "confirm",
    "BootstrapScreen": "bootstrap",
    "VersionScreen": "version",
    "AdvancedScreen": "advanced",
    "InstallScreen": "install",
    "CompleteScreen": "complete",
}

UNIQUE_SHOTS = {
    "welcome",
    "network",
    "network_offline",
    "wifi_password",
    "disk",
    "msg_too_small",
    "msg_external",
    "msg_incomplete",
    "msg_no_shrink",
    "msg_offline",
    "mode",
    "mode_repair",
    "partition_adjust",
    "confirm_fresh",
    "confirm_repair",
    "confirm_dual_auto",
    "confirm_dual_shrink",
    "confirm_dual_delete",
    "bootstrap",
    "version",
    "version_local",
    "advanced",
    "install",
    "complete_success",
    "complete_cancel",
    "complete_fail",
}


def catalog_screens() -> set[str]:
    return {expect.screen for case in CASES for _action, expect in case.path}


def catalog_message_steps() -> set[str]:
    return {
        expect.step
        for case in CASES
        for _action, expect in case.path
        if expect.screen == "ProductMessageScreen" and expect.step
    }


def catalog_complete_status() -> set[str]:
    return {
        expect.step
        for case in CASES
        for _action, expect in case.path
        if expect.screen == "CompleteScreen" and expect.step
    }


def catalog_shots() -> set[str]:
    return {expect.shot for case in CASES for _action, expect in case.path if expect.shot}


def catalog_gui_pages() -> set[str]:
    pages: set[str] = set()
    for case in CASES:
        pages.update(case.gui_pages)
    return pages
