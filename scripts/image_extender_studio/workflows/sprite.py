"""Sprite 动画表处理工作流。

本模块负责 pose guide、色键切帧、低 alpha 残边清理、主体 bbox 计算、
脚底基线和水平锚点对齐，以及 grid/strip/manifest/zip 导出。
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from image_extender_studio.core.constants import (
    ANIM_DEFAULTS,
    BODY_PLAN_ANIMS,
    KEY_MAGENTA,
    SPRITE_FRAME_COUNT,
    SPRITE_FRAME_SIZE,
    SPRITE_GRID_COLS,
    SPRITE_GRID_ROWS,
)
from image_extender_studio.core.io import read_json_file, require_pillow, write_json
from image_extender_studio.core.models import SpriteAlignmentOptions
from image_extender_studio.imaging.common import (
    chroma_key_image,
    load_rgba,
    make_zip,
    save_rgba,
    slice_grid,
)


def build_sprite_guide(body_plan: str, anim: str, output: str) -> dict[str, Any]:
    """生成 4×2 pose guide，用确定性线框限制 sprite sheet 构图。"""
    Image, _, ImageDraw = require_pillow()
    width = SPRITE_GRID_COLS * SPRITE_FRAME_SIZE
    height = SPRITE_GRID_ROWS * SPRITE_FRAME_SIZE
    img = Image.new("RGBA", (width, height), KEY_MAGENTA)
    draw = ImageDraw.Draw(img)
    for frame in range(SPRITE_FRAME_COUNT):
        col = frame % SPRITE_GRID_COLS
        row = frame // SPRITE_GRID_COLS
        ox = col * SPRITE_FRAME_SIZE
        oy = row * SPRITE_FRAME_SIZE
        phase = frame / SPRITE_FRAME_COUNT
        draw_pose_cell(draw, ox, oy, SPRITE_FRAME_SIZE, body_plan, anim, phase)
    save_rgba(img, output)
    return {
        "output": output,
        "body_plan": body_plan,
        "anim": anim,
        "frame_size": SPRITE_FRAME_SIZE,
    }


def draw_pose_cell(
    draw: Any, ox: int, oy: int, size: int, body_plan: str, anim: str, phase: float
) -> None:
    """在单个 sprite cell 中绘制简化体型线框。"""
    cx = ox + size // 2
    floor = oy + int(size * 0.82)
    ink = (35, 35, 35, 255)
    light = (210, 210, 210, 255)
    bob = int(math.sin(phase * math.tau) * 18)

    # 每个体型使用不同的几何语言，给图像模型稳定的结构提示。
    if body_plan == "quadruped":
        y = floor - 150 + bob
        draw.ellipse((cx - 145, y - 45, cx + 115, y + 45), outline=ink, width=8)
        draw.ellipse((cx + 95, y - 55, cx + 170, y + 15), outline=ink, width=8)
        for offset in [-95, -40, 45, 95]:
            foot_x = cx + offset + int(math.sin((phase + offset / 200) * math.tau) * 22)
            draw.line((cx + offset, y + 40, foot_x, floor), fill=ink, width=8)
        draw.line((cx - 145, y - 5, cx - 210, y + 30), fill=ink, width=8)
    elif body_plan == "serpent":
        points = []
        for i in range(10):
            x = ox + 65 + i * 42
            y = oy + size // 2 + int(math.sin(i * 0.9 + phase * math.tau) * 65)
            points.append((x, y))
        draw.line(points, fill=ink, width=18, joint="curve")
        hx, hy = points[-1]
        draw.ellipse((hx - 28, hy - 22, hx + 42, hy + 22), outline=ink, width=8)
    elif body_plan == "flyer":
        y = oy + size // 2 + bob
        draw.ellipse((cx - 45, y - 35, cx + 55, y + 35), outline=ink, width=8)
        wing = int(math.sin(phase * math.tau) * 70)
        draw.polygon(
            [(cx - 25, y), (cx - 190, y - 90 - wing), (cx - 95, y + 35)],
            outline=ink,
            fill=None,
        )
        draw.polygon(
            [(cx + 15, y), (cx + 180, y - 90 - wing), (cx + 95, y + 35)],
            outline=light,
            fill=None,
        )
        draw.ellipse((cx + 50, y - 25, cx + 105, y + 20), outline=ink, width=8)
    elif body_plan == "blob":
        squash = math.sin(phase * math.tau)
        w = int(150 + squash * 25)
        h = int(130 - squash * 25)
        draw.ellipse((cx - w // 2, floor - h, cx + w // 2, floor), outline=ink, width=8)
        draw.ellipse((cx + 25, floor - h + 45, cx + 40, floor - h + 60), fill=ink)
    else:
        hip = floor - 150 + bob
        head_y = hip - 150
        draw.ellipse((cx - 35, head_y - 35, cx + 35, head_y + 35), outline=ink, width=8)
        draw.line((cx, head_y + 35, cx, hip), fill=ink, width=8)
        swing = math.sin(phase * math.tau) * 55
        draw.line((cx, hip, cx - 55 + swing, floor), fill=ink, width=8)
        draw.line((cx, hip, cx + 55 - swing, floor), fill=ink, width=8)
        draw.line((cx, head_y + 75, cx - 70 - swing, hip - 20), fill=ink, width=8)
        draw.line((cx, head_y + 75, cx + 70 + swing, hip - 20), fill=ink, width=8)


def process_sprite_sheet(
    sheet_path: str,
    output_dir: str,
    body_plan: str,
    anim: str,
    alignment: SpriteAlignmentOptions | None = None,
) -> dict[str, Any]:
    """处理 sprite sheet：切片、色键、主图隔离、归一化、导出 grid/strip。"""
    Image, _, _ = require_pillow()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    sheet = load_rgba(sheet_path)
    frames = [
        chroma_key_image(cell)
        for cell in slice_grid(
            sheet, SPRITE_GRID_COLS, SPRITE_GRID_ROWS, SPRITE_FRAME_SIZE
        )
    ]
    frames, alignment_report = normalize_sprite_frames(
        frames, alignment or SpriteAlignmentOptions()
    )

    frame_entries = []
    for i, frame in enumerate(frames):
        name = f"frame_{i + 1:02d}.png"
        save_rgba(frame, out / name)
        frame_entries.append(
            {
                "index": i,
                "file": name,
                "x": (i % 4) * SPRITE_FRAME_SIZE,
                "y": (i // 4) * SPRITE_FRAME_SIZE,
            }
        )

    grid = Image.new(
        "RGBA",
        (SPRITE_GRID_COLS * SPRITE_FRAME_SIZE, SPRITE_GRID_ROWS * SPRITE_FRAME_SIZE),
        (0, 0, 0, 0),
    )
    strip = Image.new(
        "RGBA",
        (SPRITE_FRAME_COUNT * SPRITE_FRAME_SIZE, SPRITE_FRAME_SIZE),
        (0, 0, 0, 0),
    )
    for i, frame in enumerate(frames):
        grid.paste(
            frame, ((i % 4) * SPRITE_FRAME_SIZE, (i // 4) * SPRITE_FRAME_SIZE), frame
        )
        strip.paste(frame, (i * SPRITE_FRAME_SIZE, 0), frame)
    save_rgba(grid, out / "sprite-grid.png")
    save_rgba(strip, out / "sprite-strip.png")
    spec = ANIM_DEFAULTS.get(anim, {"fps": 12, "loop": True})
    manifest = {
        "body_plan": body_plan,
        "anim": anim,
        "fps": spec["fps"],
        "loop": spec["loop"],
        "frame_size": SPRITE_FRAME_SIZE,
        "grid": "sprite-grid.png",
        "strip": "sprite-strip.png",
        "frames": frame_entries,
        "alignment": alignment_report,
    }
    write_json(out / "manifest.json", manifest)
    return manifest


def normalize_sprite_frames(
    frames: list[Any], options: SpriteAlignmentOptions
) -> tuple[list[Any], dict[str, Any]]:
    """把 sprite 帧按稳定主体锚点和脚底基线对齐。

    旧版直接使用整帧 alpha bbox，披风、裙摆、武器或低 alpha 残边都会
    进入 bbox，导致角色主体在动画中左右抖动或上下漂移。这里先清理
    残边，再用高 alpha + 行列最少像素数计算主体 bbox，最后用上身
    分位数锚点对齐视觉重心。
    """
    Image, _, _ = require_pillow()
    cleaned_frames = [
        clean_sprite_alpha(frame, options.alpha_floor) for frame in frames
    ]
    source_metrics = [measure_sprite_frame(frame, options) for frame in cleaned_frames]
    valid = [metric for metric in source_metrics if metric["bbox"]]
    if not valid:
        return cleaned_frames, {
            "vertical_anchor": options.vertical_anchor,
            "horizontal_anchor": options.horizontal_anchor,
            "alpha_threshold": options.alpha_threshold,
            "alpha_floor": options.alpha_floor,
            "frames": source_metrics,
        }

    baselines = [
        metric["baseline"] for metric in valid if metric["baseline"] is not None
    ]
    anchors = [metric["anchor_x"] for metric in valid if metric["anchor_x"] is not None]
    target_baseline = (
        max(baselines) if options.vertical_anchor == "baseline" and baselines else None
    )
    target_anchor = (
        median_number(anchors)
        if options.horizontal_anchor != "none" and anchors
        else None
    )
    normalized = []
    report_frames = []
    for index, (frame, metric) in enumerate(zip(cleaned_frames, source_metrics)):
        if not metric["bbox"]:
            normalized.append(frame)
            report_frames.append(
                {
                    "index": index,
                    **metric,
                    "dx": 0,
                    "dy": 0,
                    "aligned_bbox": None,
                    "aligned_baseline": None,
                    "aligned_anchor_x": None,
                }
            )
            continue

        dx = (
            int(round(float(target_anchor) - float(metric["anchor_x"])))
            if target_anchor is not None and metric["anchor_x"] is not None
            else 0
        )
        dy = (
            int(round(float(target_baseline) - float(metric["baseline"])))
            if target_baseline is not None and metric["baseline"] is not None
            else 0
        )
        aligned = shift_sprite_frame(frame, dx, dy)
        aligned_metric = measure_sprite_frame(aligned, options)
        normalized.append(aligned)
        report_frames.append(
            {
                "index": index,
                **metric,
                "dx": dx,
                "dy": dy,
                "aligned_bbox": aligned_metric["bbox"],
                "aligned_baseline": aligned_metric["baseline"],
                "aligned_anchor_x": aligned_metric["anchor_x"],
            }
        )

    return normalized, {
        "vertical_anchor": options.vertical_anchor,
        "horizontal_anchor": options.horizontal_anchor,
        "alpha_threshold": options.alpha_threshold,
        "alpha_floor": options.alpha_floor,
        "row_min_pixels": options.row_min_pixels,
        "col_min_pixels": options.col_min_pixels,
        "target_baseline": target_baseline,
        "target_anchor_x": target_anchor,
        "frames": report_frames,
    }


def clean_sprite_alpha(image: Any, alpha_floor: int) -> Any:
    """清理低 alpha 残边，避免去底噪点被当作脚底或外轮廓。"""
    if alpha_floor <= 0:
        return image.copy()
    result = image.copy()
    pix = result.load()
    for y in range(result.height):
        for x in range(result.width):
            r, g, b, a = pix[x, y]
            if a <= alpha_floor:
                pix[x, y] = (r, g, b, 0)
    return result


def measure_sprite_frame(image: Any, options: SpriteAlignmentOptions) -> dict[str, Any]:
    """返回单帧用于对齐的主体 bbox、脚底 baseline 和水平 anchor。"""
    box = robust_alpha_bbox(
        image, options.alpha_threshold, options.row_min_pixels, options.col_min_pixels
    )
    if not box:
        return {"bbox": None, "baseline": None, "anchor_x": None}
    anchor_x = sprite_anchor_x(
        image, box, options.horizontal_anchor, options.alpha_threshold
    )
    return {"bbox": list(box), "baseline": box[3], "anchor_x": anchor_x}


def robust_alpha_bbox(
    image: Any, threshold: int, row_min_pixels: int = 0, col_min_pixels: int = 0
) -> tuple[int, int, int, int] | None:
    """用高 alpha 和行列像素数阈值计算主体 bbox，过滤孤立噪点。"""
    pix = image.load()
    row_min = row_min_pixels or max(4, image.width // 96)
    col_min = col_min_pixels or max(4, image.height // 128)
    valid_rows: list[int] = []
    for y in range(image.height):
        count = 0
        for x in range(image.width):
            if pix[x, y][3] >= threshold:
                count += 1
        if count >= row_min:
            valid_rows.append(y)
    if not valid_rows:
        return alpha_bbox(image, threshold)

    top = min(valid_rows)
    bottom = max(valid_rows) + 1
    valid_cols: list[int] = []
    for x in range(image.width):
        count = 0
        for y in range(top, bottom):
            if pix[x, y][3] >= threshold:
                count += 1
        if count >= col_min:
            valid_cols.append(x)
    if not valid_cols:
        return alpha_bbox(image, threshold)
    return (min(valid_cols), top, max(valid_cols) + 1, bottom)


def sprite_anchor_x(
    image: Any, box: tuple[int, int, int, int], mode: str, threshold: int
) -> float | None:
    """按指定策略计算水平锚点，默认使用上身右侧分位数。"""
    if mode == "none":
        return None
    left, top, right, bottom = box
    if mode == "bbox-center":
        return (left + right) / 2

    height = max(1, bottom - top)
    if mode == "feet-center":
        y1 = top + int(height * 0.78)
        y2 = bottom
        quantile = 0.5
    else:
        quantile = anchor_mode_quantile(mode)
        y1 = top + int(height * 0.15)
        y2 = top + int(height * 0.62)

    xs = alpha_x_samples(image, y1, y2, threshold)
    if not xs:
        return (left + right) / 2
    return quantile_number(xs, quantile)


def anchor_mode_quantile(mode: str) -> float:
    """从 upper-qNN 模式名解析分位数，非法值回落到 q75。"""
    match = re.fullmatch(r"upper-q(\d{2})", mode)
    if not match:
        return 0.75
    return max(0.0, min(1.0, int(match.group(1)) / 100))


def alpha_x_samples(image: Any, y1: int, y2: int, threshold: int) -> list[int]:
    """采集指定 y 区间内的主体 alpha 像素 x 坐标。"""
    pix = image.load()
    start = max(0, min(image.height, y1))
    end = max(start, min(image.height, y2))
    xs: list[int] = []
    for y in range(start, end):
        for x in range(image.width):
            if pix[x, y][3] >= threshold:
                xs.append(x)
    return xs


def quantile_number(values: list[int] | list[float], q: float) -> float:
    """返回简单线性分位数，用于稳定 anchor 目标。"""
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def median_number(values: list[int] | list[float]) -> float:
    """返回中位数，避免单帧异常 anchor 拉偏整组目标。"""
    return quantile_number(values, 0.5)


def shift_sprite_frame(frame: Any, dx: int, dy: int) -> Any:
    """把 frame 平移到同尺寸透明画布，自动裁剪越界区域。"""
    Image, _, _ = require_pillow()
    canvas = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    dst_left = max(0, dx)
    dst_top = max(0, dy)
    dst_right = min(frame.width, dx + frame.width)
    dst_bottom = min(frame.height, dy + frame.height)
    if dst_right <= dst_left or dst_bottom <= dst_top:
        return canvas
    src_left = max(0, -dx)
    src_top = max(0, -dy)
    src_right = src_left + (dst_right - dst_left)
    src_bottom = src_top + (dst_bottom - dst_top)
    canvas.alpha_composite(
        frame.crop((src_left, src_top, src_right, src_bottom)), (dst_left, dst_top)
    )
    return canvas


def alpha_bbox(image: Any, threshold: int = 10) -> tuple[int, int, int, int] | None:
    """计算 alpha 大于阈值的紧致包围盒。"""
    pix = image.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(image.height):
        for x in range(image.width):
            if pix[x, y][3] > threshold:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def package_sprite(input_dir: str, output: str) -> dict[str, Any]:
    """把 sprite 处理目录打包成 ZIP。"""
    inp = Path(input_dir)
    manifest = read_json_file(inp / "manifest.json", default={})
    files = [inp / "manifest.json", inp / "sprite-grid.png", inp / "sprite-strip.png"]
    files.extend(inp / frame["file"] for frame in manifest.get("frames", []))
    make_zip(output, files)
    return manifest
