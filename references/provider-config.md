# Provider Configuration

Priority: High.

Use this file when choosing provider settings.

Do not guess provider protocols.

Do not write secrets into repository files.

Good:

```text
Load a local provider JSON file.
Resolve each capability.
Run `providers validate`.
```

Bad:

```text
Paste an API key into a tracked markdown file.
Use an unsupported protocol name.
```

## Capability Slots

Priority: High.

Use three capability slots.

- `image`: image generation, image editing, outpainting, tiles, sprites, and props.
- `text`: scene briefs and prop ideas.
- `vision`: tile review and sprite review.

Good:

```json
{
  "image": {
    "protocol": "openai-responses",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-image-2",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

Bad:

```json
{
  "all": {
    "api_key": "real-secret-value"
  }
}
```

## Supported Protocols

Priority: High.

Use only supported protocol names.

- `openrouter-chat-completions`
- `openai-chat-completions`
- `openai-responses`
- `openai-images`
- `codex-app-imagegen`

Use `openrouter-chat-completions` for OpenRouter chat image models.

Use `openai-chat-completions` for OpenAI-compatible text and vision calls.

Use `openai-responses` for Responses text, vision, and image workflows.

Use `openai-images` for text-to-image only.

Use `codex-app-imagegen` when Codex must call `$imagegen`.

Good:

```text
Use `openai-responses` for image edits with input images.
```

Bad:

```text
Use `openai-images` for an edit with input images.
```

## Resolution Order

Priority: High.

Apply this order.

1. Read CLI arguments.
2. Read environment variables.
3. Read JSON configuration.
4. Use legacy `OPENROUTER_API_KEY`.
5. Use defaults only after explicit inputs are missing.

Good:

```text
Pass `--image-model` to override the JSON model.
```

Bad:

```text
Ignore the CLI value because the JSON file has a model.
```

## Example Configuration

Priority: Medium.

Use this shape for local files.

Do not commit files with real secrets.

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

Good:

```text
Store this as `providers.local.json`.
Keep it untracked.
```

Bad:

```text
Commit `providers.local.json` with a real API key.
```
