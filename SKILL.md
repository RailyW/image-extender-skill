---
name: image-extender-studio
description: "Use this skill to run the Image Extender workflows inside Codex instead of the web studio: AI outpainting, parallax backgrounds, 2D autotiles, sprite animations, and transparent prop libraries. Supports BYOK/custom providers for image/text/vision capabilities and can route image generation through the Codex app imagegen tool when requested."
---

# Image Extender Studio Skill

Priority: High.

Use this skill for deterministic 2D game art workflows.

Do not rewrite image slicing logic in the model response.

Do not rewrite chroma key logic in the model response.

Do not rewrite manifest logic in the model response.

Do not create final artwork with local placeholder drawing.

Call the Python runner for fixed steps.

Good:

```text
Run `python scripts/image_extender_skill.py tileset extract`.
Then report the output files.
```

Bad:

```text
Describe how to crop the tiles manually.
Skip the runner.
Draw a simple placeholder and present it as final art.
```

## When To Use

Priority: High.

Use this skill when the user asks for any listed workflow.

- Extend image edges.
- Run AI outpainting.
- Generate parallax background layers.
- Generate 2D autotiles.
- Generate sprite animation sheets.
- Generate transparent prop libraries.
- Move Image Extender web workflows into Codex.

Good:

```text
The user asks for a parallax forest background.
Read `references/subskill-parallax.md`.
```

Bad:

```text
The user asks for a sprite sheet.
Answer with only a prompt.
```

## Core Flow

Priority: High.

1. Read the user request.
2. Choose one workflow.
3. Choose the provider path.
4. Generate stable prompts with the runner.
5. Generate images with the selected provider.
6. Run deterministic post-processing with the runner.
7. Return files, manifests, and next actions.

Good:

```text
Choose `sprite`.
Generate the prompt.
Call image generation.
Run `sprite process`.
Run `sprite package`.
```

Bad:

```text
Generate a sprite prompt.
Stop before post-processing.
```

## Provider Path

Priority: High.

Read [provider-config.md](references/provider-config.md).

Choose one image path.

- Use `openrouter-chat-completions` for OpenRouter chat image models.
- Use `openai-responses` for Responses image generation.
- Use `openai-images` for text-to-image only.
- Use `codex-app-imagegen` when the user wants Codex image generation.

Choose one text path.

- Use chat completions for scene briefs.
- Use Responses for scene briefs when configured.

Choose one vision path.

- Use chat completions for tile review.
- Use chat completions for sprite review.

Do not write API keys into the repository.

Good:

```text
Read `providers.local.json`.
Resolve `image`, `text`, and `vision`.
Validate with `providers validate`.
```

Bad:

```text
Paste an API key into `SKILL.md`.
Commit a provider file with secrets.
```

## Workflow References

Priority: High.

Read one reference file for the selected workflow.

- Extender: [subskill-extender.md](references/subskill-extender.md).
- Parallax: [subskill-parallax.md](references/subskill-parallax.md).
- Tileset: [subskill-tileset.md](references/subskill-tileset.md).
- Sprite: [subskill-sprite.md](references/subskill-sprite.md).
- Props: [subskill-props.md](references/subskill-props.md).
- Coverage audit: [feature-map.md](references/feature-map.md).

Good:

```text
For a tileset request, read only `subskill-tileset.md` first.
```

Bad:

```text
Load every reference file before choosing a workflow.
```

## Python Modules

Priority: Medium.

Use the compatibility runner.

The runner path is `scripts/image_extender_skill.py`.

The implementation package is `scripts/image_extender_studio/`.

Use the module map.

- `core`: constants, dataclasses, and file utilities.
- `providers`: BYOK and provider protocols.
- `prompts`: prompt builders.
- `imaging`: shared pixel tools.
- `workflows`: deterministic workflow steps.
- `cli`: argument parsing and command dispatch.
- `audit`: structure and coverage checks.

Good:

```text
Add a new user command in `cli/parser.py`.
Put image logic in `workflows/` or `imaging/`.
```

Bad:

```text
Put a new algorithm into `scripts/image_extender_skill.py`.
```

## Common Commands

Priority: Medium.

Run commands from the skill root.

```bash
python scripts/image_extender_skill.py --help
python scripts/image_extender_skill.py providers validate --config providers.example.json
python scripts/image_extender_skill.py prompt generate --mode tileset --prompt "mossy stone platform"
python scripts/image_extender_skill.py tileset guide --output outputs/tile-guide.png
python scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan biped --anim idle --output-dir outputs/sprite --vertical-anchor baseline --horizontal-anchor upper-q75
```

Good:

```text
Run the exact command.
Report the manifest path.
```

Bad:

```text
Invent a new command name.
Omit the output directory.
```

## Agent Installation Text

Priority: Medium.

Use the top section of [README.md](README.md).

Copy the full installation text to another agent.

The other agent may not have this skill installed.

Do not ask it to call `$image-extender-studio`.

Good:

```text
Copy the README installation block.
Ask the other agent to clone the repository.
```

Bad:

```text
Ask the other agent to run this skill before installing it.
```

## Codex App Imagegen Path

Priority: High.

Use this path when the user asks for Codex image generation.

Use this path when no external image provider key exists.

1. Generate a prompt file with the runner.
2. Attach required reference images for the selected workflow.
3. Call `$imagegen`.
4. Save the generated image.
5. Run deterministic post-processing.
6. Return the manifest.

For sprite sheets, attach the anchor image.

For sprite sheets, attach the pose guide image.

For sprite sheets, use the exact runner prompt.

Do not replace the runner prompt with a hand-written prompt.

Do not use local fallback art as final sprite art.

Good:

```text
Run `prompt generate --mode sprite-sheet`.
Attach `anchor.png`.
Attach `pose-guide.png`.
Call `$imagegen`.
Run `sprite process`.
```

Bad:

```text
Call a HTTP provider after the user asked for Codex imagegen.
Call `$imagegen` with text only for a sprite sheet.
Draw a placeholder sprite with Pillow.
```

## Final Checks

Priority: High.

Run these checks before reporting completion.

```bash
python -m compileall -q scripts
python scripts/image_extender_skill.py audit coverage --root .
python scripts/image_extender_skill.py --help
```

Also check for non-English skill markdown text.

Good:

```text
Run the checks.
Report failures honestly.
```

Bad:

```text
Say the work is complete without running checks.
```
