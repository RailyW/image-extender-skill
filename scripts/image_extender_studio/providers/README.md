# providers 模块

`providers` 负责解析 BYOK / 自定义 provider 配置，并把不同 OpenAI-compatible 协议统一成文本调用和图片调用两个稳定接口。

## 包含文件

- `client.py`：配置解析、HTTP header 构造、JSON POST、文本 provider 调用、图片 provider 调用、响应文本/图片提取、data URL 和返回图片保存。

## 修改规则

- 新增 provider 协议时，先在 `core/constants.py` 的 `PROVIDER_PROTOCOLS` 中登记，再在 `client.py` 中补请求体和响应解析。
- 不要把 API key 写入代码、README 或示例配置；只允许通过环境变量、命令行参数或本地私有配置传入。
- `codex-app-imagegen` 不是 HTTP provider。脚本只生成 prompt 和做后处理，实际 `$imagegen` 调用由 Skill 编排完成。

