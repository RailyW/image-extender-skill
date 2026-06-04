---
name: image-extender-studio
description: "Use this skill to run the Image Extender workflows inside Codex instead of the web studio: AI outpainting, parallax backgrounds, 2D autotiles, sprite animations, and transparent prop libraries. Supports BYOK/custom providers for image/text/vision capabilities and can route image generation through the Codex app imagegen tool when requested."
---

# Image Extender Studio Skill

本 Skill 把原 Web 工作台拆成 Codex 可执行工作流：Markdown 负责编排和选择路径，`scripts/image_extender_skill.py` 保持兼容入口，实际实现位于 `scripts/image_extender_studio/` 包。不要让 LLM 临场重写切图、色键、导出、manifest 或 provider 适配逻辑；这些步骤必须调用脚本。

## 何时使用

当用户要做以下任一任务时使用本 Skill：

- 扩展图片边缘或做 outpainting。
- 生成横版游戏视差背景，并导出图层包。
- 生成 2D 平台游戏 autotile 瓦片集。
- 生成角色或生物 sprite 动画表。
- 生成透明装饰 props 库。
- 把原 Image Extender Web 工作台能力迁移到 Codex App 中执行。

## 固定执行原则

1. 先读取用户需求，确定目标子流程：`extender`、`parallax`、`tileset`、`sprite`、`props`。
2. 对 provider 做显式选择：自定义 provider / BYOK / Codex App `imagegen`。
3. 所有固定步骤都调用 Python 脚本：prompt 生成、provider JSON、画布扩展、Poisson/羽化融合、色键、切图、guide 生成、对齐、打包、manifest。
4. 当选择 Codex App `imagegen` 时，先用脚本生成稳定 prompt，再调用 `$imagegen` 生成图片，最后把生成图片交回脚本后处理。
5. 输出必须包含可交付文件路径、manifest 和用户下一步可直接使用的资源。

## Provider 模式

读取 [provider-config.md](references/provider-config.md) 选择 provider。默认推荐：

- `image`：OpenRouter chat image、OpenAI Responses、OpenAI Images，或 Codex App `imagegen`。
- `text`：OpenAI-compatible chat 或 Responses，用于 scene brief / prop ideas。
- `vision`：OpenAI-compatible chat 或 Responses，用于 tile / sprite QA。

密钥只通过环境变量、命令行参数或用户提供的本地配置传入；不要把密钥写入仓库。脚本支持与 Web app 相同的三类能力分槽配置。

## 子流程导航

按任务读取对应参考文件：

- Extender 扩图：读 [subskill-extender.md](references/subskill-extender.md)。
- Parallax 视差背景：读 [subskill-parallax.md](references/subskill-parallax.md)。
- Tileset 自动瓦片：读 [subskill-tileset.md](references/subskill-tileset.md)。
- Sprite 动画：读 [subskill-sprite.md](references/subskill-sprite.md)。
- Props 装饰库：读 [subskill-props.md](references/subskill-props.md)。
- 功能覆盖审计：读 [feature-map.md](references/feature-map.md)。

## 工程化模块导航

Python 实现已经按职责拆分：

- `scripts/image_extender_skill.py`：兼容入口，只负责调用包内 CLI。
- `scripts/image_extender_studio/core/`：常量、数据模型和通用 IO。
- `scripts/image_extender_studio/providers/`：BYOK / 自定义 provider 协议适配。
- `scripts/image_extender_studio/prompts/`：各子流程稳定 prompt 构造。
- `scripts/image_extender_studio/imaging/`：跨工作流复用的像素和打包工具。
- `scripts/image_extender_studio/workflows/`：extender、parallax、tileset、sprite、props 的确定性处理流程。
- `scripts/image_extender_studio/cli/`：命令树与命令分派。
- `scripts/image_extender_studio/audit/`：文件结构和关键能力覆盖审计。

新增或修改功能时，同步更新根 `README.md`、本 `SKILL.md`、对应 `references/subskill-*.md` 和相关模块 README。

## 常用脚本入口

所有命令都从 skill 目录运行，或显式传入脚本绝对路径：

```bash
python scripts/image_extender_skill.py --help
python scripts/image_extender_skill.py providers validate --config providers.example.json
python scripts/image_extender_skill.py prompt generate --mode tileset --prompt "mossy stone platform"
python scripts/image_extender_skill.py tileset guide --output outputs/tile-guide.png
python scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan biped --anim idle --output-dir outputs/sprite --vertical-anchor baseline --horizontal-anchor upper-q75
```

图像后处理命令需要 Pillow；Codex App 的内置 Python 通常可用，普通系统 Python 缺少时脚本会给出安装提示。

## Agents 自动安装提示词

当用户希望把安装工作交给另一个尚未安装本 Skill 的 agent 时，让用户复制根 [README.md](README.md) 中的“复制给 Agents 自动安装”整段文本。那段文本本身就是功能入口，不依赖任何本仓库脚本或 `$image-extender-studio` 已存在；它会指示对方 agent 直接从仓库获取内容并复制到自己的 skill 目录。

## Codex App imagegen 路径

如果用户要求“直接在 Codex App 中调用 image gen”，或没有外部 provider key：

1. 用 `prompt generate` / `prompt extend` / 对应子命令生成稳定 prompt 文件。
2. 调用 `$imagegen`，让 Codex App 生成位图。
3. 将生成图片保存到输出目录。
4. 用 `tileset extract`、`sprite process`、`props process`、`parallax package` 或 `extend apply-result` 完成确定性后处理。

Python 脚本不能直接调用 Codex App 的工具，因此 Skill 的 Markdown 编排负责调用 `$imagegen`，脚本负责准备 prompt 与后处理。

## 结束前检查

交付前至少执行：

```bash
python -m compileall -q scripts
python scripts/image_extender_skill.py audit coverage --root .
python scripts/image_extender_skill.py --help
```

若修改了原 Web 应用代码，再额外运行项目构建命令。
