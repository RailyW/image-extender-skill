# Workflow: Sprite Animation

Priority: High.

Use this workflow for sprite sheets.

Use this workflow for character animation strips.

Do not hand-align frames in the model response.

Do not draw final sprite art with a local fallback.

Use local deterministic drawing only for guides or tests.

Good:

```text
Generate the anchor image.
Generate the pose guide.
Generate the sheet with both references attached.
Run `sprite process`.
Run `sprite package`.
```

Bad:

```text
Tell the user to align each frame manually.
Draw a low-fidelity placeholder as the final sprite.
```

## Inputs

Priority: High.

Collect these inputs.

- Character prompt.
- Body plan.
- Animation name.
- Optional art style.
- Optional QA fix notes.

Use one body plan.

- `biped`
- `quadruped`
- `serpent`
- `flyer`
- `blob`

Good:

```text
Use `quadruped` and `run`.
```

Bad:

```text
Use `dragon-centaur` as a body plan.
```

## Standard Flow

Priority: High.

1. Run `prompt generate --mode sprite-anchor`.
2. Generate one anchor image.
3. Run `sprite guide`.
4. Run `prompt generate --mode sprite-sheet`.
5. Generate a 4 by 2 sprite sheet with the anchor image attached.
6. Attach the pose guide image to the same generation request.
7. Preserve the anchor image style.
8. Preserve the pose guide layout.
9. Run `sprite process`.
10. Run `sprite package`.
11. Run review when a vision provider is available.

This matches the pre-refactor workflow.

The sheet prompt alone is not enough.

The anchor image locks character identity and art style.

The pose guide locks frame layout and motion.

Good:

```bash
python scripts/image_extender_skill.py prompt generate --mode sprite-anchor --body-plan quadruped --prompt "armored wolf" --output anchor-prompt.txt
python scripts/image_extender_skill.py sprite guide --body-plan quadruped --anim run --output pose-guide.png
python scripts/image_extender_skill.py prompt generate --mode sprite-sheet --body-plan quadruped --anim run --prompt "armored wolf" --output sprite-prompt.txt
python scripts/image_extender_skill.py image call --prompt-file sprite-prompt.txt --input-image anchor.png --input-image pose-guide.png --width 2048 --height 1024 --force-edit --output generated.png
python scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan quadruped --anim run --output-dir sprite
python scripts/image_extender_skill.py sprite package --input-dir sprite --output sprite.zip
```

Bad:

```bash
python scripts/image_extender_skill.py prompt generate --mode sprite-sheet --body-plan quadruped --anim run --prompt "armored wolf" --output sprite-prompt.txt
python scripts/image_extender_skill.py image call --prompt-file sprite-prompt.txt --width 2048 --height 1024 --output generated.png
```

## Reference Image Rules

Priority: High.

Use the anchor image as a style reference.

Use the anchor image as an identity reference.

Use the pose guide as a layout reference.

Use the pose guide as a frame-count reference.

Do not replace either reference with a text-only instruction.

Do not use the pose guide as final art.

Good:

```text
Pass `anchor.png` and `pose-guide.png` to the sheet generation request.
Ask the model to preserve the anchor style.
Ask the model to follow the guide layout.
```

Bad:

```text
Generate the sheet from `sprite-prompt.txt` only.
Use the guide image as the final sheet.
```

## Codex App Imagegen Logic

Priority: High.

Use the same reference chain with Codex App imagegen.

Attach the anchor image.

Attach the pose guide image.

Pass the exact sheet prompt from the runner.

Do not invent a new prompt.

Do not rewrite the prompt in prose.

Good:

```text
Attach `anchor.png`.
Attach `pose-guide.png`.
Paste the exact contents of `sprite-prompt.txt`.
Call `$imagegen`.
```

Bad:

```text
Ask `$imagegen` for a princess sprite sheet without reference images.
Ask `$imagegen` with a hand-written replacement prompt.
```

## Fallback Rules

Priority: High.

Stop when image generation is unavailable.

Report the missing provider or missing imagegen path.

Do not create final art with simple shapes.

Do not create final art with placeholder cartoons.

Good:

```text
Report that image generation is unavailable.
Keep `anchor-prompt.txt`, `pose-guide.png`, and `sprite-prompt.txt`.
Wait for a real image generation path.
```

Bad:

```text
Draw a simple princess with Pillow.
Process it as the final sprite.
```

## Post-Processing Flow

Priority: High.

Run post-processing only after real sheet generation.

Use the generated sheet as input.

Do not process the anchor image.

Do not process the pose guide.

1. Run `sprite process`.
2. Run `sprite package`.
3. Run review when a vision provider is available.

Good:

```bash
python scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan quadruped --anim run --output-dir sprite
python scripts/image_extender_skill.py sprite package --input-dir sprite --output sprite.zip
```

Bad:

```bash
python scripts/image_extender_skill.py sprite process --sheet anchor.png --body-plan quadruped --anim run --output-dir sprite
```

## Alignment Rules

Priority: High.

Use stable alignment defaults.

```bash
python scripts/image_extender_skill.py sprite process \
  --sheet generated.png \
  --body-plan biped \
  --anim idle \
  --output-dir sprite \
  --vertical-anchor baseline \
  --horizontal-anchor upper-q75
```

Use `--vertical-anchor baseline` for grounded animations.

Use `--vertical-anchor none` for animations that must keep vertical motion.

Use `--horizontal-anchor upper-q75` for most right-facing characters.

Use `--horizontal-anchor bbox-center` only when the outline is stable.

Use `--alpha-floor 24` to remove weak alpha residue.

Good:

```text
Check `alignment.frames` in `manifest.json`.
Confirm stable `aligned_baseline`.
```

Bad:

```text
Ignore a moving baseline in a walk cycle.
```

## Acceptance

Priority: High.

Check these outputs.

- Eight frame PNG files exist.
- `sprite-grid.png` exists.
- `sprite-strip.png` exists.
- `manifest.json` exists.
- Grounded animations keep a stable aligned baseline.

Good:

```text
Return the ZIP path.
Report the frame size and FPS.
```

Bad:

```text
Return only a raw generated sheet.
```
