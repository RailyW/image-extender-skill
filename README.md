# Image Extender Studio Skill

## 一句话复制给 Agents 自动安装

下面这段话不依赖本 skill 已安装。直接复制给任意支持本地文件操作和网络访问的 AI agent，它就能从本仓库拿到 skill 内容，并复制到它自己的 skill 目录中：

```text
你当前不需要预先安装 `image-extender-studio` skill。请直接从下面的仓库获取 skill 内容，并复制到你自己运行环境的 skill 目录中，完成自动安装。

仓库：https://github.com/RailyW/image-extender-skill.git
目标目录：请识别你当前运行环境自己的 skill 目录，优先使用 ~/.codex/skills/image-extender-studio；如果你的环境使用 ~/.agents/skills，则使用 ~/.agents/skills/image-extender-studio。

执行要求：
1. 不要尝试调用 `$image-extender-studio`，因为当前环境可能还没有安装它；请使用 `git clone`、下载 zip，或其他可用方式先取得仓库内容。
2. 如果目标目录不存在，请创建目标目录并把仓库内容复制进去；如果目标目录已存在，请先检查是否有本地未保存修改，不要直接覆盖。
3. 安装后的目录顶层必须包含 `SKILL.md`、`README.md`、`agents/openai.yaml`、`references/`、`scripts/image_extender_skill.py` 和 `scripts/image_extender_studio/`。
4. 在安装后的 skill 根目录运行 `python scripts/image_extender_skill.py --help` 和 `python scripts/image_extender_skill.py audit coverage --root .`，确认命令可用且审计通过。
5. 如果当前 agent 支持注册、刷新或重新索引 skill，请执行对应刷新；否则告诉我需要重启或刷新会话后才能使用。
6. 不要把任何 API key 写入仓库；provider key 只通过环境变量、命令行参数或本地私有配置传入。
```

Image Extender Studio Skill 用于在 Codex 中执行 2D AI 游戏美术工作流，包括图片扩图、横版视差背景、自动瓦片、sprite 动画表和透明 props 库。它把稳定、可复用、容易出错的步骤放进 Python 脚本，把任务编排和场景判断保留在 `SKILL.md` 与各个参考文档中。

## 适用场景

- 对已有图片做 outpainting 或边缘扩展。
- 生成横版游戏的四层 parallax 背景，并导出图层包。
- 生成 2D 平台游戏 autotile tileset。
- 生成角色或生物的 4x2 sprite animation sheet，并做基线与锚点对齐。
- 生成透明装饰 props sheet、atlas、manifest 和 zip 包。
- 在 Codex App 中使用内置 `$imagegen`，或通过 BYOK / 自定义 OpenAI-compatible provider 调用模型。

## Skill 用法

在 Codex 中触发 `$image-extender-studio` 后，先根据用户目标读取对应参考文档：

- 扩图：`references/subskill-extender.md`
- 视差背景：`references/subskill-parallax.md`
- 自动瓦片：`references/subskill-tileset.md`
- Sprite 动画：`references/subskill-sprite.md`
- Props：`references/subskill-props.md`
- Provider 配置：`references/provider-config.md`

固定步骤必须调用兼容入口：

```bash
python scripts/image_extender_skill.py --help
python scripts/image_extender_skill.py prompt generate --mode tileset --prompt "mossy stone platform"
python scripts/image_extender_skill.py tileset guide --output outputs/tile-guide.png
python scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan biped --anim idle --output-dir outputs/sprite
python scripts/image_extender_skill.py audit coverage --root .
```

`scripts/image_extender_skill.py` 只保留历史兼容入口；实际实现已经拆分到 `scripts/image_extender_studio/`。新增能力时优先在对应子模块内实现，再在 `scripts/image_extender_studio/cli/parser.py` 注册命令。

## 安装方法

把仓库放到 Codex skill 目录中即可。常见目录如下：

```bash
git clone https://github.com/RailyW/image-extender-skill.git ~/.codex/skills/image-extender-studio
```

如果你的环境使用 agents skill 根目录，也可以安装到：

```bash
git clone https://github.com/RailyW/image-extender-skill.git ~/.agents/skills/image-extender-studio
```

安装后在 skill 根目录运行：

```bash
python scripts/image_extender_skill.py --help
python scripts/image_extender_skill.py audit coverage --root .
```

图像后处理依赖 Pillow。若当前 Python 环境缺少 Pillow，脚本会在执行图像命令时提示安装方式。

## 目录结构

```text
.
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── references/
└── scripts/
    ├── image_extender_skill.py
    └── image_extender_studio/
        ├── core/
        ├── providers/
        ├── prompts/
        ├── imaging/
        ├── workflows/
        ├── cli/
        └── audit/
```

## 开发约定

- 新增功能时同步更新 `README.md`、`SKILL.md` 和相关模块 README。
- 所有临时 TDD 或验证测试放到 `.codex-tdd-tests/`，该目录已被 `.gitignore` 忽略。
- `AGENTS.md` 是本地协作规则文件，已被 `.gitignore` 忽略，不进入仓库历史。
- 不要提交真实 API key；provider key 只通过环境变量、命令行参数或本地私有配置传入。

## 灵感来源

- [boona13/image-extender](https://github.com/boona13/image-extender)
