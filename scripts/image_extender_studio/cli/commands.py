"""CLI 命令处理函数。

本模块把 argparse Namespace 翻译成各业务模块的函数调用。每个命令函数只做
参数读取、调用分派和结果写出，不承载图像算法或 provider 协议细节。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from image_extender_studio.audit.coverage import audit_coverage
from image_extender_studio.core.constants import BODY_PLAN_ANIMS
from image_extender_studio.core.io import read_text, write_json, write_text
from image_extender_studio.core.models import SpriteAlignmentOptions
from image_extender_studio.imaging.common import (
    harmonize_horizontal,
    load_rgba,
    make_horizontally_tileable,
    save_rgba,
)
from image_extender_studio.prompts.builders import (
    build_extend_prompt,
    build_generate_prompt,
    build_prop_ideas_prompt,
    build_review_prompt,
    build_scene_brief_prompt,
    fallback_prop_ideas,
    format_prompt_for_emit,
    normalize_prop_ideas,
    parse_jsonish,
)
from image_extender_studio.providers.client import (
    call_image_provider,
    call_text_provider,
    normalize_image_inputs,
    resolve_provider,
    save_image_payload,
)
from image_extender_studio.workflows.extender import (
    apply_extension_result,
    prepare_extension_canvas,
)
from image_extender_studio.workflows.parallax import (
    auto_plan_parallax,
    init_parallax,
    key_parallax_layer,
    package_parallax,
    update_parallax_image,
)
from image_extender_studio.workflows.props import package_props, process_props_sheet
from image_extender_studio.workflows.sprite import (
    build_sprite_guide,
    package_sprite,
    process_sprite_sheet,
)
from image_extender_studio.workflows.tileset import (
    build_tileset_guide,
    extract_tileset,
    package_tileset,
    reconcile_tileset,
)


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
    write_text(
        args.output, format_prompt_for_emit(build_generate_prompt(args), args.emit)
    )


def cmd_prompt_extend(args: argparse.Namespace) -> None:
    """输出扩图 prompt。"""
    write_text(
        args.output, format_prompt_for_emit(build_extend_prompt(args), args.emit)
    )


def cmd_prompt_scene_brief(args: argparse.Namespace) -> None:
    """输出 scene brief 的 system/user prompt JSON。"""
    system, user = build_scene_brief_prompt(args)
    write_json(args.output, {"system": system, "user": user})


def cmd_prompt_prop_ideas(args: argparse.Namespace) -> None:
    """输出 prop ideas 的 system/user prompt JSON。"""
    existing = [
        item.strip().lower()
        for item in (args.existing or "").split(",")
        if item.strip()
    ]
    system, user = build_prop_ideas_prompt(
        args.prompt,
        args.count,
        existing,
        read_text(args.scene_brief).strip(),
        args.art_style or "",
    )
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
    text = call_text_provider(
        provider, system, user, args.title, args.max_tokens, args.temperature
    )
    write_text(args.output, text)


def cmd_review_call(args: argparse.Namespace) -> None:
    """调用 vision provider，输出 QA JSON 或原始文本。"""
    provider = resolve_provider("vision", args)
    system, user = build_review_prompt(args)
    text = call_text_provider(
        provider, system, user, args.title, args.max_tokens, args.temperature
    )
    if args.parse_json:
        write_json(args.output, parse_jsonish(text))
    else:
        write_text(args.output, text)


def cmd_image_call(args: argparse.Namespace) -> None:
    """调用 image provider，并保存返回图片。"""
    provider = resolve_provider("image", args)
    prompt = read_text(args.prompt_file) if args.prompt_file else args.prompt
    inputs = normalize_image_inputs(args.input_image or [])
    image = call_image_provider(
        provider,
        prompt,
        inputs,
        args.width,
        args.height,
        args.title,
        args.temperature,
        args.force_edit,
    )
    save_image_payload(image, args.output)
    write_json(
        Path(args.output).with_suffix(".json"),
        {"output": args.output, "provider": provider.protocol, "model": provider.model},
    )


def cmd_extend_prepare(args: argparse.Namespace) -> None:
    """执行扩图画布准备。"""
    write_json(
        args.manifest,
        prepare_extension_canvas(args.input, args.direction, args.amount, args.output),
    )


def cmd_extend_apply(args: argparse.Namespace) -> None:
    """执行扩图结果融合。"""
    write_json(
        args.manifest,
        apply_extension_result(
            args.original,
            args.generated,
            args.direction,
            args.amount,
            args.output,
            args.blend,
        ),
    )


def cmd_extend_call(args: argparse.Namespace) -> None:
    """准备 prompt 并调用 image provider 完成单次扩图生成。"""
    provider = resolve_provider("image", args)
    prompt = (
        read_text(args.prompt_file) if args.prompt_file else build_extend_prompt(args)
    )
    image = call_image_provider(
        provider,
        prompt,
        normalize_image_inputs([args.expanded]),
        args.width,
        args.height,
        "Image Extender Skill - Extend",
        args.temperature,
        True,
    )
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
        manifest = apply_extension_result(
            args.input,
            str(generated),
            args.direction,
            args.amount,
            str(final),
            args.blend,
        )
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
    write_json(
        args.manifest, build_sprite_guide(args.body_plan, args.anim, args.output)
    )


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
    write_json(
        args.manifest,
        process_sprite_sheet(
            args.sheet, args.output_dir, args.body_plan, args.anim, alignment
        ),
    )


def cmd_sprite_package(args: argparse.Namespace) -> None:
    """打包 sprite 输出。"""
    write_json(args.manifest, package_sprite(args.input_dir, args.output))


def cmd_props_ideas(args: argparse.Namespace) -> None:
    """生成 props ideas；有 provider 时调用模型，否则使用本地 fallback。"""
    existing = [
        item.strip().lower()
        for item in (args.existing or "").split(",")
        if item.strip()
    ]
    if args.offline:
        ideas = fallback_prop_ideas(args.prompt, args.count, existing)
    else:
        provider = resolve_provider("text", args)
        if provider.api_key:
            system, user = build_prop_ideas_prompt(
                args.prompt,
                args.count,
                existing,
                read_text(args.scene_brief).strip(),
                args.art_style or "",
            )
            text = call_text_provider(
                provider, system, user, "Image Extender Skill - Prop Ideas", 900, 1.0
            )
            data = parse_jsonish(text)
            ideas = normalize_prop_ideas(
                data.get("props", data) if isinstance(data, dict) else data
            )
        else:
            ideas = fallback_prop_ideas(args.prompt, args.count, existing)
    write_json(args.output, {"props": ideas[: args.count]})


def cmd_props_process(args: argparse.Namespace) -> None:
    """处理 props sheet。"""
    write_json(
        args.manifest, process_props_sheet(args.sheet, args.ideas, args.output_dir)
    )


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
    write_json(
        args.output_json,
        update_parallax_image(args.manifest, args.role, args.image, args.raw_image),
    )


def cmd_parallax_auto_plan(args: argparse.Namespace) -> None:
    """输出 parallax 自动扩图计划。"""
    write_json(
        args.output,
        auto_plan_parallax(
            args.width, args.target, args.extension_percent, args.max_steps
        ),
    )


def cmd_audit_coverage(args: argparse.Namespace) -> None:
    """执行 Skill 覆盖审计。"""
    result = audit_coverage(args.root)
    write_json(args.output, result)
    if not result["ok"]:
        raise SystemExit(1)
