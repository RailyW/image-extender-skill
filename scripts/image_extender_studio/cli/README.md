# cli 模块

`cli` 负责把用户可见命令映射到具体模块函数。它是外部调用和内部实现之间的薄分派层。

## 包含文件

- `parser.py`：argparse 命令树、参数默认值、choices 和 `main` 入口。
- `commands.py`：每个 `cmd_*` 函数读取 argparse Namespace，调用 provider、prompt 或 workflow 模块，并把结果写到 stdout 或文件。

## 修改规则

- 新增用户可见功能时，在 `parser.py` 注册命令和参数，在 `commands.py` 写薄命令函数。
- `commands.py` 不承载图像算法，不直接写复杂 prompt，不直接解析 provider 协议。
- 修改参数名或默认值时同步更新 `SKILL.md`、根 `README.md` 和相关 `references/subskill-*.md`。

