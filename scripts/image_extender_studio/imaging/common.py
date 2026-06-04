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
    """把洋红背景转成透明，并对近似洋红做软 alpha。"""
    result = image.copy()
    pix = result.load()
    clear_connected_magenta_background(pix, result.width, result.height, threshold)
    for y in range(result.height):
        for x in range(result.width):
            r, g, b, a = pix[x, y]
            magenta_score = max(0, r - 180) + max(0, b - 180) + max(0, 90 - g)
            if r > 200 and b > 200 and g < threshold:
                pix[x, y] = (0, 0, 0, 0)
            elif magenta_score > 120:
                alpha = clamp(a * max(0, 1 - magenta_score / max(1, 360 + feather)))
                pix[x, y] = (r, g, b, alpha) if alpha else (0, 0, 0, 0)
    return result


def clear_connected_magenta_background(
    pix: Any, width: int, height: int, threshold: int
) -> None:
    """清除从边界连通进来的近似洋红背景。

    生成模型有时会把 #FF00FF 背景渲成轻微渐变。只扩大全局阈值会误伤
    角色身上的紫色装饰，因此这里只对边界连通区域使用宽松判定。
    """
    if width <= 0 or height <= 0:
        return

    visited = bytearray(width * height)
    stack: list[tuple[int, int]] = []

    def push(x: int, y: int) -> None:
        index = y * width + x
        if not visited[index]:
            visited[index] = 1
            stack.append((x, y))

    for x in range(width):
        push(x, 0)
        if height > 1:
            push(x, height - 1)
    for y in range(1, height - 1):
        push(0, y)
        if width > 1:
            push(width - 1, y)

    while stack:
        x, y = stack.pop()
        if not is_background_magenta(pix[x, y], threshold):
            continue
        pix[x, y] = (0, 0, 0, 0)
        if x > 0:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)


def is_background_magenta(
    pixel: tuple[int, int, int, int], threshold: int
) -> bool:
    """判断像素是否足够像洋红背景。"""
    r, g, b, a = pixel
    if a == 0:
        return True
    if r > 200 and b > 200 and g < threshold:
        return True
    return (
        r >= 180
        and b >= 160
        and g <= max(130, threshold + 50)
        and r - g >= 110
        and b - g >= 90
        and abs(r - b) <= 90
    )


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
