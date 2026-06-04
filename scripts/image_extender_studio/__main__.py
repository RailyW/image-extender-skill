"""允许在 PYTHONPATH 包含 scripts 时执行 `python -m image_extender_studio`。"""

from __future__ import annotations

from image_extender_studio.cli.parser import main

if __name__ == "__main__":
    raise SystemExit(main())
