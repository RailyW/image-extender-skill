#!/usr/bin/env python3
"""Image Extender Studio Skill 的兼容 CLI 入口。

历史版本把所有实现都放在本文件中；现在具体功能已拆分到
`scripts/image_extender_studio/` 包内。本入口保持原命令路径不变，
方便已有文档、自动化和用户脚本继续调用。
"""

from __future__ import annotations

from image_extender_studio.cli.parser import main

if __name__ == "__main__":
    raise SystemExit(main())
