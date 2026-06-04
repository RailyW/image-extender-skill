# image_extender_studio 包

`image_extender_studio` 是 Image Extender Studio Skill 的 Python 实现包。包内代码把原先耦合在一个大脚本里的功能拆成多个稳定模块，让后续新增 provider、prompt 模板、后处理算法或工作流命令时可以局部修改。

## 子模块

- `core/`：常量、数据模型、文件读写和 Pillow 延迟加载。
- `providers/`：OpenRouter、OpenAI-compatible Chat、Responses、Images 的 provider 适配。
- `prompts/`：扩图、parallax、tileset、sprite、props 和 review 的提示词构造。
- `imaging/`：RGBA 加载保存、洋红色键控、平铺修正、网格切片和 zip 打包等通用图像工具。
- `workflows/`：面向业务的扩图、瓦片、sprite、props、parallax 工作流。
- `cli/`：argparse 命令树和命令处理函数。
- `audit/`：Skill 文件结构与关键能力覆盖审计。

## 修改规则

- 新功能优先放到最贴近职责的子模块中，只有用户可见入口才进入 `cli/`。
- 跨工作流复用的像素处理放入 `imaging/`，不要在具体工作流中复制实现。
- 对外命令保持通过 `scripts/image_extender_skill.py` 访问，避免破坏既有文档和用户脚本。
