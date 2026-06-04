# Workflow: Extender

Priority: High.

Use this workflow for outpainting.

Use this workflow for edge extension.

Do not ask the model to blend seams manually.

Good:

```text
Prepare the canvas.
Generate or call the image provider.
Apply the result with the runner.
```

Bad:

```text
Tell the user to paint over the seam by hand.
```

## Inputs

Priority: High.

Collect these inputs.

- Source image path.
- Direction: `up`, `down`, `left`, or `right`.
- Extension amount in pixels.
- Optional prompt.
- Optional art style.
- Optional provider config.

Good:

```text
Use `right` and `512`.
```

Bad:

```text
Use an unknown direction such as `diagonal`.
```

## Standard Flow

Priority: High.

1. Run `extend prepare`.
2. Run `prompt extend`.
3. Generate the expanded image.
4. Run `extend apply-result`.
5. Use `extend batch` only when Best-of-N is needed.

Good:

```bash
python scripts/image_extender_skill.py extend prepare --input base.png --direction right --amount 512 --output expanded.png
python scripts/image_extender_skill.py prompt extend --input expanded.png --direction right --amount 512 --prompt "continue the forest" --output prompt.txt
python scripts/image_extender_skill.py extend apply-result --original base.png --generated generated.png --direction right --amount 512 --output final.png
```

Bad:

```bash
python scripts/image_extender_skill.py extend apply-result --original base.png --expanded expanded.png --generated generated.png --direction right --amount 512 --output final.png
```

## Provider Choice

Priority: High.

Use `extend call` for HTTP image providers.

Use `$imagegen` for the Codex App path.

Always pass the generated image back to `extend apply-result`.

Good:

```text
Call `$imagegen`.
Save `generated.png`.
Run `extend apply-result`.
```

Bad:

```text
Return `generated.png` without seam blending.
```

## Acceptance

Priority: High.

Check these outputs.

- The final size equals the original size plus the extension.
- The new area does not contain `#B0B0B0`.
- The manifest contains `seam_score`.

Good:

```text
Report `final.png`.
Report the JSON manifest path.
```

Bad:

```text
Report only the prompt file.
```
