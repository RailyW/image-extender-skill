"""Prompt 构造和模型 JSON 容错解析。

所有自然语言模板都集中在这里，确保 CLI、Skill 文档和未来自动化流程共用
同一套约束，不在命令处理层临时拼接提示词。
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Iterable

from image_extender_studio.core.io import read_json_file, read_text, slugify
from image_extender_studio.providers.client import as_data_url


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
        return build_tileset_prompt(
            prompt, style, scene, read_text(getattr(args, "fix_notes", None)).strip()
        )
    if args.mode == "sprite-anchor":
        return build_sprite_anchor_prompt(prompt, args.body_plan, style)
    if args.mode == "sprite-sheet":
        return build_sprite_sheet_prompt(
            prompt,
            args.body_plan,
            args.anim,
            style,
            read_text(getattr(args, "fix_notes", None)).strip(),
        )
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


def build_sprite_sheet_prompt(
    prompt: str, body_plan: str, anim: str, style: str, fix_notes: str
) -> str:
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


def build_props_prompt(
    prompt: str, ideas: list[dict[str, str]], style: str, scene: str
) -> str:
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
    custom_block = (
        f'\nUser request for the new area: "{custom}".'
        if custom
        else "\nContinue the existing scene naturally without adding unrelated new subjects."
    )
    layer_block = (
        f"\nParallax layer role: {args.layer}. Preserve its layer rules exactly."
        if getattr(args, "layer", None)
        else ""
    )
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


def build_prop_ideas_prompt(
    prompt: str, count: int, existing: list[str], scene: str, style: str
) -> tuple[str, str]:
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
    image_url = (
        as_data_url(args.image)
        if args.image and not str(args.image).startswith(("http", "data:image"))
        else args.image
    )
    if args.kind == "tile":
        text = 'Review this 2D platformer autotile preview. Check transparent keying, edge consistency, seamless body tiling, palette cohesion, blur, halos and obvious grid artifacts. Return strict JSON: {"pass":true|false,"score":0-100,"fix_notes":"..."}.'
    else:
        text = 'Review this 2D sprite animation sheet. Check one character per cell, consistent identity, scale, baseline, facing direction, clean alpha key, no labels, and readable animation. Return strict JSON: {"pass":true|false,"score":0-100,"fix_notes":"..."}.'
    user = [
        {"type": "image_url", "image_url": {"url": image_url}},
        {"type": "text", "text": text},
    ]
    return (
        "You are a strict senior 2D game art QA reviewer. Only report painter-fixable issues.",
        user,
    )


def parse_jsonish(text: str) -> Any:
    """容错解析模型返回的 JSON，兼容 markdown fence 和前后说明文字。"""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    for candidate in [
        cleaned,
        slice_between(cleaned, "[", "]"),
        slice_between(cleaned, "{", "}"),
    ]:
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
            result.append(
                {
                    "category": category or slugify(description.split()[0]),
                    "description": description,
                }
            )
    return result


def fallback_prop_ideas(
    prompt: str, count: int, existing: list[str]
) -> list[dict[str, str]]:
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
        ideas.append(
            {
                "category": category,
                "description": f"{desc} fitting {prompt or 'the biome'}",
            }
        )
        if len(ideas) >= count:
            break
    return ideas
