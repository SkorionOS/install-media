"""Entry module: python -m installer.tui_main"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from installer.tui.app import run
    except ImportError as exc:
        print(f"Textual TUI unavailable: {exc}", file=sys.stderr)
        print("Install python-textual or fall back to installer-text.sh", file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":
    sys.exit(main())
