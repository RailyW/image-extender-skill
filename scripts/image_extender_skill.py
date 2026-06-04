#!/usr/bin/env python3
"""Image Extender Studio Skill 的确定性执行脚本。

这个脚本把原 Web 工作台中需要稳定复用的步骤搬到 Python：
provider 适配、prompt 生成、扩图画布、接缝融合、色键、切图、导出、
manifest 生成和覆盖审计。Skill 的 Markdown 只负责选择和编排这些入口。
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import mimetypes
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent

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


@dataclass
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


@dataclass
class ProviderConfig:
    """保存单类能力最终解析出的 provider 配置。"""

    capability: str
    protocol: str
    base_url: str
    model: str
    api_key: str
    name: str = ""


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


def load_provider_file(path: str | None) -> dict[str, Any]:
    """读取 provider JSON 配置，并兼容不存在配置文件的情况。"""
    data = read_json_file(path, default={})
    if not isinstance(data, dict):
        raise SystemExit("provider 配置必须是 JSON object")
    return data


def resolve_provider(capability: str, args: argparse.Namespace) -> ProviderConfig:
    """按 CLI、JSON、环境变量、旧 OpenRouter key 的顺序解析 provider。"""
    config = load_provider_file(getattr(args, "config", None))
    slot = config.get(capability, {}) if isinstance(config.get(capability, {}), dict) else {}
    prefix = capability.upper()

    # CLI 参数只在对应字段非空时覆盖，便于同一配置文件复用于多能力调用。
    cli_protocol = getattr(args, f"{capability}_protocol", None)
    cli_base_url = getattr(args, f"{capability}_base_url", None)
    cli_model = getattr(args, f"{capability}_model", None)
    cli_api_key = getattr(args, f"{capability}_api_key", None)

    protocol = (
        cli_protocol
        or os.environ.get(f"{prefix}_PROVIDER_PROTOCOL")
        or slot.get("protocol")
        or ("openrouter-chat-completions" if capability != "imagegen" else "codex-app-imagegen")
    )
    if protocol not in PROVIDER_PROTOCOLS:
        raise SystemExit(f"不支持的 provider protocol: {protocol}")

    base_url = (
        cli_base_url
        or os.environ.get(f"{prefix}_PROVIDER_BASE_URL")
        or slot.get("base_url")
        or slot.get("baseUrl")
        or DEFAULT_OPENROUTER_BASE
    ).rstrip("/")

    key_env = slot.get("api_key_env") or slot.get("apiKeyEnv")
    api_key = (
        cli_api_key
        or os.environ.get(f"{prefix}_PROVIDER_API_KEY")
        or slot.get("api_key")
        or slot.get("apiKey")
        or (os.environ.get(str(key_env)) if key_env else "")
        or os.environ.get("OPENROUTER_API_KEY")
        or ""
    )

    default_model = {
        "image": DEFAULT_IMAGE_MODEL,
        "text": DEFAULT_TEXT_MODEL,
        "vision": DEFAULT_VISION_MODEL,
    }.get(capability, DEFAULT_IMAGE_MODEL)
    model = cli_model or os.environ.get(f"{prefix}_PROVIDER_MODEL") or slot.get("model") or default_model

    return ProviderConfig(
        capability=capability,
        protocol=protocol,
        base_url=base_url,
        model=model,
        api_key=api_key,
        name=str(slot.get("name") or capability),
    )


def build_headers(provider: ProviderConfig, title: str) -> dict[str, str]:
    """按协议构造 HTTP header；OpenRouter 需要额外来源信息。"""
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    if provider.protocol == "openrouter-chat-completions":
        headers["HTTP-Referer"] = "http://localhost:3000"
        headers["X-Title"] = title
    return headers


def post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> Any:
    """使用标准库发送 JSON POST，避免 Skill 依赖额外 HTTP 包。"""
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"provider HTTP {exc.code}: {short_provider_error(text)}") from exc


def short_provider_error(text: str) -> str:
    """从 provider 错误体中提取短消息，避免输出大段响应。"""
    try:
        data = json.loads(text)
        return str(data.get("error", {}).get("message") or data.get("message") or text[:500])
    except Exception:
        return text[:500]


def as_data_url(path: str | Path) -> str:
    """把本地图片转成 data URL，供 OpenAI-compatible 图像输入使用。"""
    p = Path(path)
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def normalize_image_inputs(paths: Iterable[str]) -> list[str]:
    """把本地路径转成 data URL，保留已有 HTTP URL 或 data URL。"""
    result: list[str] = []
    for item in paths:
        if item.startswith("http://") or item.startswith("https://") or item.startswith("data:image"):
            result.append(item)
        else:
            result.append(as_data_url(item))
    return result


def build_chat_text_body(provider: ProviderConfig, system_prompt: str, user_content: Any, max_tokens: int, temperature: float) -> dict[str, Any]:
    """构造 OpenAI-compatible chat 文本/视觉请求体。"""
    return {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


def responses_content(content: Any) -> list[dict[str, Any]]:
    """把 chat content 转成 Responses API 使用的 input_text/input_image 结构。"""
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    converted: list[dict[str, Any]] = []
    for part in content:
        if part.get("type") == "image_url":
            converted.append({"type": "input_image", "image_url": part["image_url"]["url"]})
        else:
            converted.append({"type": "input_text", "text": part.get("text", "")})
    return converted


def call_text_provider(provider: ProviderConfig, system_prompt: str, user_content: Any, title: str, max_tokens: int = 800, temperature: float = 0.4) -> str:
    """调用文本或视觉 provider，并返回提取后的纯文本。"""
    if provider.protocol == "codex-app-imagegen":
        raise SystemExit("codex-app-imagegen 只用于图片生成，不能作为 text/vision provider")
    if not provider.api_key:
        raise SystemExit(f"{provider.capability} provider 缺少 API key")

    # Responses 与 chat 的 body 和 endpoint 不同，因此在这里分支，而不是让调用方感知。
    if provider.protocol == "openai-responses":
        endpoint = "/responses"
        body = {
            "model": provider.model,
            "instructions": system_prompt,
            "input": [{"role": "user", "content": responses_content(user_content)}],
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
    else:
        endpoint = "/chat/completions"
        body = build_chat_text_body(provider, system_prompt, user_content, max_tokens, temperature)

    data = post_json(f"{provider.base_url}{endpoint}", build_headers(provider, title), body)
    return extract_text(data)


def call_image_provider(provider: ProviderConfig, prompt: str, input_images: list[str], width: int, height: int, title: str, temperature: float = 0.4, force_edit: bool = False) -> str:
    """调用图片 provider，并返回 URL 或 data URL。"""
    if provider.protocol == "codex-app-imagegen":
        raise SystemExit("Codex App imagegen 需要由 Skill 调用 $imagegen，脚本只负责生成 prompt 和后处理")
    if not provider.api_key:
        raise SystemExit("image provider 缺少 API key")
    if provider.protocol == "openai-images" and input_images:
        raise SystemExit("openai-images 只支持纯文生图；带输入图请使用 openai-responses 或 chat image 协议")

    # 按协议构建请求体，兼容 OpenRouter、Responses 与 Images API。
    if provider.protocol == "openai-responses":
        endpoint = "/responses"
        body = {
            "model": provider.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        *[{"type": "input_image", "image_url": url} for url in input_images],
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
            "tools": [
                {
                    "type": "image_generation",
                    "action": "edit" if force_edit or input_images else "generate",
                    "size": f"{max(256, int(width))}x{max(256, int(height))}",
                }
            ],
            "tool_choice": {"type": "image_generation"},
            "temperature": temperature,
        }
    elif provider.protocol == "openai-images":
        endpoint = "/images/generations"
        body = {
            "model": provider.model,
            "prompt": prompt,
            "size": f"{max(256, int(width))}x{max(256, int(height))}",
            "n": 1,
        }
    else:
        endpoint = "/chat/completions"
        body = {
            "model": provider.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        *[{"type": "image_url", "image_url": {"url": url}} for url in input_images],
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 2000,
            "temperature": temperature,
        }
        if provider.protocol == "openrouter-chat-completions":
            body["modalities"] = ["image", "text"]
            body["image_config"] = {"aspect_ratio": supported_aspect_ratio(width, height)}

    data = post_json(f"{provider.base_url}{endpoint}", build_headers(provider, title), body)
    image = extract_image(data)
    if not image:
        raise SystemExit("provider 响应中没有可提取图片")
    return image


def extract_text(node: Any) -> str:
    """从 OpenRouter/OpenAI/Responses 的常见响应结构中提取文本。"""
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, list):
        return "".join(extract_text(item) for item in node).strip()
    if not isinstance(node, dict):
        return ""

    # Responses API 的 output_text 是最直接路径。
    if isinstance(node.get("output_text"), str):
        return node["output_text"].strip()
    if isinstance(node.get("output"), list):
        return "".join(extract_text(item) for item in node["output"]).strip()
    if isinstance(node.get("choices"), list):
        return "".join(extract_text(choice.get("message", choice)) for choice in node["choices"]).strip()

    content = node.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
        return "".join(parts).strip()
    return ""


def extract_image(node: Any) -> str | None:
    """从多种 provider 响应结构中提取第一张图片 URL 或 data URL。"""
    if node is None:
        return None
    if isinstance(node, str):
        if node.startswith("data:image") or node.startswith("http"):
            return node
        if len(node) > 100 and re.match(r"^[A-Za-z0-9+/=]+$", node[:100]):
            return "data:image/png;base64," + node
        return None
    if isinstance(node, list):
        for item in node:
            found = extract_image(item)
            if found:
                return found
        return None
    if not isinstance(node, dict):
        return None

    # Images API 通常返回 data 数组，Responses 图片工具返回 image_generation_call。
    for key in ("data", "output", "choices", "images"):
        if isinstance(node.get(key), list):
            for item in node[key]:
                found = extract_image(item.get("message", item) if isinstance(item, dict) else item)
                if found:
                    return found

    if node.get("type") == "image_generation_call" and node.get("result"):
        return "data:image/png;base64," + str(node["result"])
    if isinstance(node.get("url"), str):
        return node["url"]
    if isinstance(node.get("b64_json"), str):
        return "data:image/png;base64," + node["b64_json"]
    if isinstance(node.get("image_url"), dict) and isinstance(node["image_url"].get("url"), str):
        return node["image_url"]["url"]
    if isinstance(node.get("inline_data"), dict) and node["inline_data"].get("data"):
        mime = node["inline_data"].get("mime_type") or "image/png"
        return f"data:{mime};base64,{node['inline_data']['data']}"
    return extract_image(node.get("content"))


def save_image_payload(image: str, output: str | Path) -> None:
    """把 provider 返回的 data URL、HTTP URL 或本地路径保存成文件。"""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if image.startswith("data:image"):
        _, encoded = image.split(",", 1)
        out.write_bytes(base64.b64decode(encoded))
    elif image.startswith("http://") or image.startswith("https://"):
        with urllib.request.urlopen(image, timeout=300) as response:
            out.write_bytes(response.read())
    else:
        shutil.copyfile(image, out)


def supported_aspect_ratio(width: int, height: int) -> str:
    """把任意尺寸映射到 OpenRouter 图片模型支持的近似比例。"""
    target = width / max(1, height)
    ratios = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
    return min(ratios, key=lambda item: abs(math.log((int(item.split(":")[0]) / int(item.split(":")[1])) / target)))


def art_style_line(style: str | None) -> str:
    """把 UI 风格 id 转成短文本；未知风格直接返回空。"""
    styles = {
        "cinematic": "cinematic photography with dramatic lighting and film grain",
        "oil-painting": "oil painting style with visible brush strokes and rich textures",
        "watercolor": "watercolor painting with soft washes and flowing colors",
        "pixel-art": "pixel art style with retro video game aesthetics",
        "digital-art": "digital art with smooth gradients and modern aesthetics",
        "anime": "anime/manga style with bold lines and vibrant colors",
        "cartoon": "cartoon illustration with exaggerated features",
        "studio-ghibli": "Studio Ghibli animation style with whimsical hand-drawn aesthetics",
        "fantasy": "fantasy art with magical and ethereal elements",
        "sci-fi": "science fiction with futuristic technology and environments",
    }
    if style and style in styles:
        return f"Create in {styles[style]}. "
    return ""


def build_generate_prompt(args: argparse.Namespace) -> str:
    """按目标模式生成稳定的图片生成 prompt。"""
    prompt = args.prompt.strip()
    style = art_style_line(getattr(args, "art_style", None))
    scene = read_text(getattr(args, "scene_brief", None)).strip()

    if args.mode == "parallax":
        return build_parallax_prompt(prompt, args.layer, style, scene)
    if args.mode == "tileset":
        return build_tileset_prompt(prompt, style, scene, read_text(getattr(args, "fix_notes", None)).strip())
    if args.mode == "sprite-anchor":
        return build_sprite_anchor_prompt(prompt, args.body_plan, style)
    if args.mode == "sprite-sheet":
        return build_sprite_sheet_prompt(prompt, args.body_plan, args.anim, style, read_text(getattr(args, "fix_notes", None)).strip())
    if args.mode == "props":
        ideas = read_prop_ideas(getattr(args, "ideas", None))
        return build_props_prompt(prompt, ideas, style, scene)
    return f"{style}{prompt}"


def build_parallax_prompt(prompt: str, layer: str, style: str, scene: str) -> str:
    """生成视差图层 prompt，明确每层角色和洋红色透明规则。"""
    layer_rules = {
        "sky": "Render only the opaque back sky layer. Horizontally uniform tone, top-to-bottom gradients only, no sun or moon on one side, no foreground objects.",
        "far": "Render only far distant silhouettes in the lower-middle band. Every non-element pixel must be pure flat #FF00FF for alpha keying.",
        "mid": "Render only mid-ground trees, terrain or structures. Every non-element pixel must be pure flat #FF00FF for alpha keying.",
        "near": "Render only near foreground rocks, grass, trunks or bushes along the bottom. Every non-element pixel must be pure flat #FF00FF for alpha keying.",
    }
    scene_block = f"\nShared scene direction: {scene}" if scene else ""
    return f"{style}2D side-view game parallax layer.\nLayer role: {layer}.\n{layer_rules[layer]}\nWorld prompt: {prompt}.{scene_block}\nNo text, UI, labels, or watermark."


def build_tileset_prompt(prompt: str, style: str, scene: str, fix_notes: str) -> str:
    """生成模板引导 tileset 的图生图 prompt。"""
    scene_block = f"\nShared scene direction: {scene}" if scene else ""
    fix_block = f"\nQA fix notes to correct: {fix_notes}" if fix_notes else ""
    return f"""{style}Restyle the attached structural reference image as a side-view 2D platformer autotile material.

Hard rules:
- Keep the exact same silhouette as the reference.
- Gray pixels become the material: {prompt}.
- Pure magenta #FF00FF pixels stay perfectly flat magenta for alpha keying.
- The material is one continuous surface with locked palette, scale, lighting and texture.
- No grid lines, labels, text, UI, perspective, isometric view or 3D extrusion.
- Top-facing edges may have a small cap only when the material needs it; interior body stays uniform and tile-friendly.
- Avoid pink/red-magenta inside material because chroma key removes it.
{scene_block}{fix_block}
Return the complete restyled guide image."""


def build_sprite_anchor_prompt(prompt: str, body_plan: str, style: str) -> str:
    """生成 sprite anchor prompt，用单角色参考锁定身份。"""
    poses = {
        "biped": "upright relaxed side-view standing pose, facing right, feet on an implied floor",
        "quadruped": "standing calmly on all fours in side profile, head to the right, all four feet visible",
        "serpent": "long body in a gentle readable S-curve, head at the right, tail at the left",
        "flyer": "hovering in side profile with wings spread, facing right, full wingspan visible",
        "blob": "resting rounded blob on an implied floor, eyes toward the right",
    }
    return f"""{style}Create a single definitive 2D side-view game character reference image.
Body plan: {body_plan}. Pose: {poses.get(body_plan, poses["biped"])}.
Character: {prompt}.
Background outside the character must be pure flat #FF00FF. No ground, no shadow, no text, no sheet, no multiple poses. The character must avoid pure magenta colors."""


def build_sprite_sheet_prompt(prompt: str, body_plan: str, anim: str, style: str, fix_notes: str) -> str:
    """生成 sprite sheet prompt，固定 4×2、8 帧、同身份、同基线。"""
    choreography = animation_choreography(body_plan, anim)
    fix_block = f"\nQA fix notes to correct: {fix_notes}" if fix_notes else ""
    return f"""{style}Create a 4 columns by 2 rows sprite animation sheet for a 2D side-view game.
Character: {prompt}.
Body plan: {body_plan}. Animation: {anim}.

Rules:
- Exactly 8 frames, row-major order, one character per cell.
- Pure flat #FF00FF background in every cell.
- Same character identity, palette, scale, outline weight and camera distance in every frame.
- Same facing direction: right-facing profile.
- Keep feet/baseline stable for grounded animations; preserve intended airborne frames for jump, pounce, flap, dive and hop.
- No labels, text, UI, frame numbers, shadows or duplicate characters.

Choreography:
{choreography}{fix_block}"""


def animation_choreography(body_plan: str, anim: str) -> str:
    """返回简洁但稳定的 8 帧动作说明。"""
    if anim in {"walk", "run"}:
        return "Frames 1-4 show the first half of the locomotion cycle; frames 5-8 mirror the opposite limbs. The character moves in place with no horizontal translation."
    if anim in {"idle", "sleep", "glide"}:
        return "Subtle looping motion only. Frames 1 and 8 must be near-identical so the loop is seamless."
    if anim in {"jump", "pounce", "hop", "bounce"}:
        return "Crouch or squash, launch, airborne peak, descend, land, recover. Preserve vertical motion while keeping horizontal position stable."
    if anim in {"attack", "strike", "lunge"}:
        return "Anticipation, deep wind-up, fast forward strike at max extension, follow-through, recover to ready pose."
    if anim in {"hurt", "death"}:
        return "Impact or final hit, recoil or collapse, settling frames, final recovery or defeated rest pose."
    if anim in {"slither", "flap", "coil", "dive"}:
        return "Use body-plan-specific motion: wave for serpent, wing phases for flyer, squash/stretch for blob, with stable cell placement."
    return f"Animate {body_plan} performing {anim} across exactly 8 readable keyframes."


def build_props_prompt(prompt: str, ideas: list[dict[str, str]], style: str, scene: str) -> str:
    """生成 props 4×2 sheet prompt，并固定每格对象。"""
    item_lines = []
    for index, idea in enumerate(ideas[:8], start=1):
        item_lines.append(f"{index}. {idea.get('description') or idea.get('category')}")
    scene_block = f"\nShared scene direction: {scene}" if scene else ""
    return f"""{style}Create a 4 columns by 2 rows sheet of standalone transparent decoration sprites for a side-view 2D platformer.
World / biome: {prompt}.{scene_block}

Each cell contains exactly one standalone prop on pure flat #FF00FF background. No characters, no scenes, no text, no labels, no shadows.
Paint these props in order:
{chr(10).join(item_lines)}"""


def build_extend_prompt(args: argparse.Namespace) -> str:
    """生成扩图 prompt，保持与 Web route 相同的任务约束。"""
    custom = args.prompt.strip() if args.prompt else ""
    style = art_style_line(getattr(args, "art_style", None))
    direction_words = {
        "up": "top",
        "down": "bottom",
        "left": "left side",
        "right": "right side",
    }
    dir_word = direction_words[args.direction]
    custom_block = f'\nUser request for the new area: "{custom}".' if custom else "\nContinue the existing scene naturally without adding unrelated new subjects."
    layer_block = f"\nParallax layer role: {args.layer}. Preserve its layer rules exactly." if getattr(args, "layer", None) else ""
    return f"""{style}OUTPAINTING TASK: Extend the image on the {dir_word}.
The blank extension area is filled with solid light gray #B0B0B0. Replace every gray pixel with scene content while keeping existing non-gray pixels unchanged.
Match color temperature, lighting direction, saturation, contrast, perspective, texture scale and art style at the boundary.
The seam must be invisible, with no brightness jump, color drift or texture discontinuity.{custom_block}{layer_block}
Return the complete image at the same dimensions as the input canvas."""


def format_prompt_for_emit(prompt: str, emit: str) -> str:
    """按输出目标格式化 prompt；Codex imagegen 路径使用 Markdown 包装。"""
    if emit == "codex":
        return (
            "# Codex App imagegen prompt\n\n"
            "将下面的提示词交给 `$imagegen` 生成位图；生成后再把图片交回本 Skill 的 Python 后处理命令。\n\n"
            "```text\n"
            f"{prompt.strip()}\n"
            "```\n"
        )
    return prompt


def build_scene_brief_prompt(args: argparse.Namespace) -> tuple[str, str]:
    """生成 scene brief 的 system/user prompt，供 provider 或 LLM 使用。"""
    system = """You help game designers build multi-layer parallax backgrounds. Given the prompt used for the NEAR foreground layer, write a concise SCENE BRIEF that every other layer must follow.

Rules:
- 3-5 sentences, plain text only.
- Capture setting, time of day, lighting, named palette colors, art style and mood.
- Lighting must be ambient and horizontally even because the sky will tile.
- Do not repeat the input verbatim; distill shared art direction."""
    user = f'Near foreground prompt:\n"{args.prompt.strip()}"\n\nWrite the shared scene brief.'
    return system, user


def build_prop_ideas_prompt(prompt: str, count: int, existing: list[str], scene: str, style: str) -> tuple[str, str]:
    """生成 props art director 的 JSON-only prompt。"""
    existing_text = ", ".join(existing) if existing else "none"
    system = f"""You are the ART DIRECTOR for a side-view 2D platformer decoration set.
Propose exactly {count} new standalone prop ideas.

Rules:
- Every prop must be a different kind from each other and from existing kinds.
- Reach across plants, minerals, bones, debris, tools, containers, signs, creature traces, lights and ruins.
- Output strict JSON only: {{"props":[{{"category":"single lowercase word","description":"one vivid sentence"}}]}}"""
    user = f"World / biome: {prompt}\nExisting kinds: {existing_text}\nScene brief: {scene or 'none'}\nArt style: {style or 'none'}"
    return system, user


def build_review_prompt(args: argparse.Namespace) -> tuple[str, Any]:
    """生成 tile/sprite vision QA 的 prompt 和用户内容。"""
    image_url = as_data_url(args.image) if args.image and not str(args.image).startswith(("http", "data:image")) else args.image
    if args.kind == "tile":
        text = "Review this 2D platformer autotile preview. Check transparent keying, edge consistency, seamless body tiling, palette cohesion, blur, halos and obvious grid artifacts. Return strict JSON: {\"pass\":true|false,\"score\":0-100,\"fix_notes\":\"...\"}."
    else:
        text = "Review this 2D sprite animation sheet. Check one character per cell, consistent identity, scale, baseline, facing direction, clean alpha key, no labels, and readable animation. Return strict JSON: {\"pass\":true|false,\"score\":0-100,\"fix_notes\":\"...\"}."
    user = [
        {"type": "image_url", "image_url": {"url": image_url}},
        {"type": "text", "text": text},
    ]
    return "You are a strict senior 2D game art QA reviewer. Only report painter-fixable issues.", user


def parse_jsonish(text: str) -> Any:
    """容错解析模型返回的 JSON，兼容 markdown fence 和前后说明文字。"""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    for candidate in [cleaned, slice_between(cleaned, "[", "]"), slice_between(cleaned, "{", "}")]:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            pass
    raise SystemExit("无法从模型输出中解析 JSON")


def slice_between(text: str, left: str, right: str) -> str:
    """截取第一段括号包围内容，用于模型 JSON 容错。"""
    start = text.find(left)
    end = text.rfind(right)
    if start >= 0 and end > start:
        return text[start : end + 1]
    return ""


def read_prop_ideas(path: str | None) -> list[dict[str, str]]:
    """读取 props ideas JSON，并兼容 bare array 与 {props: []}。"""
    data = read_json_file(path, default={"props": fallback_prop_ideas("", 8, [])})
    if isinstance(data, dict) and isinstance(data.get("props"), list):
        return normalize_prop_ideas(data["props"])
    if isinstance(data, list):
        return normalize_prop_ideas(data)
    return []


def normalize_prop_ideas(items: Iterable[Any]) -> list[dict[str, str]]:
    """规整模型或手写 props ideas，确保包含 category 与 description。"""
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("brief") or "").strip()
        category = str(item.get("category") or item.get("kind") or "").strip().lower()
        if description:
            result.append({"category": category or slugify(description.split()[0]), "description": description})
    return result


def fallback_prop_ideas(prompt: str, count: int, existing: list[str]) -> list[dict[str, str]]:
    """没有 text provider 时提供确定性本地创意池，保证流程仍可演示。"""
    seeds = [
        ("mushroom", "cluster of small luminous mushrooms with uneven caps"),
        ("crystal", "jagged mineral cluster catching the world's ambient light"),
        ("root", "twisted exposed root bundle with tiny soil clumps"),
        ("bone", "weathered creature rib fragment half buried in dust"),
        ("lantern", "small worn lantern with a soft colored glow"),
        ("totem", "hand-carved little totem stone with chipped markings"),
        ("barrel", "broken wooden barrel with scattered metal hoops"),
        ("shell", "spiraled shell or creature husk with subtle highlights"),
        ("sign", "crooked wooden signpost with no readable letters"),
        ("fern", "fan of layered leaves shaped for tile-map scattering"),
        ("gem", "single faceted gem shard embedded in rough base"),
        ("cloth", "torn hanging cloth scrap on a short stake"),
    ]
    used = {item.lower() for item in existing}
    ideas = []
    for category, desc in seeds:
        if category in used:
            continue
        ideas.append({"category": category, "description": f"{desc} fitting {prompt or 'the biome'}"})
        if len(ideas) >= count:
            break
    return ideas


def load_rgba(path: str | Path) -> Any:
    """加载图片并统一为 RGBA，供所有后处理步骤复用。"""
    Image, _, _ = require_pillow()
    return Image.open(path).convert("RGBA")


def save_rgba(image: Any, path: str | Path) -> None:
    """保存 RGBA PNG，并自动创建父目录。"""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def extension_geometry(width: int, height: int, direction: str, amount: int) -> tuple[tuple[int, int], tuple[int, int, int, int], tuple[int, int, int, int]]:
    """计算扩展后尺寸、原图粘贴位置和新区域矩形。"""
    if direction in {"left", "right"}:
        new_size = (width + amount, height)
        original_box = (amount, 0, amount + width, height) if direction == "left" else (0, 0, width, height)
        extension_box = (0, 0, amount, height) if direction == "left" else (width, 0, width + amount, height)
    else:
        new_size = (width, height + amount)
        original_box = (0, amount, width, amount + height) if direction == "up" else (0, 0, width, height)
        extension_box = (0, 0, width, amount) if direction == "up" else (0, height, width, height + amount)
    return new_size, original_box, extension_box


def prepare_extension_canvas(input_path: str, direction: str, amount: int, output: str) -> dict[str, Any]:
    """创建带灰色空白扩展区的画布。"""
    Image, _, _ = require_pillow()
    original = load_rgba(input_path)
    new_size, original_box, extension_box = extension_geometry(original.width, original.height, direction, amount)
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


def apply_extension_result(original_path: str, generated_path: str, direction: str, amount: int, output: str, blend: str) -> dict[str, Any]:
    """把 provider 生成的整图结果融合为最终扩图图像。"""
    original = load_rgba(original_path)
    generated = load_rgba(generated_path)
    new_size, original_box, extension_box = extension_geometry(original.width, original.height, direction, amount)

    # provider 可能返回尺寸略有偏差，这里强制归一到扩展画布尺寸。
    if generated.size != new_size:
        generated = generated.resize(new_size)

    corrected = pre_correct_extension_color(original, generated, direction, amount, original_box, extension_box)
    if blend == "poisson":
        result = poisson_like_blend(original, corrected, direction, amount, original_box, extension_box)
    else:
        result = feather_blend(original, corrected, direction, amount, original_box, extension_box)
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


def pre_correct_extension_color(original: Any, generated: Any, direction: str, amount: int, original_box: tuple[int, int, int, int], extension_box: tuple[int, int, int, int]) -> Any:
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

    delta = tuple(int(channel_mean(original_samples, i) - channel_mean(generated_samples, i)) for i in range(3))
    x0, y0, x1, y1 = extension_box
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = gen_pixels[x, y]
            gen_pixels[x, y] = (clamp(r + delta[0]), clamp(g + delta[1]), clamp(b + delta[2]), a)
    return result


def channel_mean(samples: list[tuple[int, int, int]], index: int) -> float:
    """计算 RGB 某通道均值，空样本时返回 0。"""
    if not samples:
        return 0.0
    return sum(item[index] for item in samples) / len(samples)


def feather_blend(original: Any, generated: Any, direction: str, amount: int, original_box: tuple[int, int, int, int], extension_box: tuple[int, int, int, int]) -> Any:
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


def poisson_like_blend(original: Any, generated: Any, direction: str, amount: int, original_box: tuple[int, int, int, int], extension_box: tuple[int, int, int, int]) -> Any:
    """执行轻量梯度域近似融合；大图仍保持可接受运行时间。"""
    result = feather_blend(original, generated, direction, amount, original_box, extension_box)
    pix = result.load()
    gen = generated.load()
    x0, y0, x1, y1 = extension_box
    band = max(4, min(24, amount // 8))

    # 只在扩展区靠近接缝的一小条带做迭代平滑，避免纯 Python 在整张图上过慢。
    if direction in {"left", "right"}:
        xs = range(max(x0, x1 - band), x1) if direction == "left" else range(x0, min(x1, x0 + band))
        coords = [(x, y) for x in xs for y in range(y0 + 1, y1 - 1)]
    else:
        ys = range(max(y0, y1 - band), y1) if direction == "up" else range(y0, min(y1, y0 + band))
        coords = [(x, y) for y in ys for x in range(x0 + 1, x1 - 1)]

    for _ in range(40):
        updates: list[tuple[int, int, tuple[int, int, int, int]]] = []
        for x, y in coords:
            neighbors = [pix[x - 1, y], pix[x + 1, y], pix[x, y - 1], pix[x, y + 1]]
            base = gen[x, y]
            smooth = tuple(clamp(sum(n[i] for n in neighbors) / 4 * 0.65 + base[i] * 0.35) for i in range(3))
            updates.append((x, y, (smooth[0], smooth[1], smooth[2], base[3])))
        for x, y, value in updates:
            pix[x, y] = value
    return result


def seam_score(image: Any, direction: str, amount: int, original_box: tuple[int, int, int, int]) -> float:
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


def rgb_distance(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """返回两个像素的 RGB 平均绝对差。"""
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])) / 3


def mix_rgba(a: tuple[int, int, int, int], b: tuple[int, int, int, int], t: float) -> tuple[int, int, int, int]:
    """按 t 混合两个 RGBA 像素。"""
    return tuple(clamp(a[i] * (1 - t) + b[i] * t) for i in range(4))  # type: ignore[return-value]


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
                pix[x, y] = (clamp(r + delta[0]), clamp(g + delta[1]), clamp(b + delta[2]), a)
    return result


def slice_grid(image: Any, cols: int, rows: int, cell: int) -> list[Any]:
    """把图像归一到 cols×rows 网格并按行优先切片。"""
    Image, _, _ = require_pillow()
    normalized = image.resize((cols * cell, rows * cell), Image.Resampling.LANCZOS)
    cells = []
    for row in range(rows):
        for col in range(cols):
            cells.append(normalized.crop((col * cell, row * cell, (col + 1) * cell, (row + 1) * cell)))
    return cells


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
        return 0 <= cy < len(TILE_TEMPLATE_MASK) and 0 <= cx < len(TILE_TEMPLATE_MASK[0]) and TILE_TEMPLATE_MASK[cy][cx] == "#"

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


def role_material_rects(role: str | None, ox: int, oy: int, cell: int, q: int) -> list[tuple[int, int, int, int]]:
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
        return [(ox, oy, ox + cell - q, oy + cell), (ox + cell - q, oy + q, ox + cell, oy + cell)]
    if role == "bl_inner":
        return [(ox, oy, ox + cell, oy + cell - q), (ox + q, oy + cell - q, ox + cell, oy + cell)]
    if role == "br_inner":
        return [(ox, oy, ox + cell, oy + cell - q), (ox, oy + cell - q, ox + cell - q, oy + cell)]
    return []


def extract_tileset(sheet_path: str, output_dir: str, layout: str = "auto") -> dict[str, Any]:
    """从生成图中切出 13 个 autotile 角色并写入目录。"""
    Image, _, _ = require_pillow()
    sheet = load_rgba(sheet_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # auto 模式根据尺寸判断是 8×8 template 还是 4×4 atlas。
    if layout == "auto":
        layout = "template" if sheet.width / max(1, sheet.height) == 1 and sheet.width >= TILE_SIZE * 6 else "atlas"

    role_files = []
    if layout == "template":
        normalized = sheet.resize((8 * TILE_SIZE, 8 * TILE_SIZE), Image.Resampling.LANCZOS)
        for role, _, _, filename in TILE_ROLES:
            tx, ty = TILE_TEMPLATE_SAMPLES[role]
            tile = normalized.crop((tx * TILE_SIZE, ty * TILE_SIZE, (tx + 1) * TILE_SIZE, (ty + 1) * TILE_SIZE))
            tile = chroma_key_image(tile)
            if role == "body":
                tile = make_vertically_tileable(make_horizontally_tileable(tile, 48), 48)
            path = out / filename
            save_rgba(tile, path)
            role_files.append({"role": role, "file": filename})
    else:
        cells = slice_grid(sheet, 4, 4, TILE_SIZE)
        for role, col, row, filename in TILE_ROLES:
            tile = chroma_key_image(cells[row * 4 + col])
            if role == "body":
                tile = make_vertically_tileable(make_horizontally_tileable(tile, 48), 48)
            path = out / filename
            save_rgba(tile, path)
            role_files.append({"role": role, "file": filename})

    manifest = {"source": sheet_path, "layout": layout, "tile_size": TILE_SIZE, "roles": role_files}
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
        entries.append({"role": role, "file": filename, "x": x + TILE_EXTRUDE, "y": y + TILE_EXTRUDE, "width": TILE_SIZE, "height": TILE_SIZE})
    atlas_path = inp / "tileset-atlas.png"
    save_rgba(atlas, atlas_path)
    manifest = {"tile_size": TILE_SIZE, "extrude": TILE_EXTRUDE, "atlas": atlas_path.name, "tiles": entries}
    write_json(inp / "manifest.json", manifest)
    make_zip(output, [atlas_path, inp / "manifest.json", *[inp / entry["file"] for entry in entries]])
    return manifest


def extrude_tile(tile: Any, extrude: int) -> Any:
    """复制瓦片边缘像素，防止引擎线性过滤采样到透明边。"""
    Image, _, _ = require_pillow()
    out = Image.new("RGBA", (tile.width + extrude * 2, tile.height + extrude * 2), (0, 0, 0, 0))
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
    return {"output": output, "body_plan": body_plan, "anim": anim, "frame_size": SPRITE_FRAME_SIZE}


def draw_pose_cell(draw: Any, ox: int, oy: int, size: int, body_plan: str, anim: str, phase: float) -> None:
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
        draw.polygon([(cx - 25, y), (cx - 190, y - 90 - wing), (cx - 95, y + 35)], outline=ink, fill=None)
        draw.polygon([(cx + 15, y), (cx + 180, y - 90 - wing), (cx + 95, y + 35)], outline=light, fill=None)
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


def process_sprite_sheet(sheet_path: str, output_dir: str, body_plan: str, anim: str, alignment: SpriteAlignmentOptions | None = None) -> dict[str, Any]:
    """处理 sprite sheet：切片、色键、主图隔离、归一化、导出 grid/strip。"""
    Image, _, _ = require_pillow()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    sheet = load_rgba(sheet_path)
    frames = [chroma_key_image(cell) for cell in slice_grid(sheet, SPRITE_GRID_COLS, SPRITE_GRID_ROWS, SPRITE_FRAME_SIZE)]
    frames, alignment_report = normalize_sprite_frames(frames, alignment or SpriteAlignmentOptions())

    frame_entries = []
    for i, frame in enumerate(frames):
        name = f"frame_{i + 1:02d}.png"
        save_rgba(frame, out / name)
        frame_entries.append({"index": i, "file": name, "x": (i % 4) * SPRITE_FRAME_SIZE, "y": (i // 4) * SPRITE_FRAME_SIZE})

    grid = Image.new("RGBA", (SPRITE_GRID_COLS * SPRITE_FRAME_SIZE, SPRITE_GRID_ROWS * SPRITE_FRAME_SIZE), (0, 0, 0, 0))
    strip = Image.new("RGBA", (SPRITE_FRAME_COUNT * SPRITE_FRAME_SIZE, SPRITE_FRAME_SIZE), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        grid.paste(frame, ((i % 4) * SPRITE_FRAME_SIZE, (i // 4) * SPRITE_FRAME_SIZE), frame)
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


def normalize_sprite_frames(frames: list[Any], options: SpriteAlignmentOptions) -> tuple[list[Any], dict[str, Any]]:
    """把 sprite 帧按稳定主体锚点和脚底基线对齐。

    旧版直接使用整帧 alpha bbox，披风、裙摆、武器或低 alpha 残边都会
    进入 bbox，导致角色主体在动画中左右抖动或上下漂移。这里先清理
    残边，再用高 alpha + 行列最少像素数计算主体 bbox，最后用上身
    分位数锚点对齐视觉重心。
    """
    Image, _, _ = require_pillow()
    cleaned_frames = [clean_sprite_alpha(frame, options.alpha_floor) for frame in frames]
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

    baselines = [metric["baseline"] for metric in valid if metric["baseline"] is not None]
    anchors = [metric["anchor_x"] for metric in valid if metric["anchor_x"] is not None]
    target_baseline = max(baselines) if options.vertical_anchor == "baseline" and baselines else None
    target_anchor = median_number(anchors) if options.horizontal_anchor != "none" and anchors else None
    normalized = []
    report_frames = []
    for index, (frame, metric) in enumerate(zip(cleaned_frames, source_metrics)):
        if not metric["bbox"]:
            normalized.append(frame)
            report_frames.append({"index": index, **metric, "dx": 0, "dy": 0, "aligned_bbox": None, "aligned_baseline": None, "aligned_anchor_x": None})
            continue

        dx = int(round(float(target_anchor) - float(metric["anchor_x"]))) if target_anchor is not None and metric["anchor_x"] is not None else 0
        dy = int(round(float(target_baseline) - float(metric["baseline"]))) if target_baseline is not None and metric["baseline"] is not None else 0
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
    box = robust_alpha_bbox(image, options.alpha_threshold, options.row_min_pixels, options.col_min_pixels)
    if not box:
        return {"bbox": None, "baseline": None, "anchor_x": None}
    anchor_x = sprite_anchor_x(image, box, options.horizontal_anchor, options.alpha_threshold)
    return {"bbox": list(box), "baseline": box[3], "anchor_x": anchor_x}


def robust_alpha_bbox(image: Any, threshold: int, row_min_pixels: int = 0, col_min_pixels: int = 0) -> tuple[int, int, int, int] | None:
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


def sprite_anchor_x(image: Any, box: tuple[int, int, int, int], mode: str, threshold: int) -> float | None:
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
    canvas.alpha_composite(frame.crop((src_left, src_top, src_right, src_bottom)), (dst_left, dst_top))
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


def process_props_sheet(sheet_path: str, ideas_path: str | None, output_dir: str) -> dict[str, Any]:
    """处理 props sheet：切成 8 格、色键、命名并生成 manifest。"""
    Image, _, _ = require_pillow()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ideas = read_prop_ideas(ideas_path)[: PROP_BATCH_COLS * PROP_BATCH_ROWS]
    sheet = load_rgba(sheet_path)
    cells = [chroma_key_image(cell) for cell in slice_grid(sheet, PROP_BATCH_COLS, PROP_BATCH_ROWS, PROP_TILE_SIZE)]
    entries = []
    for i, cell in enumerate(cells[: len(ideas) or len(cells)]):
        idea = ideas[i] if i < len(ideas) else {"category": f"prop_{i + 1}", "description": f"prop {i + 1}"}
        stem = slugify(idea.get("category") or idea.get("description") or f"prop_{i + 1}", f"prop_{i + 1}")
        filename = f"{stem}_{i + 1:02d}.png"
        save_rgba(cell, out / filename)
        entries.append({"name": idea.get("category", stem), "description": idea.get("description", ""), "file": filename})
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
    atlas = Image.new("RGBA", (cols * PROP_TILE_SIZE, rows * PROP_TILE_SIZE), (0, 0, 0, 0))
    for i, prop in enumerate(props):
        img = load_rgba(inp / prop["file"]).resize((PROP_TILE_SIZE, PROP_TILE_SIZE))
        x = (i % cols) * PROP_TILE_SIZE
        y = (i // cols) * PROP_TILE_SIZE
        atlas.paste(img, (x, y), img)
        prop["atlas"] = {"x": x, "y": y, "width": PROP_TILE_SIZE, "height": PROP_TILE_SIZE}
    save_rgba(atlas, inp / "props-atlas.png")
    manifest["atlas"] = "props-atlas.png"
    write_json(inp / "manifest.json", manifest)
    make_zip(output, [inp / "manifest.json", inp / "props-atlas.png", *[inp / prop["file"] for prop in props]])
    return manifest


def init_parallax(output: str) -> dict[str, Any]:
    """创建四层 parallax manifest。"""
    layers = []
    for role in ["sky", "far", "mid", "near"]:
        spec = LAYER_SPECS[role]
        layers.append({
            "role": role,
            "image": None,
            "raw_image": None,
            "width": spec["width"],
            "height": spec["height"],
            "scroll_speed": spec["speed"],
            "opaque": spec["opaque"],
        })
    manifest = {"version": 1, "workflow_order": ["near", "mid", "far", "sky"], "layers": layers}
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
                files.append((base / value) if not Path(value).is_absolute() else Path(value))
    make_zip(output, files)
    return manifest


def update_parallax_image(manifest_path: str, role: str, image: str, raw_image: str | None) -> dict[str, Any]:
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


def auto_plan_parallax(width: int, target: int, extension_percent: int = 38, max_steps: int = 14) -> dict[str, Any]:
    """规划 parallax 横向自动扩图步数，避免每次由 LLM 心算。"""
    steps = []
    current = width
    for index in range(max_steps):
        if current >= target:
            break
        amount = max(128, round(current * extension_percent / 100))
        steps.append({"step": index + 1, "direction": "right", "amount": amount, "start_width": current, "end_width": current + amount})
        current += amount
    return {"start_width": width, "target_width": target, "steps": steps, "final_width": current}


def make_zip(output: str | Path, files: Iterable[Path]) -> None:
    """创建 ZIP 包，自动跳过不存在文件但保持相对文件名。"""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            if file.exists():
                zf.write(file, arcname=file.name)


def audit_coverage(root: str) -> dict[str, Any]:
    """检查 Skill 文件和脚本入口是否覆盖原项目主要能力。"""
    root_path = Path(root)
    standalone_files = [
        "SKILL.md",
        "references/feature-map.md",
        "references/provider-config.md",
        "references/subskill-extender.md",
        "references/subskill-parallax.md",
        "references/subskill-tileset.md",
        "references/subskill-sprite.md",
        "references/subskill-props.md",
        "scripts/image_extender_skill.py",
    ]
    monorepo_files = [f"skills/image-extender-studio/{path}" for path in standalone_files]
    standalone_script = root_path / "scripts/image_extender_skill.py"
    monorepo_script = root_path / "skills/image-extender-studio/scripts/image_extender_skill.py"
    if standalone_script.exists():
        layout = "standalone"
        required_files = standalone_files
        script_path = standalone_script
    else:
        layout = "monorepo"
        required_files = monorepo_files
        script_path = monorepo_script
    missing = [path for path in required_files if not (root_path / path).exists()]
    script = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
    required_terms = [
        "call_image_provider",
        "call_text_provider",
        "prepare_extension_canvas",
        "apply_extension_result",
        "build_tileset_guide",
        "extract_tileset",
        "build_sprite_guide",
        "process_sprite_sheet",
        "normalize_sprite_frames",
        "robust_alpha_bbox",
        "sprite_anchor_x",
        "process_props_sheet",
        "init_parallax",
        "audit_coverage",
        "codex-app-imagegen",
    ]
    missing_terms = [term for term in required_terms if term not in script]
    ok = not missing and not missing_terms
    return {"ok": ok, "layout": layout, "missing_files": missing, "missing_script_terms": missing_terms}


def cmd_providers_validate(args: argparse.Namespace) -> None:
    """验证三类 provider 配置是否可解析。"""
    data = {}
    for capability in ["image", "text", "vision"]:
        provider = resolve_provider(capability, args)
        data[capability] = {
            "protocol": provider.protocol,
            "base_url": provider.base_url,
            "model": provider.model,
            "has_api_key": bool(provider.api_key),
        }
    write_json(args.output, data)


def cmd_prompt_generate(args: argparse.Namespace) -> None:
    """输出图片生成 prompt。"""
    write_text(args.output, format_prompt_for_emit(build_generate_prompt(args), args.emit))


def cmd_prompt_extend(args: argparse.Namespace) -> None:
    """输出扩图 prompt。"""
    write_text(args.output, format_prompt_for_emit(build_extend_prompt(args), args.emit))


def cmd_prompt_scene_brief(args: argparse.Namespace) -> None:
    """输出 scene brief 的 system/user prompt JSON。"""
    system, user = build_scene_brief_prompt(args)
    write_json(args.output, {"system": system, "user": user})


def cmd_prompt_prop_ideas(args: argparse.Namespace) -> None:
    """输出 prop ideas 的 system/user prompt JSON。"""
    existing = [item.strip().lower() for item in (args.existing or "").split(",") if item.strip()]
    system, user = build_prop_ideas_prompt(args.prompt, args.count, existing, read_text(args.scene_brief).strip(), args.art_style or "")
    write_json(args.output, {"system": system, "user": user})


def cmd_prompt_review(args: argparse.Namespace) -> None:
    """输出 vision review prompt JSON。"""
    system, user = build_review_prompt(args)
    write_json(args.output, {"system": system, "user": user})


def cmd_text_call(args: argparse.Namespace) -> None:
    """调用 text provider，输出文本或保存文本。"""
    provider = resolve_provider("text", args)
    system = read_text(args.system) if args.system else args.system_text
    user = read_text(args.user) if args.user else args.user_text
    text = call_text_provider(provider, system, user, args.title, args.max_tokens, args.temperature)
    write_text(args.output, text)


def cmd_review_call(args: argparse.Namespace) -> None:
    """调用 vision provider，输出 QA JSON 或原始文本。"""
    provider = resolve_provider("vision", args)
    system, user = build_review_prompt(args)
    text = call_text_provider(provider, system, user, args.title, args.max_tokens, args.temperature)
    if args.parse_json:
        write_json(args.output, parse_jsonish(text))
    else:
        write_text(args.output, text)


def cmd_image_call(args: argparse.Namespace) -> None:
    """调用 image provider，并保存返回图片。"""
    provider = resolve_provider("image", args)
    prompt = read_text(args.prompt_file) if args.prompt_file else args.prompt
    inputs = normalize_image_inputs(args.input_image or [])
    image = call_image_provider(provider, prompt, inputs, args.width, args.height, args.title, args.temperature, args.force_edit)
    save_image_payload(image, args.output)
    write_json(Path(args.output).with_suffix(".json"), {"output": args.output, "provider": provider.protocol, "model": provider.model})


def cmd_extend_prepare(args: argparse.Namespace) -> None:
    """执行扩图画布准备。"""
    write_json(args.manifest, prepare_extension_canvas(args.input, args.direction, args.amount, args.output))


def cmd_extend_apply(args: argparse.Namespace) -> None:
    """执行扩图结果融合。"""
    write_json(args.manifest, apply_extension_result(args.original, args.generated, args.direction, args.amount, args.output, args.blend))


def cmd_extend_call(args: argparse.Namespace) -> None:
    """准备 prompt 并调用 image provider 完成单次扩图生成。"""
    provider = resolve_provider("image", args)
    prompt = read_text(args.prompt_file) if args.prompt_file else build_extend_prompt(args)
    image = call_image_provider(provider, prompt, normalize_image_inputs([args.expanded]), args.width, args.height, "Image Extender Skill - Extend", args.temperature, True)
    save_image_payload(image, args.output)


def cmd_extend_batch(args: argparse.Namespace) -> None:
    """运行 Best-of-N 扩图候选，生成按 seam score 排序的 manifest。"""
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    candidates = []
    expanded = out / "expanded.png"
    prepare_extension_canvas(args.input, args.direction, args.amount, str(expanded))
    for i in range(args.attempts):
        generated = out / f"generated_{i + 1}.png"
        final = out / f"candidate_{i + 1}.png"
        call_args = argparse.Namespace(**vars(args))
        call_args.expanded = str(expanded)
        call_args.output = str(generated)
        call_args.temperature = 0.3 + i * 0.2
        call_args.width = load_rgba(expanded).width
        call_args.height = load_rgba(expanded).height
        call_args.prompt_file = None
        call_args.layer = getattr(args, "layer", None)
        call_args.art_style = getattr(args, "art_style", None)
        cmd_extend_call(call_args)
        manifest = apply_extension_result(args.input, str(generated), args.direction, args.amount, str(final), args.blend)
        candidates.append(manifest)
    candidates.sort(key=lambda item: item["seam_score"])
    write_json(out / "candidates.json", {"candidates": candidates})


def cmd_tileset_guide(args: argparse.Namespace) -> None:
    """生成 tileset 结构 guide。"""
    write_json(args.manifest, build_tileset_guide(args.output, args.cell_size))


def cmd_tileset_extract(args: argparse.Namespace) -> None:
    """提取 tileset 单块。"""
    write_json(args.manifest, extract_tileset(args.sheet, args.output_dir, args.layout))


def cmd_tileset_reconcile(args: argparse.Namespace) -> None:
    """调和 tileset 角块。"""
    write_json(args.output, reconcile_tileset(args.input_dir))


def cmd_tileset_package(args: argparse.Namespace) -> None:
    """打包 tileset。"""
    write_json(args.manifest, package_tileset(args.input_dir, args.output))


def cmd_sprite_guide(args: argparse.Namespace) -> None:
    """生成 sprite pose guide。"""
    if args.anim not in BODY_PLAN_ANIMS.get(args.body_plan, []):
        raise SystemExit(f"{args.body_plan} 不支持动画 {args.anim}")
    write_json(args.manifest, build_sprite_guide(args.body_plan, args.anim, args.output))


def cmd_sprite_process(args: argparse.Namespace) -> None:
    """处理 sprite sheet。"""
    alignment = SpriteAlignmentOptions(
        vertical_anchor=args.vertical_anchor,
        horizontal_anchor=args.horizontal_anchor,
        alpha_threshold=args.alpha_threshold,
        alpha_floor=args.alpha_floor,
        row_min_pixels=args.row_min_pixels,
        col_min_pixels=args.col_min_pixels,
    )
    write_json(args.manifest, process_sprite_sheet(args.sheet, args.output_dir, args.body_plan, args.anim, alignment))


def cmd_sprite_package(args: argparse.Namespace) -> None:
    """打包 sprite 输出。"""
    write_json(args.manifest, package_sprite(args.input_dir, args.output))


def cmd_props_ideas(args: argparse.Namespace) -> None:
    """生成 props ideas；有 provider 时调用模型，否则使用本地 fallback。"""
    existing = [item.strip().lower() for item in (args.existing or "").split(",") if item.strip()]
    if args.offline:
        ideas = fallback_prop_ideas(args.prompt, args.count, existing)
    else:
        provider = resolve_provider("text", args)
        if provider.api_key:
            system, user = build_prop_ideas_prompt(args.prompt, args.count, existing, read_text(args.scene_brief).strip(), args.art_style or "")
            text = call_text_provider(provider, system, user, "Image Extender Skill - Prop Ideas", 900, 1.0)
            data = parse_jsonish(text)
            ideas = normalize_prop_ideas(data.get("props", data) if isinstance(data, dict) else data)
        else:
            ideas = fallback_prop_ideas(args.prompt, args.count, existing)
    write_json(args.output, {"props": ideas[: args.count]})


def cmd_props_process(args: argparse.Namespace) -> None:
    """处理 props sheet。"""
    write_json(args.manifest, process_props_sheet(args.sheet, args.ideas, args.output_dir))


def cmd_props_package(args: argparse.Namespace) -> None:
    """打包 props 输出。"""
    write_json(args.manifest, package_props(args.input_dir, args.output, args.cols))


def cmd_parallax_init(args: argparse.Namespace) -> None:
    """初始化 parallax manifest。"""
    init_parallax(args.output)


def cmd_parallax_key(args: argparse.Namespace) -> None:
    """执行 parallax 图层色键。"""
    write_json(args.manifest, key_parallax_layer(args.input, args.role, args.output))


def cmd_parallax_tileable(args: argparse.Namespace) -> None:
    """把 parallax 图层处理为水平可平铺。"""
    img = make_horizontally_tileable(load_rgba(args.input), args.band)
    save_rgba(img, args.output)


def cmd_parallax_harmonize(args: argparse.Namespace) -> None:
    """平滑 parallax 横向色漂。"""
    img = harmonize_horizontal(load_rgba(args.input), args.strength)
    save_rgba(img, args.output)


def cmd_parallax_package(args: argparse.Namespace) -> None:
    """打包 parallax 项目。"""
    write_json(args.audit, package_parallax(args.manifest, args.output))


def cmd_parallax_update(args: argparse.Namespace) -> None:
    """更新 parallax manifest 的图层路径。"""
    write_json(args.output_json, update_parallax_image(args.manifest, args.role, args.image, args.raw_image))


def cmd_parallax_auto_plan(args: argparse.Namespace) -> None:
    """输出 parallax 自动扩图计划。"""
    write_json(args.output, auto_plan_parallax(args.width, args.target, args.extension_percent, args.max_steps))


def cmd_audit_coverage(args: argparse.Namespace) -> None:
    """执行 Skill 覆盖审计。"""
    result = audit_coverage(args.root)
    write_json(args.output, result)
    if not result["ok"]:
        raise SystemExit(1)


def add_provider_args(parser: argparse.ArgumentParser) -> None:
    """给需要 provider 的命令挂载统一配置参数。"""
    parser.add_argument("--config", help="provider JSON 配置文件")
    for capability in ["image", "text", "vision"]:
        parser.add_argument(f"--{capability}-protocol", choices=sorted(PROVIDER_PROTOCOLS))
        parser.add_argument(f"--{capability}-base-url")
        parser.add_argument(f"--{capability}-model")
        parser.add_argument(f"--{capability}-api-key")


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI parser，集中声明所有 Skill 固定入口。"""
    parser = argparse.ArgumentParser(description="Image Extender Studio Skill deterministic runner")
    sub = parser.add_subparsers(dest="group", required=True)

    providers = sub.add_parser("providers")
    providers_sub = providers.add_subparsers(dest="command", required=True)
    providers_validate = providers_sub.add_parser("validate")
    add_provider_args(providers_validate)
    providers_validate.add_argument("--output")
    providers_validate.set_defaults(func=cmd_providers_validate)

    prompt = sub.add_parser("prompt")
    prompt_sub = prompt.add_subparsers(dest="command", required=True)
    p_generate = prompt_sub.add_parser("generate")
    p_generate.add_argument("--mode", choices=["image", "parallax", "tileset", "sprite-anchor", "sprite-sheet", "props"], required=True)
    p_generate.add_argument("--prompt", required=True)
    p_generate.add_argument("--layer", choices=["sky", "far", "mid", "near"], default="near")
    p_generate.add_argument("--body-plan", choices=sorted(BODY_PLAN_ANIMS), default="biped")
    p_generate.add_argument("--anim", default="idle")
    p_generate.add_argument("--art-style")
    p_generate.add_argument("--scene-brief")
    p_generate.add_argument("--fix-notes")
    p_generate.add_argument("--ideas")
    p_generate.add_argument("--emit", choices=["plain", "codex"], default="plain")
    p_generate.add_argument("--output")
    p_generate.set_defaults(func=cmd_prompt_generate)

    p_extend = prompt_sub.add_parser("extend")
    p_extend.add_argument("--input")
    p_extend.add_argument("--direction", choices=["up", "down", "left", "right"], required=True)
    p_extend.add_argument("--amount", type=int, required=True)
    p_extend.add_argument("--prompt", default="")
    p_extend.add_argument("--art-style")
    p_extend.add_argument("--layer", choices=["sky", "far", "mid", "near"])
    p_extend.add_argument("--emit", choices=["plain", "codex"], default="plain")
    p_extend.add_argument("--output")
    p_extend.set_defaults(func=cmd_prompt_extend)

    p_scene = prompt_sub.add_parser("scene-brief")
    p_scene.add_argument("--prompt", required=True)
    p_scene.add_argument("--output")
    p_scene.set_defaults(func=cmd_prompt_scene_brief)

    p_prop = prompt_sub.add_parser("prop-ideas")
    p_prop.add_argument("--prompt", required=True)
    p_prop.add_argument("--count", type=int, default=8)
    p_prop.add_argument("--existing", default="")
    p_prop.add_argument("--scene-brief")
    p_prop.add_argument("--art-style")
    p_prop.add_argument("--output")
    p_prop.set_defaults(func=cmd_prompt_prop_ideas)

    p_review = prompt_sub.add_parser("review")
    p_review.add_argument("--kind", choices=["tile", "sprite"], required=True)
    p_review.add_argument("--image", required=True)
    p_review.add_argument("--output")
    p_review.set_defaults(func=cmd_prompt_review)

    text = sub.add_parser("text")
    text_sub = text.add_subparsers(dest="command", required=True)
    t_call = text_sub.add_parser("call")
    add_provider_args(t_call)
    t_call.add_argument("--system")
    t_call.add_argument("--user")
    t_call.add_argument("--system-text", default="")
    t_call.add_argument("--user-text", default="")
    t_call.add_argument("--title", default="Image Extender Skill - Text")
    t_call.add_argument("--max-tokens", type=int, default=800)
    t_call.add_argument("--temperature", type=float, default=0.4)
    t_call.add_argument("--output")
    t_call.set_defaults(func=cmd_text_call)

    review = sub.add_parser("review")
    review_sub = review.add_subparsers(dest="command", required=True)
    r_call = review_sub.add_parser("call")
    add_provider_args(r_call)
    r_call.add_argument("--kind", choices=["tile", "sprite"], required=True)
    r_call.add_argument("--image", required=True)
    r_call.add_argument("--title", default="Image Extender Skill - Review")
    r_call.add_argument("--max-tokens", type=int, default=600)
    r_call.add_argument("--temperature", type=float, default=0.2)
    r_call.add_argument("--parse-json", action="store_true")
    r_call.add_argument("--output")
    r_call.set_defaults(func=cmd_review_call)

    image = sub.add_parser("image")
    image_sub = image.add_subparsers(dest="command", required=True)
    i_call = image_sub.add_parser("call")
    add_provider_args(i_call)
    i_call.add_argument("--prompt", default="")
    i_call.add_argument("--prompt-file")
    i_call.add_argument("--input-image", action="append")
    i_call.add_argument("--width", type=int, default=1024)
    i_call.add_argument("--height", type=int, default=1024)
    i_call.add_argument("--temperature", type=float, default=0.4)
    i_call.add_argument("--force-edit", action="store_true")
    i_call.add_argument("--title", default="Image Extender Skill - Image")
    i_call.add_argument("--output", required=True)
    i_call.set_defaults(func=cmd_image_call)

    extend = sub.add_parser("extend")
    extend_sub = extend.add_subparsers(dest="command", required=True)
    e_prepare = extend_sub.add_parser("prepare")
    e_prepare.add_argument("--input", required=True)
    e_prepare.add_argument("--direction", choices=["up", "down", "left", "right"], required=True)
    e_prepare.add_argument("--amount", type=int, required=True)
    e_prepare.add_argument("--output", required=True)
    e_prepare.add_argument("--manifest")
    e_prepare.set_defaults(func=cmd_extend_prepare)

    e_apply = extend_sub.add_parser("apply-result")
    e_apply.add_argument("--original", required=True)
    e_apply.add_argument("--generated", required=True)
    e_apply.add_argument("--direction", choices=["up", "down", "left", "right"], required=True)
    e_apply.add_argument("--amount", type=int, required=True)
    e_apply.add_argument("--output", required=True)
    e_apply.add_argument("--blend", choices=["poisson", "feather"], default="poisson")
    e_apply.add_argument("--manifest")
    e_apply.set_defaults(func=cmd_extend_apply)

    e_call = extend_sub.add_parser("call")
    add_provider_args(e_call)
    e_call.add_argument("--expanded", required=True)
    e_call.add_argument("--direction", choices=["up", "down", "left", "right"], required=True)
    e_call.add_argument("--amount", type=int, required=True)
    e_call.add_argument("--prompt", default="")
    e_call.add_argument("--prompt-file")
    e_call.add_argument("--layer", choices=["sky", "far", "mid", "near"])
    e_call.add_argument("--art-style")
    e_call.add_argument("--width", type=int, required=True)
    e_call.add_argument("--height", type=int, required=True)
    e_call.add_argument("--temperature", type=float, default=0.4)
    e_call.add_argument("--output", required=True)
    e_call.set_defaults(func=cmd_extend_call)

    e_batch = extend_sub.add_parser("batch")
    add_provider_args(e_batch)
    e_batch.add_argument("--input", required=True)
    e_batch.add_argument("--direction", choices=["up", "down", "left", "right"], required=True)
    e_batch.add_argument("--amount", type=int, required=True)
    e_batch.add_argument("--prompt", default="")
    e_batch.add_argument("--attempts", type=int, default=3)
    e_batch.add_argument("--blend", choices=["poisson", "feather"], default="poisson")
    e_batch.add_argument("--output-dir", required=True)
    e_batch.set_defaults(func=cmd_extend_batch)

    parallax = sub.add_parser("parallax")
    parallax_sub = parallax.add_subparsers(dest="command", required=True)
    px_init = parallax_sub.add_parser("init")
    px_init.add_argument("--output", required=True)
    px_init.set_defaults(func=cmd_parallax_init)
    px_key = parallax_sub.add_parser("key-layer")
    px_key.add_argument("--input", required=True)
    px_key.add_argument("--role", choices=["sky", "far", "mid", "near"], required=True)
    px_key.add_argument("--output", required=True)
    px_key.add_argument("--manifest")
    px_key.set_defaults(func=cmd_parallax_key)
    px_tile = parallax_sub.add_parser("tileable")
    px_tile.add_argument("--input", required=True)
    px_tile.add_argument("--output", required=True)
    px_tile.add_argument("--band", type=int, default=64)
    px_tile.set_defaults(func=cmd_parallax_tileable)
    px_harm = parallax_sub.add_parser("harmonize")
    px_harm.add_argument("--input", required=True)
    px_harm.add_argument("--output", required=True)
    px_harm.add_argument("--strength", type=float, default=0.35)
    px_harm.set_defaults(func=cmd_parallax_harmonize)
    px_pack = parallax_sub.add_parser("package")
    px_pack.add_argument("--manifest", required=True)
    px_pack.add_argument("--output", required=True)
    px_pack.add_argument("--audit")
    px_pack.set_defaults(func=cmd_parallax_package)
    px_update = parallax_sub.add_parser("update-layer")
    px_update.add_argument("--manifest", required=True)
    px_update.add_argument("--role", choices=["sky", "far", "mid", "near"], required=True)
    px_update.add_argument("--image", required=True)
    px_update.add_argument("--raw-image")
    px_update.add_argument("--output-json")
    px_update.set_defaults(func=cmd_parallax_update)
    px_plan = parallax_sub.add_parser("auto-plan")
    px_plan.add_argument("--width", type=int, required=True)
    px_plan.add_argument("--target", type=int, required=True)
    px_plan.add_argument("--extension-percent", type=int, default=38)
    px_plan.add_argument("--max-steps", type=int, default=14)
    px_plan.add_argument("--output")
    px_plan.set_defaults(func=cmd_parallax_auto_plan)

    tileset = sub.add_parser("tileset")
    tileset_sub = tileset.add_subparsers(dest="command", required=True)
    ts_guide = tileset_sub.add_parser("guide")
    ts_guide.add_argument("--output", required=True)
    ts_guide.add_argument("--cell-size", type=int, default=TILE_SIZE)
    ts_guide.add_argument("--manifest")
    ts_guide.set_defaults(func=cmd_tileset_guide)
    ts_extract = tileset_sub.add_parser("extract")
    ts_extract.add_argument("--sheet", required=True)
    ts_extract.add_argument("--output-dir", required=True)
    ts_extract.add_argument("--layout", choices=["auto", "template", "atlas"], default="auto")
    ts_extract.add_argument("--manifest")
    ts_extract.set_defaults(func=cmd_tileset_extract)
    ts_reconcile = tileset_sub.add_parser("reconcile")
    ts_reconcile.add_argument("--input-dir", required=True)
    ts_reconcile.add_argument("--output")
    ts_reconcile.set_defaults(func=cmd_tileset_reconcile)
    ts_package = tileset_sub.add_parser("package")
    ts_package.add_argument("--input-dir", required=True)
    ts_package.add_argument("--output", required=True)
    ts_package.add_argument("--manifest")
    ts_package.set_defaults(func=cmd_tileset_package)

    sprite = sub.add_parser("sprite")
    sprite_sub = sprite.add_subparsers(dest="command", required=True)
    sp_guide = sprite_sub.add_parser("guide")
    sp_guide.add_argument("--body-plan", choices=sorted(BODY_PLAN_ANIMS), required=True)
    sp_guide.add_argument("--anim", required=True)
    sp_guide.add_argument("--output", required=True)
    sp_guide.add_argument("--manifest")
    sp_guide.set_defaults(func=cmd_sprite_guide)
    sp_process = sprite_sub.add_parser("process")
    sp_process.add_argument("--sheet", required=True)
    sp_process.add_argument("--body-plan", choices=sorted(BODY_PLAN_ANIMS), required=True)
    sp_process.add_argument("--anim", required=True)
    sp_process.add_argument("--output-dir", required=True)
    sp_process.add_argument("--vertical-anchor", choices=["baseline", "none"], default="baseline")
    sp_process.add_argument(
        "--horizontal-anchor",
        choices=["upper-q50", "upper-q65", "upper-q75", "upper-q85", "bbox-center", "feet-center", "none"],
        default="upper-q75",
    )
    sp_process.add_argument("--alpha-threshold", type=int, default=SPRITE_ALIGN_ALPHA_THRESHOLD)
    sp_process.add_argument("--alpha-floor", type=int, default=SPRITE_ALIGN_ALPHA_FLOOR)
    sp_process.add_argument("--row-min-pixels", type=int, default=0)
    sp_process.add_argument("--col-min-pixels", type=int, default=0)
    sp_process.add_argument("--manifest")
    sp_process.set_defaults(func=cmd_sprite_process)
    sp_package = sprite_sub.add_parser("package")
    sp_package.add_argument("--input-dir", required=True)
    sp_package.add_argument("--output", required=True)
    sp_package.add_argument("--manifest")
    sp_package.set_defaults(func=cmd_sprite_package)

    props = sub.add_parser("props")
    props_sub = props.add_subparsers(dest="command", required=True)
    pr_ideas = props_sub.add_parser("ideas")
    add_provider_args(pr_ideas)
    pr_ideas.add_argument("--prompt", required=True)
    pr_ideas.add_argument("--count", type=int, default=8)
    pr_ideas.add_argument("--existing", default="")
    pr_ideas.add_argument("--scene-brief")
    pr_ideas.add_argument("--art-style")
    pr_ideas.add_argument("--offline", action="store_true")
    pr_ideas.add_argument("--output", required=True)
    pr_ideas.set_defaults(func=cmd_props_ideas)
    pr_process = props_sub.add_parser("process")
    pr_process.add_argument("--sheet", required=True)
    pr_process.add_argument("--ideas")
    pr_process.add_argument("--output-dir", required=True)
    pr_process.add_argument("--manifest")
    pr_process.set_defaults(func=cmd_props_process)
    pr_package = props_sub.add_parser("package")
    pr_package.add_argument("--input-dir", required=True)
    pr_package.add_argument("--output", required=True)
    pr_package.add_argument("--cols", type=int, default=4)
    pr_package.add_argument("--manifest")
    pr_package.set_defaults(func=cmd_props_package)

    audit = sub.add_parser("audit")
    audit_sub = audit.add_subparsers(dest="command", required=True)
    a_cov = audit_sub.add_parser("coverage")
    a_cov.add_argument("--root", default=".")
    a_cov.add_argument("--output")
    a_cov.set_defaults(func=cmd_audit_coverage)
    return parser


def main(argv: list[str] | None = None) -> int:
    """脚本主入口：解析参数并分派到具体命令。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
