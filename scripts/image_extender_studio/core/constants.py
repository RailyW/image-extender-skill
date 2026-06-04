"""Image Extender Studio 的跨模块常量。

本文件集中保存 provider 默认值、画布颜色、tile/sprite/props 尺寸和
工作流枚举，避免各子流程在自己的实现里复制魔法数字。
"""

from __future__ import annotations

DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
DEFAULT_TEXT_MODEL = "google/gemini-2.0-flash-001"
DEFAULT_VISION_MODEL = "google/gemini-2.0-flash-001"
PROVIDER_PROTOCOLS = {
    "openrouter-chat-completions",
    "openai-chat-completions",
    "openai-responses",
    "openai-images",
    "codex-app-imagegen",
}
EXTENSION_BLANK = (176, 176, 176, 255)
KEY_MAGENTA = (255, 0, 255, 255)
TILE_SIZE = 512
TILE_EXTRUDE = 2
SPRITE_FRAME_SIZE = 512
SPRITE_FRAME_COUNT = 8
SPRITE_GRID_COLS = 4
SPRITE_GRID_ROWS = 2
PROP_TILE_SIZE = 512
PROP_BATCH_COLS = 4
PROP_BATCH_ROWS = 2
SPRITE_ALIGN_ALPHA_THRESHOLD = 96
SPRITE_ALIGN_ALPHA_FLOOR = 24
LAYER_SPECS = {
    "sky": {"speed": 0.05, "opaque": True, "width": 1899, "height": 768},
    "far": {"speed": 0.25, "opaque": False, "width": 1952, "height": 544},
    "mid": {"speed": 0.55, "opaque": False, "width": 1952, "height": 544},
    "near": {"speed": 1.0, "opaque": False, "width": 1952, "height": 544},
}
TILE_ROLES = [
    ("tl_outer", 0, 0, "corner-tl-outer.png"),
    ("top", 1, 0, "edge-top.png"),
    ("tr_outer", 2, 0, "corner-tr-outer.png"),
    ("tl_inner", 3, 0, "corner-tl-inner.png"),
    ("left", 0, 1, "edge-left.png"),
    ("body", 1, 1, "body.png"),
    ("right", 2, 1, "edge-right.png"),
    ("tr_inner", 3, 1, "corner-tr-inner.png"),
    ("bl_outer", 0, 2, "corner-bl-outer.png"),
    ("bottom", 1, 2, "edge-bottom.png"),
    ("br_outer", 2, 2, "corner-br-outer.png"),
    ("bl_inner", 3, 2, "corner-bl-inner.png"),
    ("br_inner", 3, 3, "corner-br-inner.png"),
]
TILE_TEMPLATE_MASK = [
    "########",
    "########",
    "########",
    "##....##",
    "##....##",
    "########",
    "########",
    "########",
]
TILE_TEMPLATE_SAMPLES = {
    "tl_outer": (0, 0),
    "top": (4, 0),
    "tr_outer": (7, 0),
    "tl_inner": (6, 5),
    "left": (0, 4),
    "body": (4, 6),
    "right": (7, 4),
    "tr_inner": (1, 5),
    "bl_outer": (0, 7),
    "bottom": (4, 7),
    "br_outer": (7, 7),
    "bl_inner": (6, 2),
    "br_inner": (1, 2),
}
ANIM_DEFAULTS = {
    "idle": {"fps": 6, "loop": True},
    "walk": {"fps": 12, "loop": True},
    "run": {"fps": 14, "loop": True},
    "jump": {"fps": 10, "loop": False},
    "attack": {"fps": 12, "loop": False},
    "hurt": {"fps": 8, "loop": False},
    "death": {"fps": 10, "loop": False},
    "pounce": {"fps": 12, "loop": False},
    "sleep": {"fps": 4, "loop": True},
    "slither": {"fps": 12, "loop": True},
    "strike": {"fps": 14, "loop": False},
    "coil": {"fps": 10, "loop": False},
    "flap": {"fps": 12, "loop": True},
    "glide": {"fps": 8, "loop": True},
    "dive": {"fps": 14, "loop": False},
    "hop": {"fps": 10, "loop": True},
    "bounce": {"fps": 12, "loop": True},
    "lunge": {"fps": 12, "loop": False},
}
BODY_PLAN_ANIMS = {
    "biped": ["idle", "walk", "run", "jump", "attack", "hurt", "death"],
    "quadruped": ["idle", "walk", "run", "jump", "pounce", "hurt", "death", "sleep"],
    "serpent": ["idle", "slither", "strike", "coil", "hurt", "death"],
    "flyer": ["idle", "flap", "glide", "dive", "hurt", "death"],
    "blob": ["idle", "hop", "bounce", "lunge", "hurt", "death"],
}
