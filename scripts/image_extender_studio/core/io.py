"""文件、JSON、命名和可选 Pillow 加载工具。

本模块只放没有业务语义的基础设施函数。它不依赖 provider、prompt 或图像
工作流，因此可以被任意上层模块安全复用。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def eprint(message: str) -> None:
    """把运行状态写到 stderr，避免污染 JSON/stdout 结果。"""
    print(message, file=sys.stderr)


def read_text(path: str | Path | None) -> str:
    """读取文本文件；没有路径时返回空字符串，方便可选参数复用。"""
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path | None, text: str) -> None:
    """按需写入文本；未指定路径时直接输出到 stdout。"""
    if path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text)


def read_json_file(path: str | Path | None, default: Any = None) -> Any:
    """读取 JSON 文件；文件不存在或未指定时返回默认值。"""
    if not path:
        return default
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path | None, data: Any) -> None:
    """把对象以稳定缩进写成 JSON；未指定路径时输出到 stdout。"""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    write_text(path, text + "\n")


def slugify(value: str, fallback: str = "asset") -> str:
    """把用户可读名称转换成安全文件名 stem。"""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return (slug or fallback)[:60]


def require_pillow() -> tuple[Any, Any, Any]:
    """延迟导入 Pillow，让非图像命令在未安装依赖时仍可运行。"""
    try:
        from PIL import Image, ImageChops, ImageDraw
    except ImportError as exc:
        raise SystemExit(
            "需要 Pillow 才能执行图像处理命令。请在当前环境安装：python3 -m pip install Pillow"
        ) from exc
    return Image, ImageChops, ImageDraw
