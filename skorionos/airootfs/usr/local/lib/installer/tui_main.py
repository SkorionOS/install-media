"""Entry module: python -m installer.tui_main"""

from __future__ import annotations

import os
import sys

# Live ISO runs on Linux VT (fbcon): only 16 ANSI colors. Force before Textual import.
# Truecolor Nord gets crushed to gray on VT; dialog works because it uses 16 colors.
os.environ["TEXTUAL_COLOR_SYSTEM"] = "standard"
os.environ.pop("COLORTERM", None)
os.environ.pop("NO_COLOR", None)


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
