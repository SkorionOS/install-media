#!/usr/bin/env python3
"""Refuse agent completion while .sim/VERIFY-DOD.txt still has open [ ] items.

Cursor stop hook: stdin JSON {status, loop_count}, stdout {followup_message} or {}.
User abort (status != completed) is not overridden.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DOD = os.path.join(ROOT, ".sim", "VERIFY-DOD.txt")
OPEN = re.compile(r"^\[ \] (.+)$")


def _payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _open_items() -> list[str]:
    if not os.path.isfile(DOD):
        return ["VERIFY-DOD.txt is missing; recreate the floor list and continue"]
    items: list[str] = []
    with open(DOD, encoding="utf-8") as fh:
        for line in fh:
            m = OPEN.match(line.rstrip("\n"))
            if m:
                items.append(m.group(1).strip())
    return items


def main() -> int:
    payload = _payload()
    status = payload.get("status", "completed")
    if status != "completed":
        print("{}")
        return 0

    opens = _open_items()
    if not opens:
        print("{}")
        return 0

    nxt = opens[0]
    msg = (
        f".sim/VERIFY-DOD.txt still has {len(opens)} open [ ] items. "
        "You are not done. Do not ask the user to check this list or to验收. "
        f"Next item: {nxt}. "
        "Execute it now on Win5 with INSTALLER_SIMULATION=1 and installer-stubs. "
        "Do not write new rules. Do not end this turn with explanation only."
    )
    print(json.dumps({"followup_message": msg}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
