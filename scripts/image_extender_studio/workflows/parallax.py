"""横版游戏 parallax 背景图层工作流。

本模块负责四层 manifest 初始化、图层色键、manifest 路径更新、repeat-x
扩图计划和最终 zip 打包。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from image_extender_studio.core.constants import LAYER_SPECS
from image_extender_studio.core.io import read_json_file, write_json
from image_extender_studio.imaging.common import (
    chroma_key_image,
    load_rgba,
    make_zip,
    save_rgba,
)


def init_parallax(output: str) -> dict[str, Any]:
    """创建四层 parallax manifest。"""
    layers = []
    for role in ["sky", "far", "mid", "near"]:
        spec = LAYER_SPECS[role]
        layers.append(
            {
                "role": role,
                "image": None,
                "raw_image": None,
                "width": spec["width"],
                "height": spec["height"],
                "scroll_speed": spec["speed"],
                "opaque": spec["opaque"],
            }
        )
    manifest = {
        "version": 1,
        "workflow_order": ["near", "mid", "far", "sky"],
        "layers": layers,
    }
    write_json(output, manifest)
    return manifest


def key_parallax_layer(input_path: str, role: str, output: str) -> dict[str, Any]:
    """对非 sky 图层执行洋红色透明化；sky 直接复制。"""
    img = load_rgba(input_path)
    keyed = img if role == "sky" else chroma_key_image(img)
    save_rgba(keyed, output)
    return {"input": input_path, "output": output, "role": role, "keyed": role != "sky"}


def package_parallax(manifest_path: str, output: str) -> dict[str, Any]:
    """根据 parallax manifest 打包图层和 JSON。"""
    manifest = read_json_file(manifest_path, default={})
    base = Path(manifest_path).parent
    files = [Path(manifest_path)]
    for layer in manifest.get("layers", []):
        for key in ("image", "raw_image"):
            value = layer.get(key)
            if value:
                files.append(
                    (base / value) if not Path(value).is_absolute() else Path(value)
                )
    make_zip(output, files)
    return manifest


def update_parallax_image(
    manifest_path: str, role: str, image: str, raw_image: str | None
) -> dict[str, Any]:
    """更新某个 parallax 图层的图片路径。"""
    manifest = read_json_file(manifest_path, default={})
    for layer in manifest.get("layers", []):
        if layer.get("role") == role:
            layer["image"] = image
            layer["raw_image"] = raw_image or image
            try:
                img = load_rgba(Path(manifest_path).parent / image)
                layer["width"] = img.width
                layer["height"] = img.height
            except Exception:
                pass
    write_json(manifest_path, manifest)
    return manifest


def auto_plan_parallax(
    width: int, target: int, extension_percent: int = 38, max_steps: int = 14
) -> dict[str, Any]:
    """规划 parallax 横向自动扩图步数，避免每次由 LLM 心算。"""
    steps = []
    current = width
    for index in range(max_steps):
        if current >= target:
            break
        amount = max(128, round(current * extension_percent / 100))
        steps.append(
            {
                "step": index + 1,
                "direction": "right",
                "amount": amount,
                "start_width": current,
                "end_width": current + amount,
            }
        )
        current += amount
    return {
        "start_width": width,
        "target_width": target,
        "steps": steps,
        "final_width": current,
    }
