# Provider 配置

本 Skill 兼容三类能力分槽配置，保持 Web app 的 BYOK / 自定义 provider 设计：

- `image`：图片生成、图生图、扩图、Tiles / Sprite / Props 绘制。
- `text`：scene brief、prop ideas 等文本规划。
- `vision`：tile review、sprite review 等带图评审。

## 支持协议

- `openrouter-chat-completions`：OpenRouter `/chat/completions`，图片请求会带 `modalities` 与 `image_config`。
- `openai-chat-completions`：OpenAI-compatible `/chat/completions`，适合文本和视觉评审。
- `openai-responses`：OpenAI Responses `/responses`，图片通过 `image_generation_call` 解析。
- `openai-images`：OpenAI Images `/images/generations`，只适合纯文生图。
- `codex-app-imagegen`：不走 HTTP。Skill 先生成 prompt，Codex 再调用 `$imagegen` 工具，随后脚本做后处理。

## 配置方式

优先级从高到低：

1. CLI 参数：`--image-api-key`、`--text-api-key`、`--vision-api-key` 等。
2. JSON 配置文件：`--config providers.local.json`。
3. 环境变量：`IMAGE_PROVIDER_*`、`TEXT_PROVIDER_*`、`VISION_PROVIDER_*`。
4. 兼容旧变量：`OPENROUTER_API_KEY`。

配置示例：

```json
{
  "image": {
    "protocol": "openai-responses",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-image-2",
    "api_key_env": "OPENAI_API_KEY"
  },
  "text": {
    "protocol": "openai-chat-completions",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "google/gemini-2.0-flash-001",
    "api_key_env": "OPENROUTER_API_KEY"
  },
  "vision": {
    "protocol": "openai-chat-completions",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "google/gemini-2.0-flash-001",
    "api_key_env": "OPENROUTER_API_KEY"
  }
}
```

不要提交包含真实 API key 的配置文件。
