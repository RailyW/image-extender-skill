"""透明 props 资产库处理工作流。

本模块负责 4x2 props sheet 的切片、洋红色键控、稳定命名、atlas 构建、
manifest 和 zip 打包；props 创意列表由 prompts 模块提供。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from image_extender_studio.core.constants import (
    PROP_BATCH_COLS,
    PROP_BATCH_ROWS,
    PROP_TILE_SIZE,
)
from image_extender_studio.core.io import (
    read_json_file,
    require_pillow,
    slugify,
    write_json,
)
from image_extender_studio.imaging.common import (
    chroma_key_image,
    load_rgba,
    make_zip,
    save_rgba,
    slice_grid,
)
from image_extender_studio.prompts.builders import read_prop_ideas


def process_props_sheet(
    sheet_path: str, ideas_path: str | None, output_dir: str
) -> dict[str, Any]:
    """处理 props sheet：切成 8 格、色键、命名并生成 manifest。"""
    Image, _, _ = require_pillow()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ideas = read_prop_ideas(ideas_path)[: PROP_BATCH_COLS * PROP_BATCH_ROWS]
    sheet = load_rgba(sheet_path)
    cells = [
        chroma_key_image(cell)
        for cell in slice_grid(sheet, PROP_BATCH_COLS, PROP_BATCH_ROWS, PROP_TILE_SIZE)
    ]
    entries = []
    for i, cell in enumerate(cells[: len(ideas) or len(cells)]):
        idea = (
            ideas[i]
            if i < len(ideas)
            else {"category": f"prop_{i + 1}", "description": f"prop {i + 1}"}
        )
        stem = slugify(
            idea.get("category") or idea.get("description") or f"prop_{i + 1}",
            f"prop_{i + 1}",
        )
        filename = f"{stem}_{i + 1:02d}.png"
        save_rgba(cell, out / filename)
        entries.append(
            {
                "name": idea.get("category", stem),
                "description": idea.get("description", ""),
                "file": filename,
            }
        )
    manifest = {"tile_size": PROP_TILE_SIZE, "props": entries}
    write_json(out / "manifest.json", manifest)
    return manifest


def package_props(input_dir: str, output: str, cols: int = 4) -> dict[str, Any]:
    """把 props 目录打包为透明 atlas、manifest 和 ZIP。"""
    Image, _, _ = require_pillow()
    inp = Path(input_dir)
    manifest = read_json_file(inp / "manifest.json", default={})
    props = manifest.get("props", [])
    rows = max(1, math.ceil(len(props) / cols))
    atlas = Image.new(
        "RGBA", (cols * PROP_TILE_SIZE, rows * PROP_TILE_SIZE), (0, 0, 0, 0)
    )
    for i, prop in enumerate(props):
        img = load_rgba(inp / prop["file"]).resize((PROP_TILE_SIZE, PROP_TILE_SIZE))
        x = (i % cols) * PROP_TILE_SIZE
        y = (i // cols) * PROP_TILE_SIZE
        atlas.paste(img, (x, y), img)
        prop["atlas"] = {
            "x": x,
            "y": y,
            "width": PROP_TILE_SIZE,
            "height": PROP_TILE_SIZE,
        }
    save_rgba(atlas, inp / "props-atlas.png")
    manifest["atlas"] = "props-atlas.png"
    write_json(inp / "manifest.json", manifest)
    make_zip(
        output,
        [
            inp / "manifest.json",
            inp / "props-atlas.png",
            *[inp / prop["file"] for prop in props],
        ],
    )
    return manifest
