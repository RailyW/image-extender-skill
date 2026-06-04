"""Skill 文件结构和功能覆盖审计。

审计既检查用户可见文档，也检查工程化拆分后的 Python 包中是否仍包含
关键能力入口，避免后续重构悄悄丢失子流程。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _candidate_roots(root_path: Path) -> tuple[str, list[str], Path]:
    """识别 standalone skill 与 monorepo skill 两种常见目录布局。"""
    standalone_script = root_path / "scripts" / "image_extender_skill.py"
    monorepo_script = (
        root_path
        / "skills"
        / "image-extender-studio"
        / "scripts"
        / "image_extender_skill.py"
    )
    if standalone_script.exists():
        return "standalone", [""], root_path / "scripts" / "image_extender_studio"
    return (
        "monorepo",
        ["skills/image-extender-studio/"],
        root_path
        / "skills"
        / "image-extender-studio"
        / "scripts"
        / "image_extender_studio",
    )


def audit_coverage(root: str) -> dict[str, Any]:
    """检查 Skill 文件、模块 README 和关键 Python 能力是否完整。"""
    root_path = Path(root)
    layout, prefixes, package_path = _candidate_roots(root_path)
    prefix = prefixes[0]
    required_files = [
        f"{prefix}.gitignore",
        f"{prefix}README.md",
        f"{prefix}SKILL.md",
        f"{prefix}agents/openai.yaml",
        f"{prefix}references/feature-map.md",
        f"{prefix}references/provider-config.md",
        f"{prefix}references/subskill-extender.md",
        f"{prefix}references/subskill-parallax.md",
        f"{prefix}references/subskill-tileset.md",
        f"{prefix}references/subskill-sprite.md",
        f"{prefix}references/subskill-props.md",
        f"{prefix}scripts/README.md",
        f"{prefix}scripts/image_extender_skill.py",
        f"{prefix}scripts/image_extender_studio/README.md",
        f"{prefix}scripts/image_extender_studio/core/README.md",
        f"{prefix}scripts/image_extender_studio/providers/README.md",
        f"{prefix}scripts/image_extender_studio/prompts/README.md",
        f"{prefix}scripts/image_extender_studio/imaging/README.md",
        f"{prefix}scripts/image_extender_studio/workflows/README.md",
        f"{prefix}scripts/image_extender_studio/cli/README.md",
        f"{prefix}scripts/image_extender_studio/audit/README.md",
    ]
    missing = [path for path in required_files if not (root_path / path).exists()]

    # 兼容工程化拆分后的包结构：关键能力不再要求集中出现在入口脚本中。
    script_text = ""
    if package_path.exists():
        for py_file in package_path.rglob("*.py"):
            script_text += "\n" + py_file.read_text(encoding="utf-8")
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
    missing_terms = [term for term in required_terms if term not in script_text]
    ok = not missing and not missing_terms
    return {
        "ok": ok,
        "layout": layout,
        "missing_files": missing,
        "missing_script_terms": missing_terms,
    }
