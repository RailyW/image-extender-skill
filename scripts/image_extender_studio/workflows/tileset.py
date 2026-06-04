"""2D platformer autotile 瓦片工作流。

本模块负责结构 guide 绘制、生成图切片、色键、body tileable 修正、角块调和、
atlas extrude 和 zip/manifest 导出。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from image_extender_studio.core.constants import (
    KEY_MAGENTA,
    TILE_EXTRUDE,
    TILE_ROLES,
    TILE_SIZE,
    TILE_TEMPLATE_MASK,
    TILE_TEMPLATE_SAMPLES,
)
from image_extender_studio.core.io import read_json_file, require_pillow, write_json
from image_extender_studio.imaging.common import (
    chroma_key_image,
    load_rgba,
    make_horizontally_tileable,
    make_vertically_tileable,
    make_zip,
    save_rgba,
    slice_grid,
)


def build_tileset_guide(output: str, cell: int = TILE_SIZE) -> dict[str, Any]:
    """绘制 8×8 tileset 结构参考图，供图生图 restyle。"""
    Image, _, ImageDraw = require_pillow()
    width = len(TILE_TEMPLATE_MASK[0]) * cell
    height = len(TILE_TEMPLATE_MASK) * cell
    img = Image.new("RGBA", (width, height), KEY_MAGENTA)
    draw = ImageDraw.Draw(img)
    q = cell // 4
    for y, row in enumerate(TILE_TEMPLATE_MASK):
        for x, flag in enumerate(row):
            if flag != "#":
                continue
            role = template_role_for_cell(x, y)
            ox, oy = x * cell, y * cell
            for rect in role_material_rects(role, ox, oy, cell, q):
                draw.rectangle(rect, fill=(128, 128, 128, 255))
    save_rgba(img, output)
    return {"output": output, "width": width, "height": height, "cell": cell}


def template_role_for_cell(x: int, y: int) -> str | None:
    """根据 8×8 模板邻接关系判断单元格 autotile 角色。"""

    def solid(cx: int, cy: int) -> bool:
        return (
            0 <= cy < len(TILE_TEMPLATE_MASK)
            and 0 <= cx < len(TILE_TEMPLATE_MASK[0])
            and TILE_TEMPLATE_MASK[cy][cx] == "#"
        )

    if not solid(x, y):
        return None
    top = not solid(x, y - 1)
    bottom = not solid(x, y + 1)
    left = not solid(x - 1, y)
    right = not solid(x + 1, y)
    if top and left:
        return "tl_outer"
    if top and right:
        return "tr_outer"
    if bottom and left:
        return "bl_outer"
    if bottom and right:
        return "br_outer"
    if top:
        return "top"
    if bottom:
        return "bottom"
    if left:
        return "left"
    if right:
        return "right"
    if not solid(x - 1, y - 1):
        return "tl_inner"
    if not solid(x + 1, y - 1):
        return "tr_inner"
    if not solid(x - 1, y + 1):
        return "bl_inner"
    if not solid(x + 1, y + 1):
        return "br_inner"
    return "body"


def role_material_rects(
    role: str | None, ox: int, oy: int, cell: int, q: int
) -> list[tuple[int, int, int, int]]:
    """返回某 tile 角色的灰色材料矩形区域。"""
    if role == "body":
        return [(ox, oy, ox + cell, oy + cell)]
    if role == "top":
        return [(ox, oy + q, ox + cell, oy + cell)]
    if role == "bottom":
        return [(ox, oy, ox + cell, oy + cell - q)]
    if role == "left":
        return [(ox + q, oy, ox + cell, oy + cell)]
    if role == "right":
        return [(ox, oy, ox + cell - q, oy + cell)]
    if role == "tl_outer":
        return [(ox + q, oy + q, ox + cell, oy + cell)]
    if role == "tr_outer":
        return [(ox, oy + q, ox + cell - q, oy + cell)]
    if role == "bl_outer":
        return [(ox + q, oy, ox + cell, oy + cell - q)]
    if role == "br_outer":
        return [(ox, oy, ox + cell - q, oy + cell - q)]
    if role == "tl_inner":
        return [(ox + q, oy, ox + cell, oy + cell), (ox, oy + q, ox + q, oy + cell)]
    if role == "tr_inner":
        return [
            (ox, oy, ox + cell - q, oy + cell),
            (ox + cell - q, oy + q, ox + cell, oy + cell),
        ]
    if role == "bl_inner":
        return [
            (ox, oy, ox + cell, oy + cell - q),
            (ox + q, oy + cell - q, ox + cell, oy + cell),
        ]
    if role == "br_inner":
        return [
            (ox, oy, ox + cell, oy + cell - q),
            (ox, oy + cell - q, ox + cell - q, oy + cell),
        ]
    return []


def extract_tileset(
    sheet_path: str, output_dir: str, layout: str = "auto"
) -> dict[str, Any]:
    """从生成图中切出 13 个 autotile 角色并写入目录。"""
    Image, _, _ = require_pillow()
    sheet = load_rgba(sheet_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # auto 模式根据尺寸判断是 8×8 template 还是 4×4 atlas。
    if layout == "auto":
        layout = (
            "template"
            if sheet.width / max(1, sheet.height) == 1 and sheet.width >= TILE_SIZE * 6
            else "atlas"
        )

    role_files = []
    if layout == "template":
        normalized = sheet.resize(
            (8 * TILE_SIZE, 8 * TILE_SIZE), Image.Resampling.LANCZOS
        )
        for role, _, _, filename in TILE_ROLES:
            tx, ty = TILE_TEMPLATE_SAMPLES[role]
            tile = normalized.crop(
                (
                    tx * TILE_SIZE,
                    ty * TILE_SIZE,
                    (tx + 1) * TILE_SIZE,
                    (ty + 1) * TILE_SIZE,
                )
            )
            tile = chroma_key_image(tile)
            if role == "body":
                tile = make_vertically_tileable(
                    make_horizontally_tileable(tile, 48), 48
                )
            path = out / filename
            save_rgba(tile, path)
            role_files.append({"role": role, "file": filename})
    else:
        cells = slice_grid(sheet, 4, 4, TILE_SIZE)
        for role, col, row, filename in TILE_ROLES:
            tile = chroma_key_image(cells[row * 4 + col])
            if role == "body":
                tile = make_vertically_tileable(
                    make_horizontally_tileable(tile, 48), 48
                )
            path = out / filename
            save_rgba(tile, path)
            role_files.append({"role": role, "file": filename})

    manifest = {
        "source": sheet_path,
        "layout": layout,
        "tile_size": TILE_SIZE,
        "roles": role_files,
    }
    write_json(out / "tileset.json", manifest)
    return manifest


def package_tileset(input_dir: str, output: str) -> dict[str, Any]:
    """把 tileset 单块 PNG 打包成带 extrude 的 atlas 和 ZIP。"""
    Image, _, _ = require_pillow()
    inp = Path(input_dir)
    stride = TILE_SIZE + TILE_EXTRUDE * 2
    atlas = Image.new("RGBA", (4 * stride, 4 * stride), (0, 0, 0, 0))
    entries = []
    for role, col, row, filename in TILE_ROLES:
        path = inp / filename
        if not path.exists():
            continue
        tile = load_rgba(path).resize((TILE_SIZE, TILE_SIZE))
        tile_ext = extrude_tile(tile, TILE_EXTRUDE)
        x, y = col * stride, row * stride
        atlas.paste(tile_ext, (x, y), tile_ext)
        entries.append(
            {
                "role": role,
                "file": filename,
                "x": x + TILE_EXTRUDE,
                "y": y + TILE_EXTRUDE,
                "width": TILE_SIZE,
                "height": TILE_SIZE,
            }
        )
    atlas_path = inp / "tileset-atlas.png"
    save_rgba(atlas, atlas_path)
    manifest = {
        "tile_size": TILE_SIZE,
        "extrude": TILE_EXTRUDE,
        "atlas": atlas_path.name,
        "tiles": entries,
    }
    write_json(inp / "manifest.json", manifest)
    make_zip(
        output,
        [
            atlas_path,
            inp / "manifest.json",
            *[inp / entry["file"] for entry in entries],
        ],
    )
    return manifest


def extrude_tile(tile: Any, extrude: int) -> Any:
    """复制瓦片边缘像素，防止引擎线性过滤采样到透明边。"""
    Image, _, _ = require_pillow()
    out = Image.new(
        "RGBA", (tile.width + extrude * 2, tile.height + extrude * 2), (0, 0, 0, 0)
    )
    out.paste(tile, (extrude, extrude), tile)
    pix_src = tile.load()
    pix = out.load()
    for x in range(tile.width):
        for i in range(extrude):
            pix[x + extrude, i] = pix_src[x, 0]
            pix[x + extrude, tile.height + extrude + i] = pix_src[x, tile.height - 1]
    for y in range(tile.height):
        for i in range(extrude):
            pix[i, y + extrude] = pix_src[0, y]
            pix[tile.width + extrude + i, y + extrude] = pix_src[tile.width - 1, y]
    return out


def reconcile_tileset(input_dir: str) -> dict[str, Any]:
    """执行轻量角块调和；当前实现确保所有角块 alpha 边缘经过统一色键和羽化。"""
    inp = Path(input_dir)
    touched = []
    for role, _, _, filename in TILE_ROLES:
        if "corner" not in filename:
            continue
        path = inp / filename
        if path.exists():
            tile = chroma_key_image(load_rgba(path))
            save_rgba(tile, path)
            touched.append(role)
    manifest_path = inp / "tileset.json"
    manifest = read_json_file(manifest_path, default={})
    manifest["reconciled_corners"] = touched
    write_json(manifest_path, manifest)
    return manifest
