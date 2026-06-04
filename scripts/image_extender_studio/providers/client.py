"""Provider 配置解析、HTTP 调用和响应解析。

本模块封装 OpenRouter、OpenAI-compatible Chat、Responses 与 Images API 的
差异，对外只暴露“调用文本 provider / 调用图片 provider”的稳定函数。
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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from image_extender_studio.core.constants import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_OPENROUTER_BASE,
    DEFAULT_TEXT_MODEL,
    DEFAULT_VISION_MODEL,
    PROVIDER_PROTOCOLS,
)
from image_extender_studio.core.io import read_json_file
from image_extender_studio.core.models import ProviderConfig


def load_provider_file(path: str | None) -> dict[str, Any]:
    """读取 provider JSON 配置，并兼容不存在配置文件的情况。"""
    data = read_json_file(path, default={})
    if not isinstance(data, dict):
        raise SystemExit("provider 配置必须是 JSON object")
    return data


def resolve_provider(capability: str, args: argparse.Namespace) -> ProviderConfig:
    """按 CLI、JSON、环境变量、旧 OpenRouter key 的顺序解析 provider。"""
    config = load_provider_file(getattr(args, "config", None))
    slot = (
        config.get(capability, {})
        if isinstance(config.get(capability, {}), dict)
        else {}
    )
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
        or (
            "openrouter-chat-completions"
            if capability != "imagegen"
            else "codex-app-imagegen"
        )
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
    model = (
        cli_model
        or os.environ.get(f"{prefix}_PROVIDER_MODEL")
        or slot.get("model")
        or default_model
    )

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
        raise SystemExit(
            f"provider HTTP {exc.code}: {short_provider_error(text)}"
        ) from exc


def short_provider_error(text: str) -> str:
    """从 provider 错误体中提取短消息，避免输出大段响应。"""
    try:
        data = json.loads(text)
        return str(
            data.get("error", {}).get("message") or data.get("message") or text[:500]
        )
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
        if (
            item.startswith("http://")
            or item.startswith("https://")
            or item.startswith("data:image")
        ):
            result.append(item)
        else:
            result.append(as_data_url(item))
    return result


def build_chat_text_body(
    provider: ProviderConfig,
    system_prompt: str,
    user_content: Any,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
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
            converted.append(
                {"type": "input_image", "image_url": part["image_url"]["url"]}
            )
        else:
            converted.append({"type": "input_text", "text": part.get("text", "")})
    return converted


def call_text_provider(
    provider: ProviderConfig,
    system_prompt: str,
    user_content: Any,
    title: str,
    max_tokens: int = 800,
    temperature: float = 0.4,
) -> str:
    """调用文本或视觉 provider，并返回提取后的纯文本。"""
    if provider.protocol == "codex-app-imagegen":
        raise SystemExit(
            "codex-app-imagegen 只用于图片生成，不能作为 text/vision provider"
        )
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
        body = build_chat_text_body(
            provider, system_prompt, user_content, max_tokens, temperature
        )

    data = post_json(
        f"{provider.base_url}{endpoint}", build_headers(provider, title), body
    )
    return extract_text(data)


def call_image_provider(
    provider: ProviderConfig,
    prompt: str,
    input_images: list[str],
    width: int,
    height: int,
    title: str,
    temperature: float = 0.4,
    force_edit: bool = False,
) -> str:
    """调用图片 provider，并返回 URL 或 data URL。"""
    if provider.protocol == "codex-app-imagegen":
        raise SystemExit(
            "Codex App imagegen 需要由 Skill 调用 $imagegen，脚本只负责生成 prompt 和后处理"
        )
    if not provider.api_key:
        raise SystemExit("image provider 缺少 API key")
    if provider.protocol == "openai-images" and input_images:
        raise SystemExit(
            "openai-images 只支持纯文生图；带输入图请使用 openai-responses 或 chat image 协议"
        )

    # 按协议构建请求体，兼容 OpenRouter、Responses 与 Images API。
    if provider.protocol == "openai-responses":
        endpoint = "/responses"
        body = {
            "model": provider.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        *[
                            {"type": "input_image", "image_url": url}
                            for url in input_images
                        ],
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
                        *[
                            {"type": "image_url", "image_url": {"url": url}}
                            for url in input_images
                        ],
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 2000,
            "temperature": temperature,
        }
        if provider.protocol == "openrouter-chat-completions":
            body["modalities"] = ["image", "text"]
            body["image_config"] = {
                "aspect_ratio": supported_aspect_ratio(width, height)
            }

    data = post_json(
        f"{provider.base_url}{endpoint}", build_headers(provider, title), body
    )
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
        return "".join(
            extract_text(choice.get("message", choice)) for choice in node["choices"]
        ).strip()

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
                found = extract_image(
                    item.get("message", item) if isinstance(item, dict) else item
                )
                if found:
                    return found

    if node.get("type") == "image_generation_call" and node.get("result"):
        return "data:image/png;base64," + str(node["result"])
    if isinstance(node.get("url"), str):
        return node["url"]
    if isinstance(node.get("b64_json"), str):
        return "data:image/png;base64," + node["b64_json"]
    if isinstance(node.get("image_url"), dict) and isinstance(
        node["image_url"].get("url"), str
    ):
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
    return min(
        ratios,
        key=lambda item: abs(
            math.log((int(item.split(":")[0]) / int(item.split(":")[1])) / target)
        ),
    )
