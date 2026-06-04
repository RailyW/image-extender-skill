# prompts 模块

`prompts` 集中保存所有稳定提示词模板和模型 JSON 容错解析逻辑。它让 CLI、Skill 文档和未来自动化流程共用同一套任务约束。

## 包含文件

- `builders.py`：图片生成 prompt、扩图 prompt、scene brief prompt、props ideas prompt、vision review prompt、JSON 容错解析和 props ideas fallback。

## 修改规则

- 新增子流程 prompt 时优先放在 `builders.py`，并通过 CLI 暴露为 `prompt ...` 命令。
- prompt 中涉及尺寸、网格、色键、透明背景和禁止项时，要写成明确规则，减少模型自由发挥。
- 修改 prompt 行为时同步更新 `SKILL.md`、根 `README.md` 和对应 `references/subskill-*.md`。

