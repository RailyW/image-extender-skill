"""Extender 扩图工作流的确定性画布和融合步骤。

本模块负责扩展画布、低频颜色预校正、羽化/近似梯度域融合和接缝评分；
图片生成本身仍由 provider 层或 Codex App imagegen 完成。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from image_extender_studio.core.constants import EXTENSION_BLANK
from image_extender_studio.core.io import require_pillow, write_json
from image_extender_studio.imaging.common import (
    clamp,
    load_rgba,
    mix_rgba,
    rgb_distance,
    save_rgba,
)


def extension_geometry(
    width: int, height: int, direction: str, amount: int
) -> tuple[tuple[int, int], tuple[int, int, int, int], tuple[int, int, int, int]]:
    """计算扩展后尺寸、原图粘贴位置和新区域矩形。"""
    if direction in {"left", "right"}:
        new_size = (width + amount, height)
        original_box = (
            (amount, 0, amount + width, height)
            if direction == "left"
            else (0, 0, width, height)
        )
        extension_box = (
            (0, 0, amount, height)
            if direction == "left"
            else (width, 0, width + amount, height)
        )
    else:
        new_size = (width, height + amount)
        original_box = (
            (0, amount, width, amount + height)
            if direction == "up"
            else (0, 0, width, height)
        )
        extension_box = (
            (0, 0, width, amount)
            if direction == "up"
            else (0, height, width, height + amount)
        )
    return new_size, original_box, extension_box


def prepare_extension_canvas(
    input_path: str, direction: str, amount: int, output: str
) -> dict[str, Any]:
    """创建带灰色空白扩展区的画布。"""
    Image, _, _ = require_pillow()
    original = load_rgba(input_path)
    new_size, original_box, extension_box = extension_geometry(
        original.width, original.height, direction, amount
    )
    canvas = Image.new("RGBA", new_size, EXTENSION_BLANK)
    canvas.paste(original, (original_box[0], original_box[1]))
    save_rgba(canvas, output)
    return {
        "input": input_path,
        "output": output,
        "direction": direction,
        "amount": amount,
        "new_size": list(new_size),
        "original_box": list(original_box),
        "extension_box": list(extension_box),
    }


def apply_extension_result(
    original_path: str,
    generated_path: str,
    direction: str,
    amount: int,
    output: str,
    blend: str,
) -> dict[str, Any]:
    """把 provider 生成的整图结果融合为最终扩图图像。"""
    original = load_rgba(original_path)
    generated = load_rgba(generated_path)
    new_size, original_box, extension_box = extension_geometry(
        original.width, original.height, direction, amount
    )

    # provider 可能返回尺寸略有偏差，这里强制归一到扩展画布尺寸。
    if generated.size != new_size:
        generated = generated.resize(new_size)

    corrected = pre_correct_extension_color(
        original, generated, direction, amount, original_box, extension_box
    )
    if blend == "poisson":
        result = poisson_like_blend(
            original, corrected, direction, amount, original_box, extension_box
        )
    else:
        result = feather_blend(
            original, corrected, direction, amount, original_box, extension_box
        )
    score = seam_score(result, direction, amount, original_box)
    save_rgba(result, output)
    manifest = {
        "original": original_path,
        "generated": generated_path,
        "output": output,
        "direction": direction,
        "amount": amount,
        "blend": blend,
        "seam_score": score,
        "width": result.width,
        "height": result.height,
    }
    write_json(Path(output).with_suffix(".json"), manifest)
    return manifest


def pre_correct_extension_color(
    original: Any,
    generated: Any,
    direction: str,
    amount: int,
    original_box: tuple[int, int, int, int],
    extension_box: tuple[int, int, int, int],
) -> Any:
    """按接缝两侧均值做低频颜色漂移预校正。"""
    result = generated.copy()
    orig_pixels = original.load()
    gen_pixels = result.load()
    original_samples: list[tuple[int, int, int]] = []
    generated_samples: list[tuple[int, int, int]] = []

    # 只采样接缝附近一列或一行，避免全图平均破坏局部颜色。
    if direction == "right":
        ox, gx = original.width - 1, original_box[2]
        for y in range(original.height):
            original_samples.append(orig_pixels[ox, y][:3])
            generated_samples.append(gen_pixels[gx, y][:3])
    elif direction == "left":
        ox, gx = 0, extension_box[2] - 1
        for y in range(original.height):
            original_samples.append(orig_pixels[ox, y][:3])
            generated_samples.append(gen_pixels[gx, y][:3])
    elif direction == "down":
        oy, gy = original.height - 1, original_box[3]
        for x in range(original.width):
            original_samples.append(orig_pixels[x, oy][:3])
            generated_samples.append(gen_pixels[x, gy][:3])
    else:
        oy, gy = 0, extension_box[3] - 1
        for x in range(original.width):
            original_samples.append(orig_pixels[x, oy][:3])
            generated_samples.append(gen_pixels[x, gy][:3])

    delta = tuple(
        int(channel_mean(original_samples, i) - channel_mean(generated_samples, i))
        for i in range(3)
    )
    x0, y0, x1, y1 = extension_box
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = gen_pixels[x, y]
            gen_pixels[x, y] = (
                clamp(r + delta[0]),
                clamp(g + delta[1]),
                clamp(b + delta[2]),
                a,
            )
    return result


def channel_mean(samples: list[tuple[int, int, int]], index: int) -> float:
    """计算 RGB 某通道均值，空样本时返回 0。"""
    if not samples:
        return 0.0
    return sum(item[index] for item in samples) / len(samples)


def feather_blend(
    original: Any,
    generated: Any,
    direction: str,
    amount: int,
    original_box: tuple[int, int, int, int],
    extension_box: tuple[int, int, int, int],
) -> Any:
    """使用确定性的羽化带融合原图与生成区域。"""
    Image, _, _ = require_pillow()
    result = Image.new("RGBA", generated.size, (0, 0, 0, 0))
    result.paste(original, (original_box[0], original_box[1]))
    pixels = result.load()
    gen = generated.load()
    x0, y0, x1, y1 = extension_box

    # 先无条件写入扩展区域，再在原图侧接缝带做交叉淡入。
    for y in range(y0, y1):
        for x in range(x0, x1):
            pixels[x, y] = gen[x, y]

    band = max(8, min(64, amount // 4))
    for i in range(band):
        t = (i + 1) / (band + 1)
        if direction == "right":
            x = original_box[2] - band + i
            for y in range(original.height):
                pixels[x, y] = mix_rgba(pixels[x, y], gen[x, y], t * 0.35)
        elif direction == "left":
            x = original_box[0] + band - i - 1
            for y in range(original.height):
                pixels[x, y] = mix_rgba(pixels[x, y], gen[x, y], t * 0.35)
        elif direction == "down":
            y = original_box[3] - band + i
            for x in range(original.width):
                pixels[x, y] = mix_rgba(pixels[x, y], gen[x, y], t * 0.35)
        else:
            y = original_box[1] + band - i - 1
            for x in range(original.width):
                pixels[x, y] = mix_rgba(pixels[x, y], gen[x, y], t * 0.35)
    return result


def poisson_like_blend(
    original: Any,
    generated: Any,
    direction: str,
    amount: int,
    original_box: tuple[int, int, int, int],
    extension_box: tuple[int, int, int, int],
) -> Any:
    """执行轻量梯度域近似融合；大图仍保持可接受运行时间。"""
    result = feather_blend(
        original, generated, direction, amount, original_box, extension_box
    )
    pix = result.load()
    gen = generated.load()
    x0, y0, x1, y1 = extension_box
    band = max(4, min(24, amount // 8))

    # 只在扩展区靠近接缝的一小条带做迭代平滑，避免纯 Python 在整张图上过慢。
    if direction in {"left", "right"}:
        xs = (
            range(max(x0, x1 - band), x1)
            if direction == "left"
            else range(x0, min(x1, x0 + band))
        )
        coords = [(x, y) for x in xs for y in range(y0 + 1, y1 - 1)]
    else:
        ys = (
            range(max(y0, y1 - band), y1)
            if direction == "up"
            else range(y0, min(y1, y0 + band))
        )
        coords = [(x, y) for y in ys for x in range(x0 + 1, x1 - 1)]

    for _ in range(40):
        updates: list[tuple[int, int, tuple[int, int, int, int]]] = []
        for x, y in coords:
            neighbors = [pix[x - 1, y], pix[x + 1, y], pix[x, y - 1], pix[x, y + 1]]
            base = gen[x, y]
            smooth = tuple(
                clamp(sum(n[i] for n in neighbors) / 4 * 0.65 + base[i] * 0.35)
                for i in range(3)
            )
            updates.append((x, y, (smooth[0], smooth[1], smooth[2], base[3])))
        for x, y, value in updates:
            pix[x, y] = value
    return result


def seam_score(
    image: Any, direction: str, amount: int, original_box: tuple[int, int, int, int]
) -> float:
    """计算接缝两侧平均 RGB 差异，分数越低越好。"""
    pix = image.load()
    diffs: list[float] = []
    if direction == "right":
        x = original_box[2] - 1
        for y in range(original_box[1], original_box[3]):
            diffs.append(rgb_distance(pix[x, y], pix[x + 1, y]))
    elif direction == "left":
        x = original_box[0]
        for y in range(original_box[1], original_box[3]):
            diffs.append(rgb_distance(pix[x, y], pix[x - 1, y]))
    elif direction == "down":
        y = original_box[3] - 1
        for x in range(original_box[0], original_box[2]):
            diffs.append(rgb_distance(pix[x, y], pix[x, y + 1]))
    else:
        y = original_box[1]
        for x in range(original_box[0], original_box[2]):
            diffs.append(rgb_distance(pix[x, y], pix[x, y - 1]))
    return round(sum(diffs) / max(1, len(diffs)), 4)
