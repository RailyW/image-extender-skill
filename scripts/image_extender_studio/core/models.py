"""Image Extender Studio 的公开数据模型。

这些 dataclass 是模块之间传递配置的轻量契约；字段含义写在类注释中，
调用方应优先构造这些对象，而不是临时传递松散 dict。
"""

from __future__ import annotations

from dataclasses import dataclass

from image_extender_studio.core.constants import (
    SPRITE_ALIGN_ALPHA_FLOOR,
    SPRITE_ALIGN_ALPHA_THRESHOLD,
)


class SpriteAlignmentOptions:
    """保存 sprite 单帧归一化的可调参数。

    alpha_threshold 用于判断主体实像素，alpha_floor 用于剔除 AI 去底后
    常见的低透明度残边；row/col_min_pixels 为 0 时按画布尺寸自动推导。
    """

    vertical_anchor: str = "baseline"
    horizontal_anchor: str = "upper-q75"
    alpha_threshold: int = SPRITE_ALIGN_ALPHA_THRESHOLD
    alpha_floor: int = SPRITE_ALIGN_ALPHA_FLOOR
    row_min_pixels: int = 0
    col_min_pixels: int = 0


class ProviderConfig:
    """保存单类能力最终解析出的 provider 配置。"""

    capability: str
    protocol: str
    base_url: str
    model: str
    api_key: str
    name: str = ""
