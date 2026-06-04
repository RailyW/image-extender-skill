"""跨工作流复用的 RGBA 图像基础处理函数。

这里的函数只处理通用像素操作、切图、平铺接缝和 ZIP 打包，不关心
extender、tileset、sprite 等具体业务流程。
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Iterable

from image_extender_studio.core.io import require_pillow


def load_rgba(path: str | Path) -> Any:
    """加载图片并统一为 RGBA，供所有后处理步骤复用。"""
    Image, _, _ = require_pillow()
    return Image.open(path).convert("RGBA")


def save_rgba(image: Any, path: str | Path) -> None:
    """保存 RGBA PNG，并自动创建父目录。"""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def rgb_distance(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """返回两个像素的 RGB 平均绝对差。"""
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])) / 3


def mix_rgba(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int], t: float
) -> tuple[int, int, int, int]:
    """按 t 混合两个 RGBA 像素。"""
    return tuple(clamp(a[i] * (1 - t) + b[i] * t) for i in range(4))


def clamp(value: float) -> int:
    """把数值限制到 8-bit 通道范围。"""
    return max(0, min(255, int(round(value))))


def chroma_key_image(image: Any, threshold: int = 80, feather: int = 24) -> Any:
    """把纯洋红背景转成透明，并对近似洋红做软 alpha。"""
    result = image.copy()
    pix = result.load()
    for y in range(result.height):
        for x in range(result.width):
            r, g, b, a = pix[x, y]
            magenta_score = max(0, r - 180) + max(0, b - 180) + max(0, 90 - g)
            if r > 200 and b > 200 and g < threshold:
                pix[x, y] = (r, g, b, 0)
            elif magenta_score > 120:
                alpha = clamp(a * max(0, 1 - magenta_score / max(1, 360 + feather)))
                pix[x, y] = (r, g, b, alpha)
    return result


def make_horizontally_tileable(image: Any, band: int = 64) -> Any:
    """通过边缘交叉淡化修复水平 repeat-x 接缝。"""
    result = image.copy()
    pix = result.load()
    band = max(1, min(band, image.width // 4))
    for i in range(band):
        t = (i + 1) / (band + 1)
        lx = i
        rx = image.width - band + i
        for y in range(image.height):
            left = pix[lx, y]
            right = pix[rx, y]
            mixed = mix_rgba(left, right, 0.5)
            pix[lx, y] = mix_rgba(left, mixed, t)
            pix[rx, y] = mix_rgba(right, mixed, 1 - t)
    return result


def make_vertically_tileable(image: Any, band: int = 64) -> Any:
    """通过边缘交叉淡化修复垂直 repeat-y 接缝。"""
    result = image.copy()
    pix = result.load()
    band = max(1, min(band, image.height // 4))
    for i in range(band):
        t = (i + 1) / (band + 1)
        ty = i
        by = image.height - band + i
        for x in range(image.width):
            top = pix[x, ty]
            bottom = pix[x, by]
            mixed = mix_rgba(top, bottom, 0.5)
            pix[x, ty] = mix_rgba(top, mixed, t)
            pix[x, by] = mix_rgba(bottom, mixed, 1 - t)
    return result


def harmonize_horizontal(image: Any, strength: float = 0.35) -> Any:
    """按列均值拉平多次横向扩展累积出的亮度/色相面板漂移。"""
    result = image.copy()
    pix = result.load()
    means: list[tuple[float, float, float]] = []
    for x in range(result.width):
        samples = [pix[x, y] for y in range(result.height) if pix[x, y][3] > 20]
        if samples:
            means.append(tuple(sum(p[i] for p in samples) / len(samples) for i in range(3)))  # type: ignore[arg-type]
        else:
            means.append((0.0, 0.0, 0.0))
    global_mean = tuple(sum(m[i] for m in means) / max(1, len(means)) for i in range(3))
    for x in range(result.width):
        delta = tuple((global_mean[i] - means[x][i]) * strength for i in range(3))
        for y in range(result.height):
            r, g, b, a = pix[x, y]
            if a > 20:
                pix[x, y] = (
                    clamp(r + delta[0]),
                    clamp(g + delta[1]),
                    clamp(b + delta[2]),
                    a,
                )
    return result


def slice_grid(image: Any, cols: int, rows: int, cell: int) -> list[Any]:
    """把图像归一到 cols×rows 网格并按行优先切片。"""
    Image, _, _ = require_pillow()
    normalized = image.resize((cols * cell, rows * cell), Image.Resampling.LANCZOS)
    cells = []
    for row in range(rows):
        for col in range(cols):
            cells.append(
                normalized.crop(
                    (col * cell, row * cell, (col + 1) * cell, (row + 1) * cell)
                )
            )
    return cells


def make_zip(output: str | Path, files: Iterable[Path]) -> None:
    """创建 ZIP 包，自动跳过不存在文件但保持相对文件名。"""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            if file.exists():
                zf.write(file, arcname=file.name)
