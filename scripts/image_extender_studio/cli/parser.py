"""argparse 命令树声明和 CLI 主入口。

本模块集中维护用户可见的命令、参数、默认值和命令函数绑定；新增功能时
优先在这里注册入口，再把实际实现放到对应业务模块。
"""

from __future__ import annotations

import argparse

from image_extender_studio.cli.commands import *  # noqa: F403 - argparse 绑定需要访问所有 cmd_* 函数
from image_extender_studio.core.constants import (
    BODY_PLAN_ANIMS,
    PROVIDER_PROTOCOLS,
    SPRITE_ALIGN_ALPHA_FLOOR,
    SPRITE_ALIGN_ALPHA_THRESHOLD,
    TILE_SIZE,
)


def add_provider_args(parser: argparse.ArgumentParser) -> None:
    """给需要 provider 的命令挂载统一配置参数。"""
    parser.add_argument("--config", help="provider JSON 配置文件")
    for capability in ["image", "text", "vision"]:
        parser.add_argument(
            f"--{capability}-protocol", choices=sorted(PROVIDER_PROTOCOLS)
        )
        parser.add_argument(f"--{capability}-base-url")
        parser.add_argument(f"--{capability}-model")
        parser.add_argument(f"--{capability}-api-key")


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI parser，集中声明所有 Skill 固定入口。"""
    parser = argparse.ArgumentParser(
        description="Image Extender Studio Skill deterministic runner"
    )
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
    p_generate.add_argument(
        "--mode",
        choices=[
            "image",
            "parallax",
            "tileset",
            "sprite-anchor",
            "sprite-sheet",
            "props",
        ],
        required=True,
    )
    p_generate.add_argument("--prompt", required=True)
    p_generate.add_argument(
        "--layer", choices=["sky", "far", "mid", "near"], default="near"
    )
    p_generate.add_argument(
        "--body-plan", choices=sorted(BODY_PLAN_ANIMS), default="biped"
    )
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
    p_extend.add_argument(
        "--direction", choices=["up", "down", "left", "right"], required=True
    )
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
    e_prepare.add_argument(
        "--direction", choices=["up", "down", "left", "right"], required=True
    )
    e_prepare.add_argument("--amount", type=int, required=True)
    e_prepare.add_argument("--output", required=True)
    e_prepare.add_argument("--manifest")
    e_prepare.set_defaults(func=cmd_extend_prepare)

    e_apply = extend_sub.add_parser("apply-result")
    e_apply.add_argument("--original", required=True)
    e_apply.add_argument("--generated", required=True)
    e_apply.add_argument(
        "--direction", choices=["up", "down", "left", "right"], required=True
    )
    e_apply.add_argument("--amount", type=int, required=True)
    e_apply.add_argument("--output", required=True)
    e_apply.add_argument("--blend", choices=["poisson", "feather"], default="poisson")
    e_apply.add_argument("--manifest")
    e_apply.set_defaults(func=cmd_extend_apply)

    e_call = extend_sub.add_parser("call")
    add_provider_args(e_call)
    e_call.add_argument("--expanded", required=True)
    e_call.add_argument(
        "--direction", choices=["up", "down", "left", "right"], required=True
    )
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
    e_batch.add_argument(
        "--direction", choices=["up", "down", "left", "right"], required=True
    )
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
    px_update.add_argument(
        "--role", choices=["sky", "far", "mid", "near"], required=True
    )
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
    ts_extract.add_argument(
        "--layout", choices=["auto", "template", "atlas"], default="auto"
    )
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
    sp_process.add_argument(
        "--body-plan", choices=sorted(BODY_PLAN_ANIMS), required=True
    )
    sp_process.add_argument("--anim", required=True)
    sp_process.add_argument("--output-dir", required=True)
    sp_process.add_argument(
        "--vertical-anchor", choices=["baseline", "none"], default="baseline"
    )
    sp_process.add_argument(
        "--horizontal-anchor",
        choices=[
            "upper-q50",
            "upper-q65",
            "upper-q75",
            "upper-q85",
            "bbox-center",
            "feet-center",
            "none",
        ],
        default="upper-q75",
    )
    sp_process.add_argument(
        "--alpha-threshold", type=int, default=SPRITE_ALIGN_ALPHA_THRESHOLD
    )
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
