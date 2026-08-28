"""GUI coverage without launching GTK: every TUI branch maps to a real page."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "skorionos/airootfs/usr/local/lib"
UI = LIB / "installer/ui/pages"
MAIN = LIB / "installer/main.py"
sys.path.insert(0, str(Path(__file__).parent))

from coverage_catalog import (  # noqa: E402
    GUI_PAGE_NAMES,
    TUI_TO_GUI,
    catalog_gui_pages,
    catalog_screens,
)

PAGE_CREATE_FILES = {
    "network": UI / "network.py",
    "disk": UI / "disk.py",
    "mode": UI / "mode.py",
    "partition_adjust": UI / "partition_adjust.py",
    "confirm": UI / "confirm.py",
    "bootstrap": UI / "bootstrap.py",
    "version": UI / "version.py",
    "advanced": UI / "advanced.py",
    "install": UI / "install.py",
    "complete": UI / "complete.py",
    "message": UI / "message.py",
}


def _page_map_from_main() -> set[str]:
    src = MAIN.read_text(encoding="utf-8")
    keys = set(re.findall(r"'(\w+)':\s*\d+", src.split("page_map = {", 1)[1].split("}", 1)[0]))
    return keys


def test_gui_page_map_matches_catalog():
    mapped = _page_map_from_main()
    assert mapped == GUI_PAGE_NAMES
    catalog = catalog_gui_pages()
    missing = GUI_PAGE_NAMES - catalog
    assert not missing, f"catalog never mentions GUI pages: {sorted(missing)}"


def test_every_tui_screen_has_gui_page():
    screens = catalog_screens()
    unmapped = screens - set(TUI_TO_GUI)
    assert not unmapped, f"TUI screens without GUI mapping: {sorted(unmapped)}"
    for screen, page in TUI_TO_GUI.items():
        assert page in GUI_PAGE_NAMES, f"{screen} → {page} not in GUI page_map"


def test_gui_page_modules_exist_and_parse():
    assert (MAIN.parent / "main.py").is_file()
    welcome = "def create_welcome_page" in MAIN.read_text(encoding="utf-8")
    assert welcome, "GTK welcome lives on InstallerApp, not a page module"
    for name, path in PAGE_CREATE_FILES.items():
        assert path.is_file(), name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert any(isinstance(n, ast.ClassDef) for n in tree.body), name


def test_gui_disk_handles_all_flow_gates():
    src = (UI / "disk.py").read_text(encoding="utf-8")
    for token in (
        'gate.step == "too_small"',
        'gate.step == "external"',
        'gate.step == "incomplete"',
        "after_disk_selected",
        "after_frzr_check",
        "after_dual_selected",
    ):
        assert token in src, f"disk.py missing {token}"


def test_gui_mode_and_complete_use_shared_copy():
    mode = (UI / "mode.py").read_text(encoding="utf-8")
    complete = (UI / "complete.py").read_text(encoding="utf-8")
    assert "flow_copy.MODE_REPAIR" in mode
    assert "flow_copy.COMPLETE_SUCCESS_TITLE" in complete
    assert "from ...flow.power import reboot" in complete
    assert "from ...flow.power import poweroff" in complete
