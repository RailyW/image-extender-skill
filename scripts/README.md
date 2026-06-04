# scripts 模块

本目录保存 Image Extender Studio Skill 的确定性执行脚本。它负责把 `SKILL.md` 中描述的工作流落到可重复运行的命令行入口，避免 agent 在每次任务中临时重写图像切片、色键、打包、provider 调用或 manifest 生成逻辑。

## 包含文件

- `image_extender_skill.py`：历史兼容入口。外部文档和用户脚本继续调用这个文件，它会转发到 `image_extender_studio.cli.parser.main`。
- `image_extender_studio/`：工程化后的 Python 包，按职责拆分为 core、providers、prompts、imaging、workflows、cli、audit 和 installation。

## 修改规则

- 不要在 `image_extender_skill.py` 中重新堆叠业务逻辑；新增命令时改 `image_extender_studio/cli/parser.py` 和对应业务模块。
- 修改任一脚本模块时，同步检查本 README、包级 README 和 `SKILL.md` 的命令示例是否仍然准确。
- 临时测试或验证脚本放到仓库根目录 `.codex-tdd-tests/`，不要放进本目录。

