# core 模块

`core` 保存全包共享的基础定义，不包含具体工作流逻辑，也不直接调用 provider 或图像生成模型。

## 包含文件

- `constants.py`：provider 默认值、协议枚举、颜色常量、tile/sprite/props 尺寸、parallax 图层规格、动画默认值和体型动画映射。
- `models.py`：`SpriteAlignmentOptions` 与 `ProviderConfig` 两个 dataclass，作为跨模块传递配置的接口契约；调用方可以直接通过字段名构造实例。
- `io.py`：文本、JSON、slug、stderr 输出和 Pillow 延迟加载工具。

## 修改规则

- 新增跨模块常量时写入 `constants.py`，并在相关模块 README 中说明用途。
- 新增 dataclass 时在类 docstring 中写清楚字段含义和调用方责任，并用最小回归测试验证字段构造方式。
- `io.py` 只放无业务语义的基础工具，避免它反向依赖 workflow 或 provider。
