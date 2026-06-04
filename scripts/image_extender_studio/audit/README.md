# audit 模块

`audit` 用于检查 Skill 的文件结构、模块 README 和关键能力入口是否仍然完整。它是重构后防止能力悄悄丢失的轻量保护网。

## 包含文件

- `coverage.py`：识别 standalone / monorepo 两种布局，检查必要文件、模块 README 和关键函数名。它会检查 `.gitignore`，但不会要求被忽略的本地 `AGENTS.md` 出现在分发仓库中。它也会检查 `SKILL.md` 与 `references/*.md` 是否残留中文正文，确保 Skill 正文 Markdown 遵守英文规则。

## 修改规则

- 新增必需文档、模块目录或关键能力函数时，把对应路径或函数名加入 `coverage.py`。
- 审计只做快速结构检查，不替代图像结果的人工验收或 provider 集成测试。
- `audit coverage` 应保持离线可运行，不依赖 API key。
